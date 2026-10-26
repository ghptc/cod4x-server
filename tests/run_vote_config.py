#!/usr/bin/env python3
"""Isolated real engine/Promod voting cvar registration and lifecycle checks.
Requires a freshly prepared private runtime and reviewed catalog/workspace checkouts.
Never operates on an existing runtime or any remote host.
"""
import argparse
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
p = argparse.ArgumentParser()
p.add_argument('--runtime', type=Path, required=True)
p.add_argument('--game', type=Path, required=True)
p.add_argument('--catalog', type=Path, required=True)
p.add_argument('--workspace', type=Path, required=True)
a = p.parse_args()
assert (a.runtime / '.bot-test-runtime').is_file()
def load_script(name):
    spec = importlib.util.spec_from_file_location('qualification_' + name, a.workspace / 'scripts' / (name + '.py'))
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module
runtime_policy = load_script('runtime')
mode_policy = load_script('modes')
fs_game, startup_map, fingerprint, maps_csv, capacity, _ = mode_policy.select(a.catalog, 'promod')
home = Path(tempfile.mkdtemp(prefix='cod4x-vote-config-'))
for name in ('mods', 'integrity'):
    shutil.copytree(a.runtime / name, home / name)
for name in ('main', 'zone'):
    (home / name).symlink_to((a.game / name).resolve(), target_is_directory=True)
shutil.copy2(ROOT / 'bin/cod4x18_dedrun', home / 'cod4x18_dedrun')
mod = home / 'mods/pml220'
shutil.copy2(a.catalog / 'shared/server.cfg', mod / 'canonical-shared.cfg')
shutil.copy2(a.catalog / 'modes/promod/server.cfg', mod / 'canonical-mode.cfg')
with (mod / 'canonical-shared.cfg').open('a') as stream:
    stream.write('\nset promod_allow_no_punkbuster "1"\n')
password = secrets.token_hex(20)
# Obsolete private rules and a nested exec must not win over mode-owned values.
(mod / 'private.cfg').write_text(f'set rcon_password "{password}"\nset sv_wwwBaseURL "http://127.0.0.1/local-fixture"\nexec obsolete.cfg\n')
canonical = (mod / 'canonical-mode.cfg').read_text()
policy = dict(re.findall(r'^set (g_(?:vote\w+|allowVote|oldVoting)) "([^"]+)"', canonical, re.M))
checks = {}
for attempt, configured in enumerate((5, 30, 120, None, -1, 0, 901, 1, 900, 5)):
    # Keep the missing-config case free of a private cooldown as well.
    (mod / 'obsolete.cfg').write_text('set g_allowVote "0"\n' +
        ('' if configured is None else 'set g_voteCooldown "900"\n'))
    cfg = re.sub(r'^set g_voteCooldown .*\n', '', canonical, flags=re.M)
    if configured is not None:
        cfg += f'set g_voteCooldown "{configured}"\n'
    (mod / 'canonical-mode.cfg').write_text(cfg)
    expected = 120 if configured is None else (900 if configured < 1 or configured > 900 else configured)
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as channel:
        channel.bind(('127.0.0.1', 0)); port = channel.getsockname()[1]
    service = {'entrypoint': [runtime_policy.EXECUTABLE],
        'volumes': [{'target': value} for value in ('/home/user/cod4/main', '/home/user/cod4/zone', runtime_policy.PERSISTENT_HOME)],
        'command': ['+set', 'dedicated', '1', '+set', 'net_ip', '127.0.0.1',
            '+set', 'net_port', str(port), '+set', 'fs_homepath', runtime_policy.PERSISTENT_HOME,
            '+set', 'bot_enable', '0', '+exec', 'private.cfg']}
    managed = runtime_policy.adapt(service, 'qualification-only', 'promod', fingerprint,
                                   fs_game, startup_map, maps_csv, capacity)['command']
    cmd = [str(home / 'cod4x18_dedrun')] + [value.replace(runtime_policy.ARTIFACT_ROOT, str(home)).replace(
        runtime_policy.PERSISTENT_HOME, str(home)) for value in managed]
    output = (home / f'console-{attempt}.log').open('w')
    proc = subprocess.Popen(cmd, cwd=home, stdin=subprocess.PIPE, stdout=output, stderr=subprocess.STDOUT)
    def send(command):
        assert proc.poll() is None
        proc.stdin.write((command + '\n').encode()); proc.stdin.flush()
    def value(name):
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as channel:
            channel.settimeout(3)
            channel.sendto(b'\xff' * 4 + f'rcon {password} {name}'.encode(), ('127.0.0.1', port))
            response = re.sub(r'\^[0-9]', '', channel.recv(65535).decode(errors='replace'))
            return re.search('"' + name + r'" is: "([^"]*)"', response)[1]
    try:
        time.sleep(4)
        for phase, command in (('startup', None), ('restart_map', 'map_restart'), ('map', 'map mp_strike')):
            if command:
                send(command); time.sleep(3)
            tag = f'{attempt}_{configured}_{phase}'
            checks[tag] = int(value('g_voteCooldown')) == expected
            checks[tag + '_policy'] = all(value(name) == setting for name, setting in policy.items()
                                          if name != 'g_voteCooldown')
        # Runtime out-of-domain writes reject and retain the current value.
        for invalid in (-1, 0, 901):
            send(f'set g_voteCooldown {invalid}'); time.sleep(.1)
            checks[f'{attempt}_reject_{invalid}'] = int(value('g_voteCooldown')) == expected
        for valid in (5, 30, 120, 1, 900):
            send(f'set g_voteCooldown {valid}'); time.sleep(.1)
            checks[f'{attempt}_update_{valid}'] = int(value('g_voteCooldown')) == valid
        checks[f'{attempt}_pure'] = value('sv_pure') == '1'
    finally:
        if proc.poll() is None: send('quit')
        try: checks[f'{attempt}_exit'] = proc.wait(timeout=10) == 0
        finally:
            if proc.poll() is None: proc.kill(); proc.wait()
            output.close()
    console = (home / f'console-{attempt}.log').read_text(errors='replace')
    checks[f'{attempt}_clean'] = not re.search(r'Sys_Error:|script (?:compile|runtime) error|Segmentation fault', console, re.I)
    checks[f'{attempt}_headers'] = 'Loaded 8 administrative IWD checksums' in console
    print(f'configured={configured} effective={expected}', flush=True)
result = {'evidence': str(home), 'checks': checks,
          'binary_sha256': hashlib.sha256((home / 'cod4x18_dedrun').read_bytes()).hexdigest()}
(home / 'results.json').write_text(json.dumps(result, indent=2))
print(json.dumps({'evidence': str(home), 'passed': sum(checks.values()),
                  'failed': [name for name, passed in checks.items() if not passed]}, indent=2))
assert all(checks.values())
