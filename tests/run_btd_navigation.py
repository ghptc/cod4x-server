#!/usr/bin/env python3
"""Private native BTD navigation qualification; never touches an existing runtime.

Synthetic clients and authored-node collision traces do not replace graphical
operator-supervised qualification. Original assets and all full logs stay private.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import shutil
import socket
import subprocess
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
RUNNER_SHA256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
parser = argparse.ArgumentParser(description=__doc__)
for name in ('runtime', 'game', 'binary'):
    parser.add_argument('--' + name, required=True, type=Path)
parser.add_argument('--original-waypoints', action='store_true',
                    help='Remove only the generated PeZBOT overlay in the disposable copy')
parser.add_argument('--expect-waypoint-defect', action='store_true',
                    help='Require the original exact Killhouse undefined-coordinate error')
a = parser.parse_args()
if a.expect_waypoint_defect and not a.original_waypoints:
    parser.error('--expect-waypoint-defect requires --original-waypoints')
assert (a.runtime / '.bot-test-runtime').is_file()
spec = importlib.util.spec_from_file_location('btd_navigation_prepare', ROOT / 'tools/btd/prepare.py')
btd = importlib.util.module_from_spec(spec)
spec.loader.exec_module(btd)
home = Path(tempfile.mkdtemp(prefix='btd-navigation-'))
for name in ('mods', 'integrity'):
    shutil.copytree(a.runtime / name, home / name)
for name in ('main', 'zone'):
    (home / name).symlink_to((a.game / name).resolve(), target_is_directory=True)
shutil.copy2(a.binary, home / 'cod4x18_dedrun')
mod = home / 'mods/btd_alpha_001'
lock = json.loads((ROOT / 'tools/btd/dependencies.json').read_text())
fastfile = mod / 'mod.ff'
assert hashlib.sha256(fastfile.read_bytes()).hexdigest() == lock['files']['btd_alpha_001/mod.ff']
source = btd.death_overlay(fastfile.read_bytes(), lock['death_callback_source_sha256']).decode()
source = source.replace('init()\r\n{', 'init()\r\n{\r\n thread btd_navigation::main();', 1)
assert 'thread btd_navigation::main();' in source
out = mod / btd.SCRIPT.replace('.gsc', '.gsx')
out.parent.mkdir(parents=True, exist_ok=True)
out.write_bytes(source.encode())
spawn = mod / btd.SPAWN_SCRIPT.replace('.gsc', '.gsx')
spawn.parent.mkdir(parents=True, exist_ok=True)
spawn.write_bytes(btd.spawn_overlay(fastfile.read_bytes(), lock['spawn_points_source_sha256']))
nav_overlay = mod / 'svr/pezbot.gsx'
if a.original_waypoints:
    if nav_overlay.exists():
        nav_overlay.unlink()
else:
    assert nav_overlay.is_file(), 'A prepared, pinned PeZBOT navigation overlay is required'
    expected = btd.navigation_overlay(fastfile.read_bytes(), lock['navigation_source_sha256'])
    assert nav_overlay.read_bytes() == expected, 'Prepared PeZBOT overlay does not match pinned preparation'
shutil.copy2(ROOT / 'tests/btd_navigation.gsc', mod / 'btd_navigation.gsc')
baseline_config_hashes = {name: hashlib.sha256((mod / name).read_bytes()).hexdigest()
                          for name in ('canonical-shared.cfg', 'canonical-mode.cfg')}
manifest = a.runtime / 'inputs.json'
prepared_manifest = json.loads(manifest.read_text()) if manifest.is_file() else None
# Accelerate fixture grace/wave size and disabled camping thresholds. Enemy
# speed, damage and health are unchanged; fixture player health is increased.
with (mod / 'canonical-mode.cfg').open('a') as cfg:
    cfg.write('\nset btd_grace_time "30"\nset btd_wave_settings "2"\nset btd_start_zoms "5"\nset btd_camp_max_time "2"\nset btd_camp_message_time "1"\n')
with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as channel:
    channel.bind(('127.0.0.1', 0))
    port = channel.getsockname()[1]
command = [str(home / 'cod4x18_dedrun'), '+set', 'dedicated', '1', '+set', 'net_ip', '127.0.0.1',
           '+set', 'net_port', str(port), '+set', 'fs_basepath', str(home), '+set', 'fs_homepath', str(home / 'persistent'),
           '+set', 'fs_game', 'mods/btd_alpha_001', '+set', 'sv_autoupdate', '0', '+set', 'developer', '1',
           '+set', 'developer_script', '1', '+set', 'fs_localizedHeadersPath', str(home / 'integrity'),
           '+set', 'sv_maxclients', '12', '+set', 'btd_nav_scenario', 'navigation',
           '+exec', 'canonical-shared.cfg', '+exec', 'canonical-mode.cfg', '+map', 'mp_killhouse']
logpath = home / 'console.log'
checks = {}
measurements = {}

def status():
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as channel:
        channel.settimeout(3)
        channel.sendto(b'\xff' * 4 + b'getstatus\n', ('127.0.0.1', port))
        data = channel.recv(65535)
    assert b'statusResponse' in data
    fields = data.split(b'\n')[1].split(b'\\')
    return dict(zip(fields[1::2], fields[2::2]))

with logpath.open('w') as output:
    proc = subprocess.Popen(command, cwd=home, stdin=subprocess.PIPE, stdout=output, stderr=subprocess.STDOUT)
    def send(value):
        assert proc.poll() is None, 'Native server exited: ' + str(home)
        proc.stdin.write((value + '\n').encode())
        proc.stdin.flush()
    try:
        text = ''
        deadline = time.monotonic() + 300
        while time.monotonic() < deadline and proc.poll() is None:
            time.sleep(.25)
            text = re.sub(r'\^[0-9]', '', logpath.read_text(errors='replace'))
            if re.search(r'script (?:runtime|compile) error', text):
                break
            send('btd_nav_result\nbtd_nav_phase')
            if re.search(r'"btd_nav_result" is: "(?:passed|failed_[^"]+)"', text):
                break
        if not a.expect_waypoint_defect and proc.poll() is None and not re.search(r'script (?:runtime|compile) error', text):
            for key in ('phase', 'respawn', 'camping', 'elevation', 'nodes', 'linked_spawns', 'max_spawn_link', 'blocked_direct_path', 'initial_distance',
                        'displacement', 'closest_distance', 'used_waypoint', 'route_length', 'waypoint_changes',
                        'melee', 'chase', 'bullet_hits', 'bullet_kills', 'wave'):
                send('btd_nav_' + key)
                time.sleep(.03)
        if '"btd_nav_result" is: "passed"' in text and not a.expect_waypoint_defect:
            send('set btd_nav_scenario idle')
            for name in ('mp_crash', 'mp_killhouse'):
                send('map ' + name)
                time.sleep(5)
                values = status()
                checks['transition_' + name] = values.get(b'mapname') == name.encode() and values.get(b'sv_pure') == b'1' and values.get(b'g_gametype') == b'war'
                send('btd_nav_nodes\nbtd_nav_map\nbtd_anticamp')
                time.sleep(.25)
    finally:
        if proc.poll() is None:
            try:
                send('quit')
            except (AssertionError, BrokenPipeError):
                pass  # A fatal native error may finish shutdown after poll().
        try:
            proc.wait(timeout=8)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
text = re.sub(r'\^[0-9]', '', logpath.read_text(errors='replace'))
error = bool(re.search(r'script (?:runtime|compile) error', text))
original_defect = (error and 'cannot cast undefined to string' in text and
                   "file 'svr/pezbot.gsc', line 1928" in text and 'LoadStaticWaypoints();' in text)
checks['original_marker_preserved'] = 'BTD_NAV_MARKER value=[end ] length=4' in text
if a.expect_waypoint_defect:
    checks['expected_original_defect'] = original_defect
else:
    checks['no_script_error'] = not error
    checks['navigation_pass'] = '"btd_nav_result" is: "passed"' in text
    checks['eight_headers'] = 'Loaded 8 administrative IWD checksums' in text
    for name in ('respawn', 'camping', 'blocked_direct_path', 'melee', 'chase', 'wave'):
        checks[name] = f'"btd_nav_{name}" is: "passed"' in text
    for name in ('nodes', 'linked_spawns', 'max_spawn_link', 'elevation', 'initial_distance', 'displacement', 'closest_distance', 'used_waypoint', 'route_length', 'waypoint_changes', 'bullet_hits', 'bullet_kills'):
        matches = re.findall(r'"btd_nav_' + name + r'" is: "([^"]+)"', text)
        measurements[name] = matches[-1] if matches else None
result = {'evidence': str(home), 'checks': checks, 'measurements': measurements,
          'original_waypoints': a.original_waypoints, 'runtime_error': error,
          'gameplay_qualified': False, 'binary_sha256': hashlib.sha256((home / 'cod4x18_dedrun').read_bytes()).hexdigest(),
          'mod_ff_sha256': hashlib.sha256(fastfile.read_bytes()).hexdigest(),
          'navigation_overlay_sha256': hashlib.sha256(nav_overlay.read_bytes()).hexdigest() if nav_overlay.exists() else None,
          'fixture_sha256': hashlib.sha256((mod / 'btd_navigation.gsc').read_bytes()).hexdigest(),
          'runner_sha256': RUNNER_SHA256,
          'baseline_config_sha256': baseline_config_hashes,
          'fixture_config_sha256': {name: hashlib.sha256((mod / name).read_bytes()).hexdigest()
                                    for name in ('canonical-shared.cfg', 'canonical-mode.cfg')},
          'prepared_inputs': prepared_manifest}

(home / 'results.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps(result, indent=2))
assert all(checks.values()), 'Native navigation qualification failed: ' + str(home)
