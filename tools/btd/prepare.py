#!/usr/bin/env python3
"""Verify original BTD assets and generate a private, narrowly guarded source overlay."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import struct
import zlib

ROOT = Path(__file__).resolve().parents[2]


def digest(path):
    if path.is_symlink() or not path.is_file():
        raise ValueError(f'Missing or symlinked input: {path}')
    return hashlib.sha256(path.read_bytes()).hexdigest()


SCRIPT = 'maps/mp/gametypes/_globallogic.gsc'
DEATH_CONDITION = 'isDefined(eInflictor) && eInflictor.targetname == "zom"'
SAFE_DEATH_CONDITION = ('isDefined(eInflictor) && isDefined(eInflictor.targetname)'
                        ' && eInflictor.targetname == "zom"')


def raw_source(fastfile, name, expected):
    # This member is plaintext GSC already stored in the verified fastfile.
    # No bytecode decompiler or asset rebuild is involved. Never save the source
    # in the repository; only the operator's private prepared runtime receives it.
    data = zlib.decompress(fastfile[12:])
    marker = b'\xff' * 4 + name.encode() + b'\0'
    offset = data.find(marker)
    if offset < 8 or data.find(marker, offset + 1) != -1:
        raise ValueError('Missing or ambiguous BTD death callback raw source')
    length = struct.unpack('<I', data[offset - 4:offset])[0]
    start = offset + len(marker)
    if length > 1024 * 1024 or start + length >= len(data) or data[start + length] != 0:
        raise ValueError('Unsupported BTD raw source layout')
    raw = data[start:start + length]
    if hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError('BTD death callback source hash mismatch')
    return raw.decode('utf-8')


def death_overlay(fastfile, expected):
    source = raw_source(fastfile, SCRIPT, expected)
    if source.count(DEATH_CONDITION) != 1:
        raise ValueError('Unexpected BTD death callback condition')
    return source.replace(DEATH_CONDITION, SAFE_DEATH_CONDITION).encode('utf-8')


SPAWN_SCRIPT = 'btd_gametypes/survival/_survival_spawns.gsc'
SPAWN_ORIGIN = 'temp.origin = zomspawnpoint[i];'


def spawn_overlay(fastfile, expected):
    source = raw_source(fastfile, SPAWN_SCRIPT, expected)
    if source.count(SPAWN_ORIGIN) != 1:
        raise ValueError('Unexpected BTD spawn point initialization')
    # The shipped spawn structs provide only origin; the zombie constructor
    # assigns their missing angles to a native vector field, aborting wave one.
    return source.replace(SPAWN_ORIGIN, SPAWN_ORIGIN +
                          ' temp.angles = (0, 0, 0);').encode('utf-8')


def prepare(source, headers, binary, output):
    lock = json.loads((ROOT / 'tools/btd/dependencies.json').read_text())
    header_lock = json.loads((ROOT / 'bots/dependencies.json').read_text())['integrity_headers']
    for base, expected in ((source, lock['files']), (headers, header_lock)):
        for name, value in expected.items():
            path = base / name
            if any(parent.is_symlink() for parent in path.parents if parent != base.parent):
                raise ValueError(f'Symlinked input path: {path}')
            if digest(path) != value:
                raise ValueError(f'Input hash mismatch: {name}')
    overlay = death_overlay((source / 'btd_alpha_001/mod.ff').read_bytes(),
                            lock['death_callback_source_sha256'])
    spawn = spawn_overlay((source / 'btd_alpha_001/mod.ff').read_bytes(),
                          lock['spawn_points_source_sha256'])
    binary_hash = digest(binary)
    if output.exists():
        raise ValueError('Output must be a new directory; existing runtimes are never overwritten')
    destination = output.resolve()
    for path in (source, headers, binary):
        if destination == path.resolve() or destination.is_relative_to(path.resolve()) or path.resolve().is_relative_to(destination):
            raise ValueError('Output must be separate from inputs')
    output.mkdir(parents=True)
    (output / '.bot-test-runtime').touch()
    mod = output / 'mods/btd_alpha_001'
    mod.mkdir(parents=True)
    # Keep original CFGs private, excluding the unsafe sample server/passwords.
    for name in lock['files']:
        if name.startswith('btd_alpha_001/') and Path(name).name != 'server.cfg':
            shutil.copy2(source / name, mod / Path(name).name)
    patched = mod / SCRIPT.replace('.gsc', '.gsx')
    patched.parent.mkdir(parents=True)
    patched.write_bytes(overlay)
    spawn_path = mod / SPAWN_SCRIPT.replace('.gsc', '.gsx')
    spawn_path.parent.mkdir(parents=True, exist_ok=True)
    spawn_path.write_bytes(spawn)
    notices = output / 'licenses'
    notices.mkdir()
    shutil.copy2(source / 'readme.txt', notices / 'Before-the-Dawn-readme.txt')
    target_headers = output / 'integrity/addiwdheaders'
    target_headers.mkdir(parents=True)
    for name in header_lock:
        shutil.copy2(headers / name, target_headers / name)
    shutil.copy2(binary, output / 'cod4x18_dedrun')
    (output / 'cod4x18_dedrun').chmod(0o755)
    rotation = (source / 'btd_alpha_001/btd_maprotation.cfg').read_text()
    record = {'asset_type': 'btd-alpha-001', 'fs_game': 'mods/btd_alpha_001',
              'maps': re.findall(r'\bmap (mp_[a-z0-9_]+)', rotation),
              'binary_sha256': binary_hash, 'headers': header_lock,
              'assets': {Path(k).name: v for k, v in lock['files'].items()
                         if k.startswith('btd_alpha_001/') and Path(k).name != 'server.cfg'},
              'default_cfgs': lock['default_cfgs'],
              'overlays': {str(patched.relative_to(mod)): digest(patched),
                           str(spawn_path.relative_to(mod)): digest(spawn_path)},
              'death_callback_source_sha256': lock['death_callback_source_sha256'],
              'spawn_points_source_sha256': lock['spawn_points_source_sha256'],
              'dependency_lock_sha256': digest(ROOT / 'tools/btd/dependencies.json'),
              'qualification': 'original package map list; gameplay qualification is separate'}
    (output / 'inputs.json').write_text(json.dumps(record, indent=2) + '\n')
    return record


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('source', 'headers', 'binary', 'output'):
        parser.add_argument('--' + name, required=True, type=Path)
    args = parser.parse_args()
    try:
        record = prepare(args.source, args.headers, args.binary, args.output)
    except (OSError, ValueError) as exc:
        parser.exit(1, f'BTD preparation failed: {exc}\n')
    print(json.dumps({'runtime': str(args.output), 'maps': record['maps']}, indent=2))
