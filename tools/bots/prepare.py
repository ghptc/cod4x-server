#!/usr/bin/env python3
"""Prepare a private runtime from verified local inputs, without editing originals."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import struct
import zlib
import zipfile

ROOT = Path(__file__).resolve().parents[2]


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def admin_rules(source):
    # Run after each original assignment, before Promod caches level.* settings.
    names = ['scr_sd_timelimit', 'scr_sd_roundlimit', 'scr_sd_scorelimit',
             'scr_sd_roundswitch', 'scr_team_fftype', 'sv_voice']
    for name in names:
        pattern = r'(setDvar\( "' + name + r'", [^;]+ \);)'
        if len(re.findall(pattern, source)) != 1:
            raise ValueError('Unexpected installed custom_public rule: ' + name)
        override = 'cod4x_rule_' + name
        source = re.sub(pattern, lambda match: match[0] +
            '\n\tif (getDvarInt("sv_promod_admin") && getDvar("' + override + '") != "" && getDvarFloat("' + override + '") >= 0)\n'
            '\t\tsetDvar("' + name + '", getDvarFloat("' + override + '"));\n', source)
    return '// Private derived ruleset, 2026-10-25. Original defaults/notices retained; see docs/administration.md.\n' + source


def omit_function(source, name):
    match = re.search(r'^' + name + r'\([^)]*\)\s*\{', source, re.M)
    if not match:
        raise ValueError('Unexpected upstream source: ' + name)
    end, depth = match.end(), 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[:match.start()] + '// Combat-only integration omits ' + name + '\n' + source[end:]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--promod', type=Path, required=True)
    parser.add_argument('--bot-warfare', type=Path, required=True)
    parser.add_argument('--headers', type=Path, required=True)
    parser.add_argument('--binary', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--admin-rules', action='store_true',
                        help='Prepare optional validated custom_public rule overrides')
    args = parser.parse_args()
    lock = json.loads((ROOT / 'bots/dependencies.json').read_text())
    for directory, files in [(args.promod, lock['promod']['files']),
                             (args.bot_warfare, lock['vendor_files']),
                             (args.headers, lock['integrity_headers'])]:
        for name, expected in files.items():
            if digest(directory / name) != expected:
                raise SystemExit('Input hash mismatch: ' + str(directory / name))
    destination = args.output.resolve()
    for source in [args.promod, args.bot_warfare, args.headers, args.binary]:
        if source.resolve().is_relative_to(destination) or (source.is_dir() and destination.is_relative_to(source.resolve())):
            raise SystemExit('Output must be separate from all inputs')
    if destination.exists() and not (destination / '.bot-test-runtime').is_file():
        raise SystemExit('Refusing to overwrite a directory not prepared by this tool')
    destination.mkdir(parents=True, exist_ok=True)
    (destination / '.bot-test-runtime').touch()
    mod = destination / 'mods/pml220'
    mod.mkdir(parents=True, exist_ok=True)
    for name in lock['promod']['files']:
        shutil.copy2(args.promod / name, mod / name)
    rulefile = mod / 'promod_ruleset/custom_public.gsx'
    if args.admin_rules:
        with zipfile.ZipFile(args.promod / 'z_c_r.iwd') as archive:
            source = archive.read('promod_ruleset/custom_public.gsc').decode()
        rulefile.parent.mkdir(exist_ok=True)
        rulefile.write_text(admin_rules(source))
        helper = mod / 'maps/mp/cod4x_admin.gsc'
        helper.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / 'scripts/promod_admin.gsc', helper)
    elif rulefile.exists():
        rulefile.unlink()
    if not args.admin_rules and (mod / 'maps/mp/cod4x_admin.gsc').exists():
        (mod / 'maps/mp/cod4x_admin.gsc').unlink()
    headers = destination / 'integrity/addiwdheaders'
    headers.mkdir(parents=True, exist_ok=True)
    for name in lock['integrity_headers']:
        shutil.copy2(args.headers / name, headers / name)
    shutil.copy2(args.binary, destination / 'cod4x18_dedrun')
    (destination / 'cod4x18_dedrun').chmod(0o755)
    target = mod / 'maps/mp/bots'
    (target / 'waypoints').mkdir(parents=True, exist_ok=True)
    vendor = args.bot_warfare
    internal = (vendor / 'maps/mp/bots/_bot_internal.gsc').read_text()
    internal = internal.replace('maps\\mp\\gametypes\\_missions::getweaponclass', 'maps\\mp\\bots\\_bot_utility::getweaponclass')
    internal = internal.replace('self endon( "disconnect" );',
        'self endon( "disconnect" );\n\tself endon( "promod_ai_reset" );\n\tlevel endon( "game_ended" );')
    (target / '_bot_internal.gsc').write_text('// Modified 2026-10-25: Promod lookup and thread lifetime. Original attribution retained in docs/third-party-bots.md.\n' + internal)
    utility = (vendor / 'maps/mp/bots/_bot_utility.gsc').read_text()
    for name in ['onUsePlantObjectFix', 'bombPlantedFix', 'isWeaponDroppable']:
        utility = omit_function(utility, name)
    utility += '\ngetweaponclass(weap) { tokens = strtok(weap, "_"); return tablelookup("mp/statstable.csv", 4, tokens[0], 2); }\n'
    (target / '_bot_utility.gsc').write_text('// Modified 2026-10-25: combat-only Promod integration; no bomb callbacks replaced.\n' + utility)
    shutil.copy2(vendor / 'maps/mp/bots/waypoints/_custom_map.gsc', target / 'waypoints/_custom_map.gsc')
    shutil.copy2(vendor / 'scripts/bots_adapter_cod4x.gsc', target / 'adapter.gsc')
    shutil.copy2(ROOT / 'bots/promod_ai.gsc', target / 'promod_ai.gsc')
    waypoints = mod / 'scriptdata/waypoints'
    waypoints.mkdir(parents=True, exist_ok=True)
    for name in lock['vendor_files']:
        if name.endswith('_wp.csv'):
            shutil.copy2(vendor / name, waypoints / Path(name).name)
    data = (args.promod / 'mod.ff').read_bytes()
    if data[:12] != b'IWffu100\x05\x00\x00\x00':
        raise SystemExit('Unsupported installed fastfile')
    data = zlib.decompress(data[12:])
    maps = []
    for match in re.finditer(rb'\xff{4}(.{4})\xff{4}(maps/mp/mp_[a-z0-9_]+\.gsc)\x00', data, re.S):
        length = struct.unpack('<I', match[1])[0]
        script = data[match.end():match.end() + length].decode()
        if length > 100000 or data[match.end() + length] != 0:
            raise SystemExit('Unsupported rawfile layout')
        if not script.startswith('main(){'):
            raise SystemExit('Unsupported installed map initialization: ' + match[2].decode())
        output = mod / (match[2].decode()[:-4] + '.gsx')
        output.parent.mkdir(parents=True, exist_ok=True)
        wrapper = '// Local server overlay, 2026-10-25. Installed map initialization retained.\n'
        wrapper += 'main(){promod_original_map_main(); level thread maps\\mp\\bots\\promod_ai::init();}\n'
        wrapper += script.replace('main(){', 'promod_original_map_main(){', 1) + '\n'
        output.write_text(wrapper)
        maps.append(output.stem)
    manifest = {'maps': maps, 'binary_sha256': digest(destination / 'cod4x18_dedrun'),
                'admin_rules_overlay': args.admin_rules,
                'ai_source_sha256': digest(ROOT / 'bots/promod_ai.gsc'),
                'dependency_lock_sha256': digest(ROOT / 'bots/dependencies.json'),
                'promod': lock['promod']['files'], 'headers': lock['integrity_headers']}
    (destination / 'inputs.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'runtime': str(destination), 'map_overlays': len(maps)}, indent=2))


if __name__ == '__main__':
    main()
