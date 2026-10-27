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


def raw_source(fastfile, name, expected, encoding='utf-8'):
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
    return raw.decode(encoding)


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


NAVIGATION_SCRIPT = 'svr/pezbot.gsc'
NAVIGATION_END_CHECK = '    if(!isDefined(string) || string == "" || string == "end")'
# The pinned Killhouse table contains 101 valid nodes, then the marker "end ".
# Keep all node coordinates, connectivity and the other map loaders unchanged.
KILLHOUSE_TERMINATOR_REPAIR = (
    '    // Modified 2026-10-27: repair only the pinned Killhouse terminator.\r\n'
    '    if(getdvar("mapname") == "mp_killhouse" && iLineOffset == 4827 &&\r\n'
    '       compiledFilename == "waypoints/PeZBOT_WP_4.csv" &&\r\n'
    '       level.waypointCount == 101 && string == "end ")\r\n'
    '        string = "end";\r\n\r\n')


def navigation_overlay(fastfile, expected):
    # Latin-1 is a reversible byte mapping: this vendor file has CP1252 comments.
    # Inserting ASCII must not recode or discard the original source bytes.
    source = raw_source(fastfile, NAVIGATION_SCRIPT, expected, encoding='latin-1')
    if source.count(NAVIGATION_END_CHECK) != 1:
        raise ValueError('Unexpected BTD waypoint termination check')
    return source.replace(NAVIGATION_END_CHECK,
                          KILLHOUSE_TERMINATOR_REPAIR + NAVIGATION_END_CHECK).encode('latin-1')


ALLIED_SURVIVAL_SCRIPT = 'btd_gametypes/survival/_survival_logic.gsc'
ALLIED_ZOMBIE_SCRIPT = 'k3/_zombie.gsc'
ALLIED_AMMO_SCRIPT = 'btd_general/_ammo_drops.gsc'
# Existing vendor protection is unconditional, independent of friendly-fire cvars.
PLAYER_DAMAGE_GUARD = 'if(isPlayer(eAttacker) && eAttacker != self)\r\n\t\treturn;'
AMMO_PICKUP_GUARD = '\t\tif(player.isammoing)\r\n\t\t\tcontinue;'
AMMO_FIRST_USE = '\r\n\t\tif (!isdefined(player.hasntfullammo)) player.hasntfullammo = true;'


def replace_exact(source, old, new, count=1):
    if source.count(old) != count:
        raise ValueError('Unexpected pinned BTD allied integration anchor: ' + old)
    return source.replace(old, new)


def allied_overlays(fastfile, lock):
    """Private vendor derivatives; original source bytes preserved except guarded edits."""
    global_source = death_overlay(fastfile, lock['death_callback_source_sha256']).decode('utf-8')
    if global_source.count(PLAYER_DAMAGE_GUARD) != 1:
        raise ValueError('Missing pinned BTD player damage protection')
    global_source = replace_exact(global_source, 'init()\r\n{',
        'init()\r\n{\r\n thread btd_allies::init();')
    # Native registration precedes threaded connected listeners. Identify only
    # actual native bots before the vendor profile-integrity check can run.
    global_source = replace_exact(global_source, 'Callback_PlayerConnect()\r\n{',
        'Callback_PlayerConnect()\r\n{\r\n if (self.isbot) self.pers["isBot"] = true;')
    # Vendor spawn waits outside its disconnect endon while a wave blocks joins.
    # Arm cancellation before that wait so kicking a dead ally cannot resume it.
    global_source = replace_exact(global_source, 'spawnPlayer()\r\n{',
        'spawnPlayer()\r\n{\r\n self endon("disconnect");')
    # Stock game-event survival accounting must also exclude native clients.
    begin = global_source.index('updateTeamStatus()\r\n{')
    end = global_source.index('\r\nisValidClass(', begin)
    block = global_source[begin:end]
    block = replace_exact(block, 'players = level.players;', 'players = btd_allies::human_players();')
    global_source = global_source[:begin] + block + global_source[end:]
    survival = raw_source(fastfile, ALLIED_SURVIVAL_SCRIPT,
                          lock['allied_survival_source_sha256'])
    survival = replace_exact(survival, 'getentarray("player","classname")',
                             'btd_allies::human_players()', count=4)
    zombie = raw_source(fastfile, ALLIED_ZOMBIE_SCRIPT,
                        lock['allied_zombie_source_sha256'])
    # Only the elimination monitor changes; targeting/damage/spawning remain vendor-owned.
    begin = zombie.index('monitorplayers()\r\n{')
    end = zombie.index('\r\nmonitorme()', begin)
    block = replace_exact(zombie[begin:end], 'getentarray("player","classname")',
                          'btd_allies::human_players()')
    zombie = zombie[:begin] + block + zombie[end:]
    ammo = raw_source(fastfile, ALLIED_AMMO_SCRIPT, lock['allied_ammo_source_sha256'])
    # Missing initial eligibility crashed the first pickup for any survivor.
    # Preserve a defined false cooldown; only vendor pickup logic grants ammo.
    ammo = replace_exact(ammo, AMMO_PICKUP_GUARD, AMMO_PICKUP_GUARD + AMMO_FIRST_USE)
    # The vendor cooldowns resume after a wait and touch the player entity.
    # Cancel both on disconnect so human reconnect and ally eviction are safe.
    for function in ('ammoingwait', 'hashadammo'):
        ammo = replace_exact(ammo, function + '()\r\n{',
                             function + '()\r\n{\r\n self endon("disconnect");')
    return {SCRIPT.replace('.gsc', '.gsx'): global_source.encode(),
            ALLIED_SURVIVAL_SCRIPT.replace('.gsc', '.gsx'): survival.encode(),
            ALLIED_ZOMBIE_SCRIPT.replace('.gsc', '.gsx'): zombie.encode(),
            ALLIED_AMMO_SCRIPT.replace('.gsc', '.gsx'): ammo.encode(),
            'btd_allies.gsx': (ROOT / 'bots/btd_allies.gsc').read_bytes()}


def prepare(source, headers, binary, output, allies=False):
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
    navigation = navigation_overlay((source / 'btd_alpha_001/mod.ff').read_bytes(),
                                    lock['navigation_source_sha256'])
    extra_overlays = allied_overlays((source / 'btd_alpha_001/mod.ff').read_bytes(), lock) if allies else {}
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
    navigation_path = mod / NAVIGATION_SCRIPT.replace('.gsc', '.gsx')
    navigation_path.parent.mkdir(parents=True, exist_ok=True)
    navigation_path.write_bytes(navigation)
    for name, data in extra_overlays.items():
        target = mod / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
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
    # The pinned navigation overlay above repairs Killhouse's terminal marker.
    # Advertise it only after verified preparation; retain vendor map order/bytes.
    maps = re.findall(r'\bmap (mp_[a-z0-9_]+)', rotation)
    if 'mp_killhouse' not in maps:
        maps.append('mp_killhouse')
    record = {'asset_type': 'btd-alpha-001', 'fs_game': 'mods/btd_alpha_001',
              'maps': maps,
              'binary_sha256': binary_hash, 'headers': header_lock,
              'assets': {Path(k).name: v for k, v in lock['files'].items()
                         if k.startswith('btd_alpha_001/') and Path(k).name != 'server.cfg'},
              'default_cfgs': lock['default_cfgs'],
              'overlays': {str(patched.relative_to(mod)): digest(patched),
                           str(spawn_path.relative_to(mod)): digest(spawn_path),
                           str(navigation_path.relative_to(mod)): digest(navigation_path)},
              'death_callback_source_sha256': lock['death_callback_source_sha256'],
              'spawn_points_source_sha256': lock['spawn_points_source_sha256'],
              'navigation_source_sha256': lock['navigation_source_sha256'],
              'dependency_lock_sha256': digest(ROOT / 'tools/btd/dependencies.json'),
              'qualification': 'original package maps plus repaired Killhouse; gameplay qualification is separate'}
    if allies:
        record['overlays'].update({name: digest(mod / name) for name in extra_overlays})
        record['allied_survival_source_sha256'] = lock['allied_survival_source_sha256']
        record['allied_zombie_source_sha256'] = lock['allied_zombie_source_sha256']
        record['allied_ammo_source_sha256'] = lock['allied_ammo_source_sha256']
        record['allied_bots'] = True
        record['qualification'] = 'experimental native allied integration; operator gameplay qualification required'
    (output / 'inputs.json').write_text(json.dumps(record, indent=2) + '\n')
    return record


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('source', 'headers', 'binary', 'output'):
        parser.add_argument('--' + name, required=True, type=Path)
    parser.add_argument('--allies', action='store_true', help='Opt in to five native allied soldiers; requires compatible packaging')
    args = parser.parse_args()
    try:
        record = prepare(args.source, args.headers, args.binary, args.output, args.allies)
    except (OSError, ValueError) as exc:
        parser.exit(1, f'BTD preparation failed: {exc}\n')
    print(json.dumps({'runtime': str(args.output), 'maps': record['maps']}, indent=2))
