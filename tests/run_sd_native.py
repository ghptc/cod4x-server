#!/usr/bin/env python3
"""Native interaction evidence in a NEW loopback-only disposable process.
Fixture positioning is not bot navigation or real-client qualification.
"""
import argparse
import json
import hashlib
from pathlib import Path
import re
import secrets
import shutil
import socket
import subprocess
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--runtime', required=True, type=Path)
p.add_argument('--game', required=True, type=Path)
p.add_argument('--names', required=True, type=Path)
p.add_argument('--scenario', choices=('native', 'navigation'), default='native')
p.add_argument('--map', default='mp_crash')
a = p.parse_args()
assert a.map in json.loads((a.runtime / 'inputs.json').read_text())['maps']
assert (a.runtime / '.bot-test-runtime').is_file()
home = Path(tempfile.mkdtemp(prefix='cod4x-sd-native-'))
for name in ('mods', 'integrity'):
    shutil.copytree(a.runtime / name, home / name)
for name in ('main', 'zone'):
    (home / name).symlink_to((a.game / name).resolve(), target_is_directory=True)
shutil.copy2(ROOT / 'bin/cod4x18_dedrun', home / 'cod4x18_dedrun')
(home / 'scriptdata').mkdir()
shutil.copy2(a.names, home / 'scriptdata/botnames.txt')
mod = home / 'mods/pml220'
lock = json.loads((ROOT / 'bots/dependencies.json').read_text())
for directory, expected in [(mod, lock['promod']['files']),
                            (home / 'integrity/addiwdheaders', lock['integrity_headers'])]:
    for name, sha in expected.items():
        assert hashlib.sha256((directory / name).read_bytes()).hexdigest() == sha
fixture = 'sd_native' if a.scenario == 'native' else 'sd_navigation'
shutil.copy2(ROOT / ('tests/' + fixture + '.gsc'), mod / ('maps/mp/bots/' + fixture + '.gsc'))
for wrapper in (mod / 'maps/mp').glob('mp_*.gsx'):
    wrapper.write_text(wrapper.read_text().replace('main(){',
        'main(){level thread maps\\mp\\bots\\' + fixture + '::init();', 1))
password = secrets.token_hex(20)
(mod / 'qualification.cfg').write_text(f'''set rcon_password "{password}"
set promod_mode "custom_public"
set promod_allow_no_punkbuster "1"
set bot_enable "1"
set bot_use_names "1"
set bot_sd_objectives "{int(a.scenario == "navigation")}"
set bot_debug "1"
set sv_mapRotation "gametype sd map {a.map}"
''')
with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as channel:
    channel.bind(('127.0.0.1', 0)); port = channel.getsockname()[1]
output = (home / 'console.log').open('w')
cmd = [str(home / 'cod4x18_dedrun'), '+set', 'dedicated', '1',  '+set', 'net_ip', '127.0.0.1',
       '+set', 'net_port', str(port), '+set', 'fs_homepath', str(home), '+set', 'fs_basepath', str(home),
       '+set', 'fs_game', 'mods/pml220', '+set', 'sv_pure', '1', '+set', 'sv_maxclients', '12',
       '+set', 'fs_localizedHeadersPath', str(home / 'integrity'), '+exec', 'qualification.cfg', '+map_rotate']
proc = subprocess.Popen(cmd, cwd=home, stdin=subprocess.PIPE, stdout=output, stderr=subprocess.STDOUT)
result = {'map': a.map, 'scenario': a.scenario, 'fixture_positioning': a.scenario == 'native', 'real_client_qualified': False}
def rcon(command):
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as channel:
        channel.settimeout(2)
        channel.sendto(b'\xff' * 4 + f'rcon {password} {command}'.encode(), ('127.0.0.1', port))
        packets = [channel.recv(65535)]
        channel.settimeout(.1)
        while True:
            try: packets.append(channel.recv(65535))
            except TimeoutError: break
        return re.sub(r'\^[0-9]', '', b''.join(packets).decode(errors='replace'))
try:
    deadline = time.monotonic() + (65 if a.scenario == "native" else 240)
    while time.monotonic() < deadline:
        if proc.poll() is not None: raise AssertionError('engine exited')
        try:
            value = rcon('sd_test_result') if a.scenario == 'native' else rcon('sd_navigation_defuses')
            if a.scenario == 'navigation' and re.search(r' is: "[1-9][0-9]*"', value): break
        except TimeoutError: value = ''
        if '"passed"' in value: break
        if re.search(r'"(?:missing_|pickup_failed|plant_interrupt_failed|defuse_interrupt_failed|death_drop_failed|defuse_death_failed|native_).*"', value):
            raise AssertionError(value + rcon('sd_test_debug'))
        time.sleep(.5)
    else: raise AssertionError('fixture timeout')
    for key in (() if a.scenario == 'navigation' else ('pickup', 'plant_interrupted', 'planted', 'defuse_interrupted', 'death_drop', 'defuse_death', 'plant_elapsed', 'defuse_elapsed')):
        value = rcon('sd_test_' + key)
        found = re.search(r' is: "(\d+)"', value)
        assert found, value
        result[key] = int(found[1])
    result['pure'] = '"1"' in rcon('sv_pure')
    assert result['pure'], 'purity lost'
    result['status'] = rcon('status')
    names = a.names.read_text().splitlines()
    active_names = [name for name in names if name in result['status']]
    assert len(active_names) == 12, 'requested active names missing'
    result['requested_names'] = active_names
    if a.scenario == 'native':
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            if ' is: "2"' in rcon('sd_test_rounds'): break
            time.sleep(.2)
        else: raise AssertionError('native next round did not start')
        assert ' is: "1"' in rcon('sd_test_round_reset')
        after = rcon('status')
        assert all(name in after for name in active_names), 'names changed across round'
        result['round_reset_and_names_preserved'] = True
    result['passed'] = True
finally:
    if proc.poll() is None:
        proc.stdin.write(b'quit\n'); proc.stdin.flush()
        try: proc.wait(timeout=8)
        except subprocess.TimeoutExpired: proc.kill(); proc.wait()
    output.close()
    (home / 'results.json').write_text(json.dumps(result, indent=2) + '\n')
    print(home, flush=True)
