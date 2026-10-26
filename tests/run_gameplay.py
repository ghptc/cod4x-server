#!/usr/bin/env python3
"""Qualify a disposable prepared runtime locally; no remote hosts or deployment."""
import argparse
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
p.add_argument('--mode-config', type=Path, help='Optional canonical mode server.cfg to qualify')
p.add_argument('--scenario', choices=['rotation', 'controls', 'combat'], required=True)
a = p.parse_args()
runtime = a.runtime.resolve()
if not (runtime / '.bot-test-runtime').is_file():
    p.error('use a separate disposable runtime created by prepare.py')
for name in ['main', 'zone']:
    target = runtime / name
    if not target.exists():
        target.symlink_to((a.game / name).resolve(), target_is_directory=True)
mod = runtime / 'mods/pml220'
shutil.copy2(ROOT / 'tests/gameplay.gsc', mod / 'maps/mp/bots/gameplay_test.gsc')
for wrapper in (mod / 'maps/mp').glob('mp_*.gsx'):
    text = wrapper.read_text()
    call = 'level thread maps\\mp\\bots\\gameplay_test::init();'
    if call not in text:
        wrapper.write_text(text.replace('main(){promod_original_map_main();', 'main(){' + call + 'promod_original_map_main();', 1))
home = Path(tempfile.mkdtemp(prefix='gameplay-' + a.scenario + '-', dir=runtime))
(home / 'mods/pml220').mkdir(parents=True)
password = secrets.token_hex(12)  # Local fixture secret, never printed or committed.
rotation = 'gametype sd map mp_crash gametype sd map mp_strike gametype sd map mp_crossfire gametype sd map mp_backlot'
config = (a.mode_config.read_text() if a.mode_config else '') + '\n' + (ROOT / 'config/player-map-voting.cfg').read_text()
config += f'\nset sv_mapRotation "{rotation}"\nset sv_randomMapRotation "1"\nset promod_auto_maprotate "1"\n'
config += 'set promod_mode "' + ('match_mr12_pb' if a.scenario == 'rotation' else 'custom_public') + '"\n'
config += f'set gameplay_test_rotation "{int(a.scenario == "rotation")}"\nset gameplay_test_inventory "{int(a.scenario == "controls")}"\n'
config += f'set gameplay_test_stage "0"\nset rcon_password "{password}"\n'
private = home / 'mods/pml220/gameplay-test.cfg'
private.touch(mode=0o600)
private.write_text(config)
# Reserve a loopback-only UDP port for this disposable process.
with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as reservation:
    reservation.bind(('127.0.0.1', 0))
    port = reservation.getsockname()[1]
cmd = [str(runtime / 'cod4x18_dedrun'), '+set', 'dedicated', '1', '+set', 'net_ip', '127.0.0.1',
       '+set', 'net_port', str(port), '+set', 'fs_basepath', str(runtime), '+set', 'fs_homepath', str(home),
       '+set', 'fs_game', 'mods/pml220', '+set', 'fs_localizedHeadersPath', str(runtime / 'integrity'),
       '+set', 'sv_maxclients', '12', '+set', 'sv_pure', '1', '+set', 'g_gametype', 'sd',
       '+set', 'bot_enable', str(int(a.scenario != 'rotation')), '+set', 'bot_debug', '1',
       '+exec', 'gameplay-test.cfg', '+map', 'mp_crash']

def rcon(command, credential=password):
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as channel:
        channel.settimeout(3)
        channel.sendto(b'\xff' * 4 + f'rcon {credential} {command}\n'.encode(), ('127.0.0.1', port))
        return channel.recv(65535).decode(errors='replace')

checks = {}
logfile = home / 'console.log'
with logfile.open('w') as log:
    proc = subprocess.Popen(cmd, cwd=runtime, stdin=subprocess.PIPE, stdout=log, stderr=subprocess.STDOUT)
    human = None
    try:
        if a.scenario == 'rotation':
            deadline = time.monotonic() + 55
            while proc.poll() is None and time.monotonic() < deadline:
                time.sleep(1)
                gamefile = home / 'mods/pml220/games_mp.log'
                text = gamefile.read_text(errors='replace') if gamefile.exists() else ''
                if 'GAMEPLAY_TEST FAIL' in text or 'PASS rotation-resumes-without-repeat' in text:
                    break
            checks['native_round_match_vote_rotation'] = 'PASS rotation-resumes-without-repeat' in text
        elif a.scenario == 'controls':
            time.sleep(10)
            checks['autofill_twelve'] = 'bots=12' in rcon('bot_status')
            checks['bad_rcon_denied'] = 'Bad rcon' in rcon('bot_kickall', 'invalid-fixture-password')
            checks['bad_rcon_keeps_bots'] = 'bots=12' in rcon('bot_status')
            # The admitted fixture remains CONNECTED; it is not a graphical/authenticated gameplay client.
            human = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            human.bind(('127.0.0.2', 0)); human.settimeout(3)
            human.sendto(b'\xff' * 4 + b'getchallenge 123456', ('127.0.0.1', port))
            challenge = human.recv(2048)[4:].decode().split()[1]
            payload = f'connect "\\protocol\\21\\challenge\\{challenge}\\qport\\24444\\name\\LocalHumanFixture\\rate\\25000\\snaps\\20"'
            human.sendto(b'\xff' * 4 + payload.encode(), ('127.0.0.1', port))
            checks['human_admitted'] = b'connectResponse' in human.recv(2048)
            time.sleep(1)
            status = rcon('bot_status')
            checks['one_human_eleven_bots'] = 'humans=1' in status and 'bots=11' in status
            rcon('bot_kickall'); time.sleep(1)
            status = rcon('bot_status')
            checks['kickall_preserves_human'] = 'humans=1' in status and 'bots=0' in status and 'state=paused-with-humans' in status
            proc.stdin.write(b'fast_restart\n'); proc.stdin.flush(); time.sleep(2)
            status = rcon('bot_status')
            checks['round_stays_paused'] = 'humans=1' in status and 'bots=0' in status
            rcon('map mp_backlot'); time.sleep(3)
            status = rcon('bot_status')
            checks['admin_map_and_pause'] = 'humans=1' in status and 'bots=0' in status and 'mp_backlot' in rcon('status')
            rcon('bot_autofill 1'); time.sleep(4)
            status = rcon('bot_status')
            checks['explicit_resume_no_duplicates'] = 'humans=1' in status and 'bots=11' in status
            rcon('bot_kickall'); time.sleep(1)
            checks['repeated_kickall'] = 'bots=0' in rcon('bot_status')
        else:
            time.sleep(45)
        if proc.poll() is None:
            proc.stdin.write(b'sv_pure\nquit\n'); proc.stdin.flush()
        checks['exit_zero'] = proc.wait(timeout=10) == 0
    finally:
        if human is not None: human.close()
        if proc.poll() is None: proc.kill(); proc.wait()
console = logfile.read_text(errors='replace')
game = (home / 'mods/pml220/games_mp.log').read_text(errors='replace')
if a.scenario == 'rotation':
    checks['native_round_match_vote_rotation'] = 'PASS rotation-resumes-without-repeat' in game
if a.scenario == 'combat':
    checks['bot_weapon_fire'] = game.count('PMBOT FIRE') >= 20
    checks['promod_kills'] = bool(re.search(r' K;', game))
checks['script_assertions'] = 'class-and-weapon-checks-complete' in game and 'GAMEPLAY_TEST FAIL' not in game
checks['no_script_or_fatal_error'] = not re.search(r'Sys_Error:|script (?:compile|runtime) error|Segmentation fault', console, re.I)
checks['pure_and_eight_headers'] = 'Loaded 8 administrative IWD checksums' in console and bool(re.search(r'"sv_pure" is: "1', console))
if a.scenario == 'controls':
    checks['all_native_sidearm_inventories'] = len(set(re.findall(r'PASS native-sidearm-inventory-([a-z0-9]+)', game))) == 5
    checks['all_native_primary_inventories'] = len(set(re.findall(r'PASS native-inventory-([a-z0-9]+)', game))) == 14
(home / 'results.json').write_text(json.dumps(checks, indent=2) + '\n')
print(json.dumps({'evidence': str(home), 'checks': checks}, indent=2))
assert all(checks.values()), 'local qualification failed; inspect private evidence'
