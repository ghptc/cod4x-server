#!/usr/bin/env python3
"""Disposable native five-ally qualification. No simulated zombie damage or kills.

Synthetic loopback humans receive normal weapons and native user commands. Only
their health is increased for sustained observation. This cannot certify balance
against competent graphical players or replace operator gameplay qualification.
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
RUNNER_SHA256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
p = argparse.ArgumentParser(description=__doc__)
for name in ('runtime', 'game', 'binary'):
    p.add_argument('--' + name, required=True, type=Path)
p.add_argument('--observe-seconds', default=130, type=int)
a = p.parse_args()
assert (a.runtime / '.bot-test-runtime').is_file()
home = Path(tempfile.mkdtemp(prefix='btd-five-allies-'))
for name in ('mods', 'integrity'):
    shutil.copytree(a.runtime / name, home / name)
for name in ('main', 'zone'):
    (home / name).symlink_to((a.game / name).resolve(), target_is_directory=True)
shutil.copy2(a.binary, home / 'cod4x18_dedrun')
mod = home / 'mods/btd_alpha_001'
spec = importlib.util.spec_from_file_location('allied_preparation', ROOT / 'tools/btd/prepare.py')
prepare = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prepare)
lock = json.loads((ROOT / 'tools/btd/dependencies.json').read_text())
ff = (mod / 'mod.ff').read_bytes()
assert hashlib.sha256(ff).hexdigest() == lock['files']['btd_alpha_001/mod.ff']
for name, data in prepare.allied_overlays(ff, lock).items():
    target = mod / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
global_script = mod / prepare.SCRIPT.replace('.gsc', '.gsx')
source = global_script.read_bytes()
assert source.count(b'init()\r\n{') == 1
source = source.replace(b'init()\r\n{', b'init()\r\n{\r\n thread btd_allies_test::main();', 1)
# The non-graphical UDP clients have no profile upload. Supply the five vendor
# integrity sentinel stats only in the disposable fixture, preserving isbot=false.
sentinel = b'\tlevel notify( "connected", self );'
assert source.count(sentinel) == 1
source = source.replace(sentinel, b'\tif (!self.isbot) for (fixture_stat = 0; fixture_stat < 5; fixture_stat++) self setstat(205 + fixture_stat * 10, 1);\r\n' + sentinel, 1)
global_script.write_bytes(source)
shutil.copy2(ROOT / 'tests/btd_allies.gsc', mod / 'btd_allies_test.gsc')
(home / 'plugins').mkdir()
subprocess.run(['gcc', '-m32', '-shared', '-fPIC', '-Wall', '-Wextra', '-Werror',
                str(ROOT / 'tests/btd_allies_fixture.c'), '-o', str(home / 'plugins/btd_allies_fixture.so')], check=True)
baseline = {name: hashlib.sha256((mod / name).read_bytes()).hexdigest()
            for name in ('canonical-shared.cfg', 'canonical-mode.cfg')}
with (mod / 'canonical-mode.cfg').open('a') as cfg:
    cfg.write('\nset btd_grace_time "30"\nset btd_wave_settings "2"\nset btd_start_zoms "5"\n')
password = secrets.token_hex(16)
with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as channel:
    channel.bind(('127.0.0.1', 0))
    port = channel.getsockname()[1]
command = [str(home / 'cod4x18_dedrun'), '+set', 'dedicated', '1', '+set', 'net_ip', '127.0.0.1',
    '+set', 'net_port', str(port), '+set', 'fs_basepath', str(home), '+set', 'fs_homepath', str(home / 'persistent'),
    '+set', 'fs_game', 'mods/btd_alpha_001', '+set', 'sv_autoupdate', '0', '+set', 'developer', '1',
    '+set', 'developer_script', '1', '+set', 'fs_localizedHeadersPath', str(home / 'integrity'),
    '+set', 'sv_maxclients', '12', '+set', 'rcon_password', password,
    '+exec', 'canonical-shared.cfg', '+exec', 'canonical-mode.cfg', '+map', 'mp_killhouse']
checks = {}
snapshots = {}
failure = None
logpath = home / 'console.log'

def console():
    return re.sub(r'\^[0-9]', '', logpath.read_text(errors='replace'))

with logpath.open('w') as output:
    proc = subprocess.Popen(command, cwd=home, stdin=subprocess.PIPE, stdout=output, stderr=subprocess.STDOUT)
    def send(value):
        assert proc.poll() is None, 'Native server exited: ' + str(home)
        proc.stdin.write((value + '\n').encode())
        proc.stdin.flush()
    def rcon(value, credential=password):
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as channel:
            channel.settimeout(4)
            channel.sendto(b'\xff' * 4 + f'rcon {credential} {value}'.encode(), ('127.0.0.1', port))
            return re.sub(r'\^[0-9]', '', channel.recv(65535).decode(errors='replace'))
    def snapshot(label):
        send('set btd_allies_test_request ' + label)
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            match = re.search(r'BTD_ALLIES_SNAPSHOT label=' + label + r' ([^\r\n]+)', console())
            if match:
                result = {k: int(v) for k, v in re.findall(r'(\w+)=(\d+)', match[1])}
                snapshots[label] = result
                return result
            time.sleep(.1)
        raise AssertionError('Missing native snapshot ' + label + ': ' + str(home))
    def admit(number):
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as channel:
            channel.bind(('127.0.0.2', 0))
            channel.settimeout(4)
            channel.sendto(b'\xff' * 4 + b'getchallenge 123456', ('127.0.0.1', port))
            challenge = channel.recv(2048)[4:].decode().split()[1]
            name = 'AlliesHumanFixture' + str(number)
            payload = f'connect "\\protocol\\21\\challenge\\{challenge}\\qport\\{24444 + number}\\name\\{name}\\rate\\25000\\snaps\\20"'
            channel.sendto(b'\xff' * 4 + payload.encode(), ('127.0.0.1', port))
            assert b'connectResponse' in channel.recv(2048)
        time.sleep(.2)
        slot = int(re.findall(r'CS_CONNECTED for ' + name + r' num (\d+)', console())[-1])
        send('btd_allies_fixture activate ' + str(slot))
        return slot
    try:
        time.sleep(12)
        send('loadplugin btd_allies_fixture')
        time.sleep(1)
        initial = snapshot('initial')
        checks['five_default_alive'] = initial['allies'] == initial['alive'] == 5
        records = re.findall(r'BTD_ALLIES_PLAYER label=initial .*?skill=(easy|medium)', console())
        checks['three_easy_two_medium'] = records.count('easy') == 3 and records.count('medium') == 2
        checks['no_human_no_wave'] = initial['humans'] == initial['wave'] == 0
        checks['bad_rcon_denied'] = 'Bad rcon' in rcon('bot_killall', 'invalid-fixture')
        checks['pure_enabled'] = bool(re.search(r'"sv_pure" is: "1"', rcon('sv_pure')))
        for invalid in ('-1', '13', '1x', '+1', '1 2'):
            checks['add_validation_' + invalid] = 'Usage:' in rcon('bot_add ' + invalid)
            checks['kick_validation_' + invalid] = 'Usage:' in rcon('bot_kick ' + invalid)
        human = admit(1)
        time.sleep(3)
        joined = snapshot('joined')
        checks['actual_human_spawned'] = joined['humans'] == 1
        early_kill = rcon('bot_killall')
        checks['grace_killall_actual'] = 'Killed 5 bots' in early_kill
        time.sleep(.2)
        checks['grace_killall_dead'] = snapshot('grace_dead')['alive'] == 0
        time.sleep(5)
        checks['grace_respawn'] = snapshot('grace_respawn')['alive'] == 5
        # Observe the five autonomous allies before enabling native human fire.
        for second in range(35):
            time.sleep(1)
            if second >= 20:
                send('set btd_allies_test_request protection')
        snapshot('autonomous')
        send('set btd_allies_test_request protection')
        time.sleep(.3)
        checks['human_shot_obstruction'] = 'BTD_ALLIES_PROTECTION baseline=1 blocked=1 guarded=1' in console()
        send('btd_allies_fixture fire ' + str(human))
        deadline = time.monotonic() + a.observe_seconds
        while time.monotonic() < deadline and proc.poll() is None:
            time.sleep(1)
            if re.search(r'script (?:runtime|compile) error', console()): break
            send('set btd_allies_test_request progress' + str(int(deadline - time.monotonic())))
            if re.search(r'BTD_ALLIES_SNAPSHOT .* wave=[2-9]', console()): break
        # Give the original five a second wave of naturally spawned enemies;
        # weak reaction/accuracy means not every ally gets a hit in wave one.
        send('btd_allies_fixture stop ' + str(human))
        time.sleep(12)
        send('btd_allies_fixture fire ' + str(human))
        time.sleep(3)
        combat = snapshot('combat')
        checks['ally_native_bullet_hits'] = combat['hits'] > 0
        hitting_slots = set(re.findall(r'BTD_ALLIES_NATIVE_HIT slot=(\d+)', console()))
        # Intentionally inaccurate allies need not all hit in a five-zombie
        # wave. Require per-slot native hits OR actual ammunition expenditure
        # with a live zombie target, rather than aggregate damage from one bot.
        initial_clips = {slot: (weapon, int(clip)) for slot, weapon, clip in re.findall(
            r'BTD_ALLIES_PLAYER label=initial slot=(\d+) .*?weapon=(\w+) clip=(\d+)', console())}
        engaged = set(hitting_slots) | set(re.findall(r'BTD_ALLIES_NATIVE_SHOT slot=(\d+)', console()))
        for slot, weapon, clip, target in re.findall(
                r'BTD_ALLIES_PLAYER label=autonomous slot=(\d+) .*?weapon=(\w+) clip=(\d+) target=(-?\d+)', console()):
            if slot in initial_clips and initial_clips[slot][0] == weapon and int(clip) < initial_clips[slot][1] and int(target) >= 0:
                engaged.add(slot)
        checks['five_allies_native_engagement'] = len(engaged) == 5
        checks['zombie_native_melee_ally'] = combat['melee'] > 0
        checks['human_no_ally_damage'] = combat['human_damage'] == 0
        checks['human_native_bullet_hits'] = combat['human_hits'] > 0
        checks['native_wave_progression'] = combat['wave'] >= 2
        checks['synthetic_human_kill_majority'] = combat['human_kills'] > combat['kills']
        before = rcon('bot_status')
        killed_reply = rcon('bot_killall')
        killed_match = re.search(r'Killed (\d+) bots', killed_reply)
        # The earlier grace trial requires five real deaths. In live waves some
        # allies can already be dead; zero then is the correct administration result.
        checks['wave_killall_population'] = bool(killed_match and int(killed_match[1]) <= combat['alive'])
        time.sleep(.3)
        killed = snapshot('killed')
        checks['killall_preserves_humans'] = killed['humans'] == combat['humans']
        checks['killall_observed_deaths'] = killed['alive'] == 0
        time.sleep(15)
        respawn = snapshot('respawn')
        for attempt in range(8):
            if not respawn['canjoin'] or respawn['alive'] == respawn['allies']: break
            time.sleep(1)
            respawn = snapshot('grace_recovery_' + str(attempt))
        checks['bot_respawn_respects_wave'] = (respawn['alive'] == respawn['allies'] if respawn['canjoin'] else respawn['alive'] == 0)
        checks['kickall_command'] = 'Bots removed' in rcon('bot_kickall')
        time.sleep(4)
        empty = snapshot('empty')
        checks['kickall_no_immediate_refill'] = empty['allies'] == 0
        checks['empty_killall_safe'] = 'Killed 0 bots' in rcon('bot_killall')
        checks['explicit_add'] = 'Added 5 bots' in rcon('bot_add 5')
        time.sleep(6)
        checks['explicit_five'] = snapshot('readded')['allies'] == 5
        checks['kick_count'] = 'Removed 2 bots' in rcon('bot_kick 2')
        time.sleep(1)
        checks['kick_count_population'] = snapshot('kicked')['allies'] == 3
        # Reconnect and capacity exercise actual UDP admission, not script clients.
        replacement = admit(2)
        time.sleep(2)
        admitted_replacement = snapshot('replacement_waiting')
        for attempt in range(90):
            if admitted_replacement['human_alive'] == 2: break
            time.sleep(1)
            admitted_replacement = snapshot('replacement_spawn_' + str(attempt))
        checks['replacement_respects_join_window'] = admitted_replacement['human_alive'] == 2
        rcon('clientkick ' + str(human))
        human = replacement
        time.sleep(3)
        checks['reconnect'] = snapshot('reconnect')['humans'] == 1
        rcon('bot_kickall')
        rcon('bot_limit 12')
        rcon('bot_add 12')
        time.sleep(6)
        capacity = snapshot('capacity')
        checks['capacity_respected'] = capacity['allies'] + capacity['humans'] == 12
        human2 = admit(3)
        time.sleep(2)
        admitted = snapshot('reclaimed')
        checks['human_admission_at_capacity'] = admitted['humans'] == 2 and admitted['allies'] == capacity['allies'] - 1
        send('btd_allies_fixture fire ' + str(human))
        # Require a real active wave with living allies and humans. Killing in
        # grace races the vendor's legitimate human respawn before its queued end.
        ready = admitted
        for attempt in range(90):
            if ready['alive'] > 0 and ready['human_alive'] > 0 and not ready['canjoin']: break
            time.sleep(1)
            ready = snapshot('elimination_ready_' + str(attempt))
        checks['living_allies_before_human_death'] = ready['alive'] > 0 and not ready['canjoin']
        boundary = len(console())
        send('set btd_allies_test_request all_humans_die')
        time.sleep(4)
        eliminated = re.search(r'BTD_ALLIES_SNAPSHOT label=eliminated ([^\r\n]+)', console()[boundary:])
        ended_state = {k: int(v) for k, v in re.findall(r'(\w+)=(\d+)', eliminated[1])} if eliminated else {}
        checks['all_humans_dead_ends_survival'] = (ready['alive'] > 0 and ended_state.get('alive', 0) > 0 and ended_state.get('human_alive') == 0)
        rcon('bot_limit 5')
        rcon('bot_autofill 1')
        for mapname in ('mp_crash', 'mp_killhouse'):
            send('map ' + mapname)
            time.sleep(12)
            state = snapshot('transition_' + mapname)
            checks['transition_' + mapname] = state['allies'] == 5
    except (AssertionError, OSError) as exc:
        failure = str(exc)
        checks['runner_completed'] = False
    finally:
        if proc.poll() is None:
            try: send('quit')
            except BrokenPipeError: pass
        try: checks['shutdown_zero'] = proc.wait(timeout=10) == 0
        except subprocess.TimeoutExpired:
            proc.kill(); proc.wait(); checks['shutdown_zero'] = False

text = console()
if failure is None:
    logpath = home / 'console-restart.log'
    with logpath.open('w') as output:
        proc = subprocess.Popen(command, cwd=home, stdin=subprocess.PIPE, stdout=output, stderr=subprocess.STDOUT)
        try:
            time.sleep(12)
            restarted = snapshot('restart')
            checks['restart_five_alive'] = restarted['allies'] == restarted['alive'] == 5
            send('loadplugin btd_allies_fixture')
            time.sleep(.5)
            send('set btd_wave_settings 1')
            dynamic_human = admit(10)
            dynamic = restarted
            for attempt in range(45):
                time.sleep(1)
                dynamic = snapshot('dynamic_' + str(attempt))
                if dynamic['wave'] == 1: break
            checks['dynamic_wave_human_only_scaling'] = (dynamic['humans'] == 1 and dynamic['allies'] == 5 and
                dynamic['wave'] == 1 and dynamic['total'] == 28)
        except (AssertionError, OSError) as exc:
            failure = str(exc)
            checks['restart_five_alive'] = False
        finally:
            if proc.poll() is None:
                try: send('quit')
                except BrokenPipeError: pass
            try: checks['restart_shutdown_zero'] = proc.wait(timeout=10) == 0
            except subprocess.TimeoutExpired:
                proc.kill(); proc.wait(); checks['restart_shutdown_zero'] = False
    text += '\n' + console()
checks['no_script_errors'] = not re.search(r'script (?:compile|runtime) error|Sys_Error:|Segmentation fault', text, re.I)
checks['eight_headers'] = 'Loaded 8 administrative IWD checksums' in text
result = {'evidence': str(home), 'checks': checks, 'snapshots': snapshots,
    'failure': failure,
    'operator_gameplay_qualified': False, 'balance_qualified': False,
    'binary_sha256': hashlib.sha256((home / 'cod4x18_dedrun').read_bytes()).hexdigest(),
    'fixture_sha256': hashlib.sha256((mod / 'btd_allies_test.gsc').read_bytes()).hexdigest(),
    'runner_sha256': RUNNER_SHA256,
    'plugin_sha256': hashlib.sha256((home / 'plugins/btd_allies_fixture.so').read_bytes()).hexdigest(),
    'baseline_config_sha256': baseline}
(home / 'results.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps(result, indent=2))
assert all(checks.values()), 'Native allied qualification failed: ' + str(home)
