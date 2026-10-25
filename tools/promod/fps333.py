#!/usr/bin/env python3
"""Rebuild only Promod's two FPS menus from the verified installed fastfile."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess

PROMOD_SHA = '930c9123b679394c18683f890d8e792d3b31cafacadda2c3293e5e066e9fb1c2'
OAT = {'Unlinker': 'fe36b530f638b87410a3a651663217824c89c98209211ac4265e733b1409ea23',
       'Linker': '0e46f052ceb819e24656b45fcb3754c7c9a7ecd74de1e6095c8c67bb45a00896'}
RULE = 'dvarint("com_maxfps") > 250'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def patch_menu(source, count, warning):
    if source.count(RULE) != count or source.count('SET COM_MAXFPS WITHIN 40-250') != warning:
        raise ValueError('Unexpected installed FPS menu; refusing to change it')
    return source.replace(RULE, 'dvarint("com_maxfps") > 333').replace(
        'SET COM_MAXFPS WITHIN 40-250', 'SET COM_MAXFPS WITHIN 40-333')


def expression_tree(source):
    """Compare typed boolean trees, preserving precedence and unrelated checks."""
    pattern = r'\s*("(?:\\.|[^"\\])*"|\d+(?:\.\d+)?|[A-Za-z_]\w*|&&|\|\||==|!=|<=|>=|[!<>() ,])'
    tokens = []
    offset = 0
    while offset < len(source):
        match = re.match(pattern, source[offset:])
        if not match:
            raise ValueError('Unsupported menu expression: ' + source[offset:])
        tokens.append(match[1]); offset += match.end()
    cursor = 0
    precedence = {'||': 1, '&&': 2, '==': 3, '!=': 3, '<': 4, '>': 4, '<=': 4, '>=': 4}

    def parse(minimum=0):
        nonlocal cursor
        token = tokens[cursor]; cursor += 1
        if token == '!':
            left = ('!', parse(5))
        elif token == '(':
            left = parse()
            if tokens[cursor] != ')': raise ValueError('Unbalanced expression')
            cursor += 1
        elif cursor < len(tokens) and tokens[cursor] == '(':
            cursor += 1
            argument = parse()
            if tokens[cursor] != ')': raise ValueError('Unsupported function arguments')
            cursor += 1
            left = ('call', token, argument)
        else:
            left = token
        while cursor < len(tokens) and tokens[cursor] in precedence and precedence[tokens[cursor]] >= minimum:
            operator = tokens[cursor]; cursor += 1
            left = (operator, left, parse(precedence[operator] + 1))
        return left

    result = parse()
    if cursor != len(tokens): raise ValueError('Trailing expression tokens')
    return result


def canonical_menu(source):
    result = []
    for line in source.splitlines():
        line = line.strip()
        visible = re.fullmatch(r'visible\s+when\((.*)\);', line)
        text = re.fullmatch(r'exp text\s+\(?((?:"(?:\\.|[^"\\])*")+)\)?;', line)
        if visible: result.append(('visible', expression_tree(visible[1])))
        elif text: result.append(('text', text[1]))
        else: result.append(line)
    return result


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--promod', type=Path, required=True, help='Original private mod.ff')
    p.add_argument('--oat', type=Path, required=True, help='Verified official OAT v0.34.0 Linux tools')
    p.add_argument('--output', type=Path, required=True, help='New private build directory')
    args = p.parse_args()
    if sha(args.promod) != PROMOD_SHA: p.error('Original installed Promod hash mismatch')
    for name, expected in OAT.items():
        if sha(args.oat / name) != expected: p.error('OAT binary hash mismatch: ' + name)
    if args.output.exists(): p.error('Output must not exist; original inputs are never overwritten')
    output = args.output.resolve(); output.mkdir(parents=True)

    def run(name, options, log):
        result = subprocess.run([str((args.oat / name).resolve()), '--no-color', *map(str, options)],
                                capture_output=True, text=True)
        text = result.stdout + result.stderr
        (output / log).write_text(text)
        if result.returncode or 'ERROR:' in text or 'Finished with 0 warnings, 0 errors' not in text:
            raise RuntimeError('Asset tool failed; see ' + str(output / log))

    original = output / 'original'
    run('Unlinker', ['--include-assets', 'menu,menulist,localize,rawfile', '--output-folder', original, args.promod.resolve()], 'extract.log')
    project = output / 'project'
    (project / 'raw/ui_mp').mkdir(parents=True)
    (project / 'zone_source').mkdir()
    for name, count, warning in [('xpbar', 1, 0), ('talkers', 2, 1)]:
        source = (original / 'ui_mp' / (name + '.menu')).read_text()
        (project / 'raw/ui_mp' / (name + '.menu')).write_text(patch_menu(source, count, warning))
    shutil.copytree(original / 'english', project / 'raw/english')
    shutil.copy2(original / 'zone_source/mod.zone', project / 'zone_source/mod.zone')
    (project / 'zone_source/fps333.zone').write_text(
        '>game,IW3\n>name,mod\nmenulist,ui_mp/xpbar.menu\nmenulist,ui_mp/talkers.menu\ninclude,mod\n')
    run('Linker', ['--base-folder', project, '--load', args.promod.resolve(), '--menu-no-optimization', 'fps333'], 'link.log')
    binary = project / 'zone_out/fps333/mod.ff'
    rebuilt = output / 'verified'
    run('Unlinker', ['--include-assets', 'menu,menulist,localize,rawfile', '--output-folder', rebuilt, binary], 'verify.log')
    compared = 0
    for source in original.rglob('*'):
        if not source.is_file() or 'zone_source' in source.parts: continue
        relative = source.relative_to(original)
        target = rebuilt / relative
        if str(relative) in ['ui_mp/xpbar.menu', 'ui_mp/talkers.menu']:
            count, warning = (1, 0) if relative.name == 'xpbar.menu' else (2, 1)
            if canonical_menu(patch_menu(source.read_text(), count, warning)) != canonical_menu(target.read_text()):
                raise ValueError('Unexpected change in FPS menu: ' + str(relative))
        elif source.read_bytes() != target.read_bytes():
            raise ValueError('Unrelated extracted asset changed: ' + str(relative))
        compared += 1
    # Original asset inventory must remain, with only the two required menu containers added.
    def inventory(path):
        return {line for line in path.read_text().splitlines() if line and not line.startswith(('//', '>'))}
    expected = inventory(original / 'zone_source/mod.zone') | {'menulist,ui_mp/xpbar.menu', 'menulist,ui_mp/talkers.menu'}
    if inventory(rebuilt / 'zone_source/mod.zone') != expected:
        raise ValueError('Unexpected asset inventory change')
    record = {'source_mod_ff_sha256': PROMOD_SHA, 'mod_ff_sha256': sha(binary), 'oat_version': 'v0.34.0',
              'oat_binary_sha256': OAT, 'verified_extracted_assets': compared, 'minimum_fps': 40, 'maximum_fps': 333,
              'graphical_client_validation': 'pending', 'modified_menu_assets': ['xpbar', 'talkers']}
    (output / 'manifest.json').write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps(record, indent=2))


if __name__ == '__main__': main()
