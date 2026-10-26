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

ROOT = Path(__file__).resolve().parents[2]


def source_block(source, pattern):
    match = re.search(pattern + r'\s*\{', source, re.M)
    if not match:
        raise ValueError('Unexpected pinned Bot Warfare source: ' + pattern)
    end, depth = match.end(), 1
    while depth and end < len(source):
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    if depth:
        raise ValueError('Truncated pinned Bot Warfare source')
    return source[match.start():end]


def difficulty_source(internal, script):
    added = source_block(internal, r'^added\(\)')
    defaults = '\n'.join(line.strip() for line in added.splitlines()
                         if re.match(r'\s*self\.pers\[ "bots" \]\[ "(?:skill|behavior)" \]', line))
    profile = source_block(source_block(script, r'^difficulty\(\)'),
                           r'switch \( self\.pers\[ "bots" \]\[ "skill" \]\[ "base" \] \)')
    selection = source_block(script, r'^set_diff\(\)')
    selection = selection.replace('getdvarint( "bots_skill" )', 'getdvarint( "bot_skill" )')
    return ('// Derived locally from pinned Bot Warfare; original profile values unchanged.\n'
            '// Attribution and permission: docs/third-party-bots.md.\n'
            '#include maps\\mp\\bots\\_bot_utility;\n' + selection + '\n'
            'apply_profile() {\n' + profile + '\n}\n'
            'reset_profile() {\n' + defaults + '\n}\n')


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def rawfile(data, name):
    marker = b'\xff' * 4 + name.encode() + b'\x00'
    start = data.find(marker)
    if start < 8 or data.find(marker, start + 1) != -1:
        raise ValueError('Missing or ambiguous installed rawfile: ' + name)
    length = struct.unpack('<I', data[start - 4:start])[0]
    start += len(marker)
    if length > 100000 or start + length >= len(data) or data[start + length] != 0:
        raise ValueError('Unsupported rawfile layout: ' + name)
    return data[start:start + length].decode()


def punkbuster_policy(source):
    # Preserve every other warning/check; never report PB enabled when it is not.
    condition = 'if(!getDvarInt("sv_punkbuster")&&!game["LAN_MODE"]&&!game["PROMOD_PB_OFF"])'
    if source.count(condition) != 1:
        raise ValueError('Unexpected installed PunkBuster warning condition')
    return source.replace(condition, condition[:-1] + '&&!getDvarInt("promod_allow_no_punkbuster"))')


def map_vote_policy(source):
    # Only the startup voting prohibition changes; match rules stay intact.
    restriction = 'setDvar("g_allowVote",0);'
    if source.count(restriction) != 1:
        raise ValueError('Unexpected installed Promod voting restriction')
    return source.replace(restriction, '')


def replace_once(source, old, new):
    if source.count(old) != 1:
        raise ValueError('Unexpected installed Promod gameplay policy: ' + old)
    return source.replace(old, new)


def human_class_limits(source):
    # Reservation and UI use the same current human choices, not stale spawn classes.
    source = replace_once(source,
        'if(isDefined(self.pers["class"])&&self.pers["class"]==classType)return true;',
        'if(self.isbot)return getDvarInt("class_"+classType+"_limit")>0;')
    source = replace_once(source,
        'if(level.players[i].team==teamName&&isDefined(level.players[i].class)&&level.players[i].class==classType)',
        'if(level.players[i]!=self&&!level.players[i].isbot&&isDefined(level.players[i].pers["team"])&&level.players[i].pers["team"]==teamName&&isDefined(level.players[i].pers["class"])&&level.players[i].pers["class"]==classType)')
    for cls in ('assault', 'specops', 'demolitions', 'sniper'):
        source = replace_once(source,
            f'if(player.team==teamName&&isDefined(player.class)&&player.class=="{cls}")',
            f'if(!player.isbot&&isDefined(player.pers["team"])&&player.pers["team"]==teamName&&isDefined(player.pers["class"])&&player.pers["class"]=="{cls}")')
    return replace_once(source, 'idef=!isDefined(self.pers["class"]);',
        'if(!self verifyClassChoice(self.pers["team"],classType))return;idef=!isDefined(self.pers["class"]);')


def match_end_rotation(source):
    # Only the terminal match restart changes; ordinary S&D round restarts remain.
    return replace_once(source,
        'if(isDefined(game["PROMOD_MATCH_MODE"])&&game["PROMOD_MATCH_MODE"]=="match"){map_restart(false);return;}exitLevel(false);',
        'if(isDefined(game["PROMOD_MATCH_MODE"])&&game["PROMOD_MATCH_MODE"]=="match"&&!getDvarInt("promod_auto_maprotate")){map_restart(false);return;}exitLevel(false);')


def bot_readyup(source):
    # Keep the original human input/HUD/recording paths. Evaluate bot eligibility
    # in the original Ready Up loop, including late joins and team changes.
    source = replace_once(source, 'player thread selfLoop();',
                          'if(!player.isbot)player thread selfLoop();')
    return replace_once(source, 'player.oldready=player.update;',
        'if(player.isbot){'
        'player.ready=isDefined(player.pers["team"])&&'
        '(player.pers["team"]=="allies"||player.pers["team"]=="axis")&&'
        'isDefined(player.pers["class"]);'
        'player.update=player.ready;'
        'if(!player.ready){level.not_ready_count++;all_players_ready=false;}'
        'continue;}'
        'player.oldready=player.update;')


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
    parser.add_argument('--allow-no-punkbuster', action='store_true',
                        help='Generate an opt-in PB-warning policy overlay; does not enable/disable PB')
    parser.add_argument('--allow-map-voting', action='store_true',
                        help='Let native g_allowVote configuration survive Promod competition setup')
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
    difficulty = difficulty_source(internal, (vendor / 'maps/mp/bots/_bot_script.gsc').read_text())
    (target / 'difficulty.gsc').write_text(difficulty)
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
    policy = mod / 'promod/servercheck.gsx'
    if args.allow_no_punkbuster:
        script = punkbuster_policy(rawfile(data, 'promod/servercheck.gsc'))
        policy.parent.mkdir(exist_ok=True)
        policy.write_text('// Private derived Promod overlay; original checks retained. See docs/punkbuster.md.\n' + script)
    elif policy.exists():
        # Repreparing without the option restores the installed servercheck.
        policy.unlink()
    vote_policy = mod / 'promod/comp.gsx'
    if args.allow_map_voting:
        script = map_vote_policy(rawfile(data, 'promod/comp.gsc'))
        vote_policy.parent.mkdir(exist_ok=True)
        vote_policy.write_text('// Private derived overlay; see docs/map-voting.md.\n' + script)
    elif vote_policy.exists():
        vote_policy.unlink()
    for name, transform in [('maps/mp/gametypes/_promod', human_class_limits),
                            ('maps/mp/gametypes/_globallogic', match_end_rotation),
                            ('promod/readyup', bot_readyup)]:
        output = mod / (name + '.gsx')
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text('// Private derived gameplay correction; original rules retained.\n' +
                          transform(rawfile(data, name + '.gsc')))
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
                'punkbuster_warning_policy_overlay': args.allow_no_punkbuster,
                'map_voting_policy_overlay': args.allow_map_voting,
                'human_class_limits_overlay': True,
                'match_end_rotation_overlay': True,
                'bot_readyup_overlay': True,
                'ai_source_sha256': digest(ROOT / 'bots/promod_ai.gsc'),
                'dependency_lock_sha256': digest(ROOT / 'bots/dependencies.json'),
                'promod': lock['promod']['files'], 'headers': lock['integrity_headers']}
    (destination / 'inputs.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'runtime': str(destination), 'map_overlays': len(maps)}, indent=2))


if __name__ == '__main__':
    main()
