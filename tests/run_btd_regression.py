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
p.add_argument('--artifact-ammo', action='store_true', help='Use packaged ammo bytes unchanged; never synthesize the correction')
p.add_argument('--reproduce-spawn-defect', action='store_true', help='Apply death guard only, expect the native missing-angle failure')
p.add_argument('--scenario', choices=('expression', 'death', 'lifecycle', 'classic', 'ammo'), required=True)
p.add_argument('--classic-control', choices=('timer', 'teleport'),
               help='Negative control: restore one original anti-camping mechanism')
a = p.parse_args()
if a.classic_control and (a.scenario != 'classic' or not a.fixed):
    p.error('--classic-control requires --fixed --scenario classic')
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
if a.fixed and not a.reproduce_spawn_defect:
    spawn = mod / btd.SPAWN_SCRIPT.replace('.gsc', '.gsx')
    spawn.parent.mkdir(parents=True, exist_ok=True)
    spawn.write_bytes(btd.spawn_overlay(ff.read_bytes(), lock['spawn_points_source_sha256']))
if a.scenario == 'ammo' and not a.artifact_ammo:
    ammo = (btd.ammo_overlay(ff.read_bytes(), lock['allied_ammo_source_sha256']) if a.fixed else
            btd.raw_source(ff.read_bytes(), btd.ALLIED_AMMO_SCRIPT, lock['allied_ammo_source_sha256']).encode())
    target = mod / btd.ALLIED_AMMO_SCRIPT.replace('.gsc', '.gsx')
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(ammo)
    shutil.copy2(ROOT / 'tests/btd_ammo.gsc', mod / 'btd_ammo.gsc')
if a.scenario == 'ammo' and a.artifact_ammo:
    shutil.copy2(ROOT / 'tests/btd_ammo.gsc', mod / 'btd_ammo.gsc')
fixture = (ROOT / 'tests/btd_regression.gsc').read_text()
if a.scenario == 'ammo':
    fixture = 'main() { btd_ammo::main(); }\n'
condition = btd.SAFE_DEATH_CONDITION if a.fixed else btd.DEATH_CONDITION
fixture = fixture.replace('BTD_TEST_CONDITION', condition.replace('eInflictor', 'fixture'))
(mod / 'btd_regression.gsc').write_text(fixture)
if a.scenario == 'lifecycle':
    with (mod/'canonical-mode.cfg').open('a') as cfg:
        cfg.write('\nset btd_grace_time "10"\nset btd_wave_settings "2"\nset btd_start_zoms "5"\n')
if a.scenario == 'classic':
    with (mod / 'canonical-mode.cfg').open('a') as cfg:
        cfg.write('\nset btd_camp_max_time "2"\nset btd_camp_message_time "1"\n')
        if a.classic_control:
            cfg.write('set btd_anticamp "' + {'timer': '2', 'teleport': '1'}[a.classic_control] + '"\n')
with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
    s.bind(('127.0.0.1', 0)); port = s.getsockname()[1]
cmd = [str(home / 'cod4x18_dedrun'), '+set', 'dedicated', '1', '+set', 'net_ip', '127.0.0.1',
       '+set', 'net_port', str(port), '+set', 'fs_basepath', str(home), '+set', 'fs_homepath', str(home/'persistent'),
       '+set', 'fs_game', 'mods/btd_alpha_001', '+set', 'sv_autoupdate', '0', '+set', 'developer', '1', '+set', 'developer_script', '1',
       '+set', 'fs_localizedHeadersPath', str(home/'integrity'), '+set', 'sv_maxclients', '12',
       '+set', 'btd_test_scenario', a.scenario, '+exec', 'canonical-shared.cfg',
       '+exec', 'canonical-mode.cfg', '+map', 'mp_crash']
logpath = home/'console.log'
network_checks = {}
def status():
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as channel:
        channel.settimeout(3); channel.sendto(b'\xff'*4+b'getstatus\n',('127.0.0.1',port))
        data=channel.recv(65535)
    assert b'statusResponse' in data
    fields=data.split(b'\n')[1].split(b'\\')
    return dict(zip(fields[1::2],fields[2::2]))

def admit(attempt):
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as channel:
        channel.bind(('127.0.0.2',0));channel.settimeout(3)
        channel.sendto(b'\xff'*4+b'getchallenge 123456',('127.0.0.1',port))
        challenge=channel.recv(2048)[4:].decode().split()[1]
        userinfo=f'connect "\\protocol\\21\\challenge\\{challenge}\\qport\\{24444+attempt}\\name\\ReconnectFixture\\rate\\25000\\snaps\\20"'
        channel.sendto(b'\xff'*4+userinfo.encode(),('127.0.0.1',port))
        assert b'connectResponse' in channel.recv(2048)
    time.sleep(.2)
    text=re.sub(r'\^[0-9]', '', logpath.read_text(errors='replace'))
    slot=re.findall(r'CS_CONNECTED for ReconnectFixture num (\d+)',text)[-1]
    proc.stdin.write(('clientkick '+slot+'\n').encode());proc.stdin.flush()
    time.sleep(2)

with logpath.open('w') as log:
    proc = subprocess.Popen(cmd, cwd=home, stdin=subprocess.PIPE, stdout=log, stderr=subprocess.STDOUT)
    try:
        until = time.monotonic() + (130 if a.scenario == 'lifecycle' else 65 if a.scenario == 'ammo' else 35)
        while time.monotonic() < until and proc.poll() is None:
            time.sleep(.25)
            text = re.sub(r'\^[0-9]', '', logpath.read_text(errors='replace'))
            if 'script runtime error' in text or 'script compile error' in text: break
            proc.stdin.write(b'btd_test_result\nbtd_test_respawn\nbtd_test_zombie_spawn\nbtd_test_wave\n'); proc.stdin.flush()
            success = {'expression': 'expression_pass', 'death': 'death_callback_survived', 'lifecycle': 'lifecycle_pass', 'classic': 'classic_pass', 'ammo': 'ammo_pass'}[a.scenario]
            if '"'+success+'"' in text or re.search(r'"(?:spawn|respawn|zombie_spawn|wave)_failed"|"classic_[a-z_]+(?:failed|enabled)"', text): break
        if a.scenario == 'lifecycle' and '"lifecycle_pass"' in text and not a.reproduce_spawn_defect:
            time.sleep(2)
            for attempt in range(2):
                admit(attempt); network_checks['udp_admission_'+str(attempt)]=True
            proc.stdin.write(b'set btd_test_scenario idle\n');proc.stdin.flush()
            for mapname in ('mp_strike','mp_crash'):
                proc.stdin.write(('map '+mapname+'\n').encode());proc.stdin.flush()
                time.sleep(3)
                values=status()
                assert values[b'mapname']==mapname.encode() and values[b'fs_game']==b'mods/btd_alpha_001' and values[b'g_gametype']==b'war' and values[b'sv_pure']==b'1'
                network_checks['map_'+mapname]=True
        if a.scenario == 'ammo':
            network_checks['process_alive_after_scenario'] = proc.poll() is None
            try:
                values = status()
                network_checks['udp_available_after_scenario'] = values.get(b'sv_pure') == b'1'
            except socket.timeout:
                network_checks['udp_available_after_scenario'] = False
    finally:
        if proc.poll() is None:
            proc.stdin.write(b'quit\n'); proc.stdin.flush()
        try: proc.wait(timeout=8)
        except subprocess.TimeoutExpired: proc.kill(); proc.wait()
text = re.sub(r'\^[0-9]', '', logpath.read_text(errors='replace'))
error = bool(re.search(r'script (?:runtime|compile) error', text))
result = {'evidence': str(home), 'scenario': a.scenario, 'fixed': a.fixed, 'artifact_ammo': a.artifact_ammo, 'input_binary_sha256': hashlib.sha256(a.binary.read_bytes()).hexdigest(), 'input_fastfile_sha256': hashlib.sha256(ff.read_bytes()).hexdigest(),
          'runtime_error': error, 'gameplay_qualified': False, 'network_checks': network_checks,
          'expression_pass': '"expression_pass"' in text,
          'death_callback_survived': '"death_callback_survived"' in text,
          'spawn_failed': '"spawn_failed"' in text,
          'respawn_pass': '"btd_test_respawn" is: "passed"' in text,
          'zombie_spawn_pass': '"btd_test_zombie_spawn" is: "passed"' in text,
          'wave_pass': '"btd_test_wave" is: "passed"' in text,
          'classic_pass': '"classic_pass"' in text,
          'classic_control': a.classic_control,
          'classic_control_detected': bool(a.classic_control and '"classic_'+a.classic_control+'_enabled"' in text),
          'lifecycle_pass': '"lifecycle_pass"' in text, 'ammo_pass': '"ammo_pass"' in text}
(home/'results.json').write_text(json.dumps(result, indent=2)+'\n')
print(json.dumps(result, indent=2))
expected = result[{'expression':'expression_pass','death':'death_callback_survived','lifecycle':'lifecycle_pass','classic':'classic_pass','ammo':'ammo_pass'}[a.scenario]]
if a.classic_control:
    assert not error and result['classic_control_detected'], 'Negative control not detected: '+str(home)
elif a.reproduce_spawn_defect:
    assert error and 'type undefined is not a vector' in text, 'Spawn defect not reproduced: '+str(home)
elif a.scenario == 'ammo' and not a.fixed:
    assert error and 'cannot cast undefined to bool' in text and 'player.hasntfullammo' in text, 'Ammo failure not reproduced: '+str(home)
    assert network_checks['process_alive_after_scenario'] and not network_checks['udp_available_after_scenario'], 'Shutdown symptom not reproduced'
elif a.fixed:
    assert not error and expected, 'Fixed regression failed: '+str(home)
    if a.scenario == 'ammo':
        assert all(network_checks.values()), 'Fixed ammo service unavailable: '+str(home)
else: assert error and "has unmatching types 'undefined' and 'string'" in text, 'Expected failure not reproduced: '+str(home)
