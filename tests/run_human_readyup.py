#!/usr/bin/env python3
"""Disposable real Promod runtime; synthetic humans use native input/command paths.
Never loads the test plugin in the input runtime or changes existing services.
"""
import argparse
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
import zlib

ROOT = Path(__file__).resolve().parents[1]
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--runtime', type=Path, required=True)
p.add_argument('--game', type=Path, required=True)
a = p.parse_args()
assert (a.runtime / '.bot-test-runtime').is_file()
home = Path(tempfile.mkdtemp(prefix='cod4x-human-readyup-'))
for name in ('mods', 'integrity'):
    shutil.copytree(a.runtime / name, home / name)
for name in ('main', 'zone'):
    (home / name).symlink_to((a.game / name).resolve(), target_is_directory=True)
shutil.copy2(ROOT / 'bin/cod4x18_dedrun', home / 'cod4x18_dedrun')
mod = home / 'mods/pml220'
spec = importlib.util.spec_from_file_location('prepare', ROOT / 'tools/bots/prepare.py')
prepare = importlib.util.module_from_spec(spec); spec.loader.exec_module(prepare)
lock = json.loads((ROOT / 'bots/dependencies.json').read_text())
for name, expected in lock['promod']['files'].items():
    assert prepare.digest(mod / name) == expected
for name, expected in lock['integrity_headers'].items():
    assert prepare.digest(home / 'integrity/addiwdheaders' / name) == expected
raw = prepare.rawfile(zlib.decompress((mod / 'mod.ff').read_bytes()[12:]), 'promod/readyup.gsc')
(mod / 'promod/readyup.gsx').write_text(prepare.bot_readyup(raw))
shutil.copy2(ROOT / 'tests/promod_runtime.gsc', mod / 'maps/mp/bots/integration_test.gsc')
for wrapper in (mod / 'maps/mp').glob('mp_*.gsx'):
    wrapper.write_text(wrapper.read_text().replace('main(){', 'main(){level thread maps\\mp\\bots\\integration_test::init();', 1))
(home / 'plugins').mkdir()
subprocess.run(['cc', '-m32', '-shared', '-fPIC', str(ROOT / 'tests/promod_runtime_plugin.c'),
                '-o', str(home / 'plugins/runtime_test.so')], check=True)
password = secrets.token_hex(20)
(mod / 'qualification.cfg').write_text(f'''set rcon_password "{password}"
set promod_mode "match_mr12_pb"
set promod_allow_no_punkbuster "1"
set promod_auto_maprotate "1"
set g_allowVote "1"
set g_oldVoting "1"
set g_voteAllowMap "1"
set g_voteCooldown "0"
set sv_mapRotation "gametype sd map mp_crash gametype sd map mp_strike gametype sd map mp_backlot"
set sv_randomMapRotation "0"
''')
with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as channel:
    channel.bind(('127.0.0.1', 0)); port = channel.getsockname()[1]
output = (home / 'console.log').open('w')
cmd = [str(home / 'cod4x18_dedrun'), '+set', 'dedicated', '1', '+set', 'net_ip', '127.0.0.1',
       '+set', 'net_port', str(port), '+set', 'fs_homepath', str(home), '+set', 'fs_basepath', str(home),
       '+set', 'fs_game', 'mods/pml220', '+set', 'sv_pure', '1', '+set', 'sv_maxclients', '12',
       '+set', 'fs_localizedHeadersPath', str(home / 'integrity'), '+set', 'bot_enable', '1', '+set', 'bot_debug', '1', '+exec', 'qualification.cfg', '+map_rotate']
proc = subprocess.Popen(cmd, cwd=home, stdin=subprocess.PIPE, stdout=output, stderr=subprocess.STDOUT)
checks = {}; snapshots = []
def send(command):
    assert proc.poll() is None, 'engine exited: ' + str(home)
    proc.stdin.write((command + '\n').encode()); proc.stdin.flush()
def rcon(command):
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as channel:
        channel.settimeout(3)
        channel.sendto(b'\xff' * 4 + f'rcon {password} {command}'.encode(), ('127.0.0.1', port))
        return re.sub(r'\^[0-9]', '', channel.recv(65535).decode(errors='replace'))
def snap(tag):
    send('set integration_snapshot ""\nset integration_request ' + tag)
    deadline = time.monotonic() + 4
    while time.monotonic() < deadline:
        value = rcon('integration_snapshot')
        found = re.search(r'PROMOD_RUNTIME ' + tag + r' (.*)" default', value)
        if not found:
            found = re.search(r'PROMOD_RUNTIME ' + tag + r' ([^"\n]+)', value)
        if found:
            data = dict(re.findall(r'(\w+)=([\w-]+)', found[1]))
            data = {k: int(v) if re.fullmatch(r'-?\d+', v) else v for k,v in data.items()}
            snapshots.append(dict(tag=tag, **data)); print(tag, data, flush=True); return data
        time.sleep(.1)
    raise AssertionError('snapshot timeout: ' + tag)
def check(name, value):
    checks[name] = bool(value)
    assert value, name + ': ' + str(home)
def human(slot):
    send(f'runtime_fixture {slot} human'); time.sleep(.2); snap('reset_human'); snap('recorded'); time.sleep(.2)
def use(slot):
    snap('recorded'); send(f'runtime_fixture {slot} use 1'); time.sleep(.3)
    send(f'runtime_fixture {slot} use 0'); time.sleep(.2)
def restore():
    for i in range(12): send(f'runtime_fixture {i} bot')
def start():
    human(3); use(3)
    ready = snap('one_human_confirmed')
    check('one_human_can_confirm', ready['over'] == 1 and ready['eligible'] == 1 and ready['pending'] == 0)
    restore(); time.sleep(14)
    state = snap('playing')
    check('original_countdown_start_' + str(len(snapshots)), state['rdyup'] == 0 and state['phase'] == 'playing')
    restore()
try:
    time.sleep(14)
    state = snap('bot_only')
    check('12_bots_zero_humans_wait', state['bots'] == 12 and state['eligible'] == 0 and state['pending'] == 0 and state['rdyup'] == 1 and state['over'] == 0 and state['bot_ready'] == 0)
    snap('bots_mark_ready'); time.sleep(.2); state = snap('bots_forced_ready')
    check('bot_ready_flags_cannot_start', state['bot_ready'] == 0 and state['over'] == 0 and state['pending'] == 0)
    send('loadplugin runtime_test'); time.sleep(.5)
    human(0); state = snap('one_unready')
    check('one_human_waits', state['eligible'] == 1 and state['pending'] == 1 and state['bot_ready'] == 0 and state['over'] == 0)
    human(1)
    snap('team_reset'); time.sleep(.2); state = snap('bot_spectators')
    check('bot_teams_do_not_change_quorum', state['eligible'] == 2 and state['pending'] == 2 and state['over'] == 0)
    snap('team_restore'); time.sleep(.2)
    use(0); state = snap('one_of_two')
    check('one_of_two_waits', state['eligible'] == 2 and state['pending'] == 1 and state['human_ready'] == 1 and state['over'] == 0)
    snap('human_spectator'); time.sleep(.2); state = snap('spectators')
    check('spectators_excluded', state['eligible'] == 0 and state['pending'] == 0 and state['human_ready'] == 0 and state['over'] == 0)
    snap('human_restore'); time.sleep(.2); state = snap('returned')
    check('spectator_return_requires_confirmation', state['eligible'] == 2 and state['pending'] == 2)
    use(0); snap('human_switch'); time.sleep(.2); state = snap('switched')
    check('team_switch_resets_confirmation', state['eligible'] == 2 and state['pending'] == 2 and state['human_ready'] == 0 and state['over'] == 0)
    # An unready disconnect removes the entity from the original level.players.
    send('clientkick 1'); time.sleep(.5); state = snap('disconnect')
    check('disconnect_no_stale_entry', state['eligible'] == 1 and state['pending'] <= 1)
    human(2); state = snap('late_join')
    check('joining_recalculates', state['eligible'] == 2 and state['pending'] >= 1 and state['over'] == 0)
    # Drop the remaining humans while unready: zero must still wait.
    send('clientkick 0\nclientkick 2'); time.sleep(12); state = snap('last_disconnect')
    check('last_human_disconnect_waits', state['eligible'] == 0 and state['pending'] == 0 and state['over'] == 0)
    human(3); human(4); use(3); use(4)
    ready = snap('two_humans_confirmed')
    check('all_humans_confirmed_countdown', ready['over'] == 1 and ready['eligible'] == 2 and ready['pending'] == 0)
    restore(); time.sleep(7); state = snap('all_ready')
    check('all_humans_original_start', state['rdyup'] == 0 and state['phase'] == 'playing')
    restore()
    # Native vote electorate: three humans, one bot casting cannot pass a ballot.
    human(3); human(4); human(5)
    send('runtime_fixture 6 callvote mp_strike'); time.sleep(.2)
    check('bot_cannot_callvote', 'slot=6 human=0 voteTime=0' in (home / 'console.log').read_text(errors='replace'))
    target = 'mp_strike' if state['map'] != 'mp_strike' else 'mp_backlot'
    send('runtime_fixture 3 callvote ' + target); time.sleep(.2)
    send('runtime_fixture 6 vote yes'); time.sleep(.3)
    check('bot_vote_does_not_pass', '""' in rcon('g_votedMapName'))
    send('runtime_fixture 4 vote yes'); time.sleep(4)
    check('two_of_three_humans_pass', f'"{target}"' in rcon('g_votedMapName'))
    restore(); snap('short_match'); send('runtime_fixture 6 eliminate axis'); time.sleep(12)
    round1 = snap('ordinary_round')
    check('ordinary_round_no_readyup', round1['map'] == state['map'] and round1['rdyup'] == 0 and round1['rounds'] == 1)
    snap('short_match'); send('runtime_fixture 6 eliminate axis'); time.sleep(24)
    voted = snap('voted_map')
    deadline = time.monotonic() + 30
    while voted['map'] != target and time.monotonic() < deadline:
        time.sleep(2); voted = snap('voted_map_wait')
    check('voted_map_resets_readyup', voted['map'] == target and voted['rdyup'] == 1 and voted['over'] == 0 and voted['eligible'] == 0 and voted['bot_ready'] == 0)
    start(); snap('short_match'); send('runtime_fixture 6 eliminate axis'); time.sleep(12)
    snap('short_match'); send('runtime_fixture 6 eliminate axis'); time.sleep(24)
    rotated = snap('automatic_map')
    deadline = time.monotonic() + 30
    while rotated['map'] == target and time.monotonic() < deadline:
        time.sleep(2); rotated = snap('automatic_map_wait')
    check('completed_match_rotation_resets', rotated['map'] != target and rotated['rdyup'] == 1 and rotated['over'] == 0 and rotated['eligible'] == 0 and rotated['bot_ready'] == 0)
    check('purity_preserved', '"1"' in rcon('sv_pure'))
finally:
    if proc.poll() is None: send('quit')
    try: proc.wait(timeout=10)
    finally:
        if proc.poll() is None: proc.kill(); proc.wait()
        output.close()
        console = (home / 'console.log').read_text(errors='replace')
        checks['clean_scripts'] = not re.search(r'Sys_Error:|script (?:compile|runtime) error|Segmentation fault', console, re.I)
        checks['eight_headers'] = 'Loaded 8 administrative IWD checksums' in console
        result = {'evidence': str(home), 'checks': checks, 'snapshots': snapshots,
                  'binary_sha256': prepare.digest(home / 'cod4x18_dedrun'),
                  'readyup_overlay_sha256': prepare.digest(mod / 'promod/readyup.gsx'),
                  'dependency_lock_sha256': prepare.digest(ROOT / 'bots/dependencies.json')}
        (home / 'results.json').write_text(json.dumps(result, indent=2) + '\n')
        print(json.dumps({'evidence': str(home), 'checks': checks}, indent=2))
assert all(checks.values())
