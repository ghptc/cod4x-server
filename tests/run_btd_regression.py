#!/usr/bin/env python3
"""Private disposable native-VM reproduction; never modifies input runtimes.
Synthetic clients are not proof of graphical client gameplay qualification.
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
p = argparse.ArgumentParser(description=__doc__)
for name in ('runtime', 'game', 'binary'):
    p.add_argument('--' + name, required=True, type=Path)
p.add_argument('--fixed', action='store_true')
p.add_argument('--scenario', choices=('expression', 'death', 'lifecycle'), required=True)
a = p.parse_args()
assert (a.runtime / '.bot-test-runtime').is_file()
spec = importlib.util.spec_from_file_location('btd', ROOT / 'tools/btd/prepare.py')
btd = importlib.util.module_from_spec(spec); spec.loader.exec_module(btd)
home = Path(tempfile.mkdtemp(prefix='btd-death-regression-'))
for name in ('mods', 'integrity'):
    shutil.copytree(a.runtime / name, home / name)
for name in ('main', 'zone'):
    (home / name).symlink_to((a.game / name).resolve(), target_is_directory=True)
shutil.copy2(a.binary, home / 'cod4x18_dedrun')
mod = home / 'mods/btd_alpha_001'
lock = json.loads((ROOT / 'tools/btd/dependencies.json').read_text())
ff = mod / 'mod.ff'
assert hashlib.sha256(ff.read_bytes()).hexdigest() == lock['files']['btd_alpha_001/mod.ff']
source = btd.death_overlay(ff.read_bytes(), lock['death_callback_source_sha256']).decode()
if not a.fixed:
    source = source.replace(btd.SAFE_DEATH_CONDITION, btd.DEATH_CONDITION)
source = source.replace('init()\r\n{', 'init()\r\n{\r\n thread btd_regression::main();', 1)
assert 'thread btd_regression::main();' in source
out = mod / 'maps/mp/gametypes/_globallogic.gsx'
out.parent.mkdir(parents=True, exist_ok=True); out.write_bytes(source.encode())
fixture = (ROOT / 'tests/btd_regression.gsc').read_text()
condition = btd.SAFE_DEATH_CONDITION if a.fixed else btd.DEATH_CONDITION
fixture = fixture.replace('BTD_TEST_CONDITION', condition.replace('eInflictor', 'fixture'))
(mod / 'btd_regression.gsc').write_text(fixture)
if a.scenario == 'lifecycle':
    with (mod/'canonical-mode.cfg').open('a') as cfg:
        cfg.write('\nset btd_grace_time "10"\nset btd_wave_settings "2"\nset btd_start_zoms "5"\n')
with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
    s.bind(('127.0.0.1', 0)); port = s.getsockname()[1]
cmd = [str(home / 'cod4x18_dedrun'), '+set', 'dedicated', '1', '+set', 'net_ip', '127.0.0.1',
       '+set', 'net_port', str(port), '+set', 'fs_basepath', str(home), '+set', 'fs_homepath', str(home/'persistent'),
       '+set', 'fs_game', 'mods/btd_alpha_001', '+set', 'sv_autoupdate', '0', '+set', 'developer', '1', '+set', 'developer_script', '1',
       '+set', 'fs_localizedHeadersPath', str(home/'integrity'), '+set', 'sv_maxclients', '12',
       '+set', 'btd_test_scenario', a.scenario, '+exec', 'canonical-shared.cfg',
       '+exec', 'canonical-mode.cfg', '+map', 'mp_crash']
logpath = home/'console.log'
with logpath.open('w') as log:
    proc = subprocess.Popen(cmd, cwd=home, stdin=subprocess.PIPE, stdout=log, stderr=subprocess.STDOUT)
    try:
        until = time.monotonic() + (130 if a.scenario == 'lifecycle' else 35)
        while time.monotonic() < until and proc.poll() is None:
            time.sleep(.25)
            text = re.sub(r'\^[0-9]', '', logpath.read_text(errors='replace'))
            if 'script runtime error' in text or 'script compile error' in text: break
            proc.stdin.write(b'btd_test_result\nbtd_test_respawn\nbtd_test_zombie_spawn\nbtd_test_wave\n'); proc.stdin.flush()
            success = {'expression': 'expression_pass', 'death': 'death_callback_survived', 'lifecycle': 'lifecycle_pass'}[a.scenario]
            if '"'+success+'"' in text or re.search(r'"(?:spawn|respawn|zombie_spawn|wave)_failed"', text): break
    finally:
        if proc.poll() is None:
            proc.stdin.write(b'quit\n'); proc.stdin.flush()
        try: proc.wait(timeout=8)
        except subprocess.TimeoutExpired: proc.kill(); proc.wait()
text = re.sub(r'\^[0-9]', '', logpath.read_text(errors='replace'))
error = bool(re.search(r'script (?:runtime|compile) error', text))
result = {'evidence': str(home), 'scenario': a.scenario, 'fixed': a.fixed,
          'runtime_error': error, 'gameplay_qualified': False,
          'expression_pass': '"expression_pass"' in text,
          'death_callback_survived': '"death_callback_survived"' in text,
          'spawn_failed': '"spawn_failed"' in text,
          'respawn_pass': '"btd_test_respawn" is: "passed"' in text,
          'zombie_spawn_pass': '"btd_test_zombie_spawn" is: "passed"' in text,
          'wave_pass': '"btd_test_wave" is: "passed"' in text,
          'lifecycle_pass': '"lifecycle_pass"' in text}
(home/'results.json').write_text(json.dumps(result, indent=2)+'\n')
print(json.dumps(result, indent=2))
expected = result[{'expression':'expression_pass','death':'death_callback_survived','lifecycle':'lifecycle_pass'}[a.scenario]]
if a.fixed: assert not error and expected, 'Fixed regression failed: '+str(home)
else: assert error and "has unmatching types 'undefined' and 'string'" in text, 'Expected failure not reproduced: '+str(home)
