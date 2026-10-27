#!/usr/bin/env python3
"""Disposable loopback BTD startup/map/RCON preflight checks, without decompilation.
This checks startup compatibility, not native zombie combat or container switching.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import secrets
import shutil
import socket
import subprocess
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
for name in ('runtime', 'game', 'catalog', 'workspace'):
    parser.add_argument('--' + name, required=True, type=Path)
args = parser.parse_args()
assert (args.runtime / '.bot-test-runtime').is_file()

def load(name):
    spec = importlib.util.spec_from_file_location('btd_' + name, args.workspace / 'scripts' / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

modes, runtime = load('modes'), load('runtime')
fs_game, startup, fingerprint, maps, capacity, _ = modes.select(args.catalog, 'zombies')
home = Path(tempfile.mkdtemp(prefix='cod4-btd-qualified-'))
for name in ('mods', 'integrity'):
    shutil.copytree(args.runtime / name, home / name)
for name in ('main', 'zone'):
    (home / name).symlink_to((args.game / name).resolve(), target_is_directory=True)
shutil.copy2(ROOT / 'bin/cod4x18_dedrun', home / 'cod4x18_dedrun')
mod = home / fs_game
assert (mod / 'canonical-shared.cfg').is_file()
assert (mod / 'canonical-mode.cfg').read_bytes() == (args.catalog / 'modes/zombies/server.cfg').read_bytes()
password = secrets.token_hex(16)
(mod / 'private.cfg').write_text(f'set rcon_password "{password}"\nexec obsolete.cfg\n')
(mod / 'obsolete.cfg').write_text('set g_gametype "sd"\nset bot_enable "1"\nset btd_grace_time "900"\n'
    'set btd_anticamp "3"\nset btd_msg2 "obsolete administrator fixture"\n')
checks = {}
for attempt in range(2):
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as channel:
        channel.bind(('127.0.0.1', 0)); port = channel.getsockname()[1]
    service = {'entrypoint': [runtime.EXECUTABLE], 'read_only': True,
        'volumes': [{'target': value} for value in ('/home/user/cod4/main', '/home/user/cod4/zone', runtime.PERSISTENT_HOME)],
        'command': ['+set', 'dedicated', '1', '+set', 'net_ip', '127.0.0.1',
                    '+set', 'net_port', str(port), '+set', 'developer', '1', '+set', 'developer_script', '1', '+set', 'fs_homepath', runtime.PERSISTENT_HOME,
                    '+exec', 'private.cfg']}
    adapted = runtime.adapt(service, 'qualification-only', 'zombies', fingerprint, fs_game, startup, maps, capacity)
    checks[f'{attempt}_readonly_config_retained'] = adapted['read_only'] is True
    command = [str(home / 'cod4x18_dedrun')] + [value.replace(runtime.ARTIFACT_ROOT, str(home)).replace(
        runtime.PERSISTENT_HOME, str(home / 'persistent')) for value in adapted['command']]
    output = (home / f'console-{attempt}.log').open('w')
    proc = subprocess.Popen(command, cwd=home, stdin=subprocess.PIPE, stdout=output, stderr=subprocess.STDOUT)
    def send(command):
        assert proc.poll() is None
        proc.stdin.write((command + '\n').encode()); proc.stdin.flush()
    def rcon(command, credential=password):
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as channel:
            channel.settimeout(4)
            channel.sendto(b'\xff' * 4 + f'rcon {credential} {command}'.encode(), ('127.0.0.1', port))
            return re.sub(r'\^[0-9]', '', channel.recv(65535).decode(errors='replace'))
    def value(name):
        return re.search('"' + name + r'" is: "([^"]*)"', rcon(name))[1]
    try:
        time.sleep(5)
        state = {name: value(name) for name in ('g_gametype', 'bot_enable', 'btd_grace_time', 'sv_pure')}
        print('startup', attempt, state, flush=True)
        checks[f'{attempt}_precedence'] = state == {'g_gametype': 'war', 'bot_enable': '0', 'btd_grace_time': '60', 'sv_pure': '1'}
        checks[f'{attempt}_classic_policy'] = value('btd_anticamp') == '0' and value('btd_msg2') == 'Server admins are pitta'
        checks[f'{attempt}_bad_password'] = 'Bad rcon' in rcon('change_mode zombies', 'invalid-fixture')
        checks[f'{attempt}_status'] = fs_game in rcon('change_mode') and 'targets: none' in rcon('change_mode')
        for requested in ('zombies', 'promod', 'hardcore', 'unknown'):
            checks[f'{attempt}_unavailable_{requested}'] = 'Runtime unchanged' in rcon('change_mode ' + requested)
        for invalid in ('../zombies', 'mods/btd_alpha_001', 'https://example.invalid', 'zombies;quit'):
            checks[f'{attempt}_invalid_{invalid}'] = 'Invalid mode' in rcon('change_mode ' + invalid)
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(rcon, ['change_mode zombies', 'change_mode promod']))
        checks[f'{attempt}_concurrent_denied'] = all('Runtime unchanged' in result for result in results)
        send('set fs_game mods/pml220'); time.sleep(.1)
        checks[f'{attempt}_fs_game_protected'] = value('fs_game') == fs_game
        for mapname in maps.split(',') if attempt == 0 else [startup]:
            send('map ' + mapname); time.sleep(2)
            state = {name: value(name) for name in ('mapname', 'g_gametype', 'sv_pure')}
            print('map', state, flush=True)
            checks[f'{attempt}_{mapname}'] = state == {'mapname': mapname, 'g_gametype': 'war', 'sv_pure': '1'}
            checks[f'{attempt}_{mapname}_classic_policy'] = value('btd_anticamp') == '0' and value('btd_msg2') == 'Server admins are pitta'
        checks[f'{attempt}_credentials_after_maps'] = bool(re.search(r'map\s*:', rcon('status')))
        marker = home / 'persistent' / 'qualification-marker'
        if attempt == 0:
            marker.write_text('persistent fixture')
        else:
            checks['persistent_marker_survives_restart'] = marker.read_text() == 'persistent fixture'
    finally:
        if proc.poll() is None: send('quit')
        try: checks[f'{attempt}_exit'] = proc.wait(timeout=10) == 0
        finally:
            if proc.poll() is None: proc.kill(); proc.wait()
            output.close()
    console = (home / f'console-{attempt}.log').read_text(errors='replace')
    checks[f'{attempt}_clean'] = not re.search(r'Sys_Error:|script (?:compile|runtime) error|Segmentation fault', console, re.I)
    checks[f'{attempt}_headers'] = 'Loaded 8 administrative IWD checksums' in console
result = {'evidence': str(home), 'checks': checks, 'gameplay_qualified': False,
          'binary_sha256': hashlib.sha256((home / 'cod4x18_dedrun').read_bytes()).hexdigest()}
(home / 'results.json').write_text(json.dumps(result, indent=2))
print(json.dumps({'evidence': str(home), 'passed': sum(checks.values()),
                  'failed': [name for name, passed in checks.items() if not passed]}, indent=2))
assert all(checks.values())
