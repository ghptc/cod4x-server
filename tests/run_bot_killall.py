#!/usr/bin/env python3
"""Qualify bot_killall in a NEW copy of a prepared local runtime."""
import argparse
import json
from pathlib import Path
import re
import shutil
import secrets
import socket
import subprocess
import tempfile
import time

p = argparse.ArgumentParser()
p.add_argument('--runtime', type=Path, required=True)
p.add_argument('--game', type=Path, required=True)
a = p.parse_args()
assert (a.runtime / '.bot-test-runtime').is_file()
root = Path(__file__).resolve().parents[1]
runtime = Path(tempfile.mkdtemp(prefix='cod4x-killall-'))
for name in ['mods', 'integrity']:
    shutil.copytree(a.runtime / name, runtime / name)
for name in ['main', 'zone']:
    (runtime / name).symlink_to((a.game / name).resolve(), target_is_directory=True)
shutil.copy2(root / 'bin/cod4x18_dedrun', runtime / 'cod4x18_dedrun')
mod = runtime / 'mods/pml220'
(mod / 'maps/mp/bots/killall_test.gsc').write_text(r'''
init()
{
    for (;;)
    {
        wait 0.05;
        request = getdvar("killall_test_snapshot");
        if (request == "") continue;
        setdvar("killall_test_snapshot", "");
        players = getentarray("player", "classname");
        alive = 0;
        for (i = 0; i < players.size; i++)
        {
            player = players[i];
            if (player.isbot && isalive(player) && player.sessionstate == "playing") alive++;
        }
        logprint("KILLALL_TEST " + request + " alive=" + alive + " players=" + players.size + "\n");
    }
}
''')
for wrapper in (mod / 'maps/mp').glob('mp_*.gsx'):
    wrapper.write_text(wrapper.read_text().replace('main(){', 'main(){level thread maps\\mp\\bots\\killall_test::init();', 1))
with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as channel:
    channel.bind(('127.0.0.1', 0)); port = channel.getsockname()[1]
cmd = [str(runtime / 'cod4x18_dedrun'), '+set', 'dedicated', '1', '+set', 'net_ip', '127.0.0.1',
       '+set', 'net_port', str(port), '+set', 'fs_basepath', str(runtime), '+set', 'fs_homepath', str(runtime),
       '+set', 'fs_game', 'mods/pml220', '+set', 'fs_localizedHeadersPath', str(runtime / 'integrity'),
       '+set', 'sv_maxclients', '12', '+set', 'sv_pure', '1', '+set', 'g_gametype', 'sd',
       '+set', 'bot_enable', '1', '+set', 'bot_debug', '1', '+set', 'promod_mode', 'custom_public',
       '+map', 'mp_crash']
password = secrets.token_hex(16)
cmd[1:1] = ['+set', 'rcon_password', password]
checks = {}
with (runtime / 'console.log').open('w') as output:
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=output, stderr=subprocess.STDOUT)
    def send(command):
        proc.stdin.write((command + '\n').encode()); proc.stdin.flush()
    def snapshot(name):
        send('set killall_test_snapshot ' + name); time.sleep(.15)
    def rcon(command, credential=password):
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as channel:
            channel.settimeout(3)
            channel.sendto(b'\xff' * 4 + f'rcon {credential} {command}'.encode(), ('127.0.0.1', port))
            reply = channel.recv(65535).decode(errors='replace')
            output.write(reply); output.flush()
            return reply
    try:
        time.sleep(10)
        # Disable combat for deterministic alive/dead counts; never change death callbacks.
        send('bots_play_fire 0\nbots_play_knife 0\nbot_autofill 0')
        time.sleep(5)
        snapshot('before')
        send('bot_status')
        checks['bad_rcon_denied'] = 'Bad rcon' in rcon('bot_killall', 'invalid-local-fixture')
        checks['authenticated_rcon'] = bool(re.search(r'Killed [1-9][0-9]* bots', rcon('bot_killall')))
        rcon('bot_killall'); send('bot_status'); snapshot('after')
        time.sleep(15); snapshot('respawn')
        send('bot_status\nbot_killall\nbot_status')
        time.sleep(2)
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as human:
            human.bind(('127.0.0.2', 0)); human.settimeout(3)
            human.sendto(b'\xff' * 4 + b'getchallenge 123456', ('127.0.0.1', port))
            challenge = human.recv(2048)[4:].decode().split()[1]
            payload = f'connect "\\protocol\\21\\challenge\\{challenge}\\qport\\24444\\name\\LocalHumanFixture\\rate\\25000\\snaps\\20"'
            human.sendto(b'\xff' * 4 + payload.encode(), ('127.0.0.1', port))
            checks['human_admitted'] = b'connectResponse' in human.recv(2048)
            time.sleep(.2)
            before = rcon('bot_status')
            rcon('bot_killall')
            after = rcon('bot_status')
            checks['human_connection_and_autofill_unchanged'] = ('humans=1' in before and 'humans=1' in after
                and 'bots=11' in before and 'bots=11' in after and 'state=paused-with-humans' in after)
        send('bot_kickall\nbot_killall\nbot_status\nsv_pure\nquit')
        checks['exit_zero'] = proc.wait(timeout=10) == 0
    finally:
        if proc.poll() is None: proc.kill(); proc.wait()
console = (runtime / 'console.log').read_text(errors='replace')
game = (mod / 'games_mp.log').read_text(errors='replace')
snapshots = {m[1]: int(m[2]) for m in re.finditer(r'KILLALL_TEST (\w+) alive=(\d+)', game)}
counts = [int(x) for x in re.findall(r'Killed (\d+) bots', console)]
checks.update({'initial_alive': snapshots.get('before', 0) > 0,
               'all_living_killed': bool(counts) and counts[0] == snapshots.get('before'),
               'no_surviving_bots': snapshots.get('after') == 0,
               'repeated_zero': len(counts) >= 2 and counts[1] == 0,
               'zero_bots': bool(counts) and counts[-1] == 0,
               'round_respawn': snapshots.get('respawn', 0) > 0,
               'connections_and_pause': console.count('state=paused-awaiting-human humans=0 connecting=0 bots=12') >= 4,
               'pure_headers': 'Loaded 8 administrative IWD checksums' in console and bool(re.search(r'"sv_pure" is: "1', console)),
               'suicide_callbacks': game.count('MOD_SUICIDE') >= 12,
               'no_script_errors': not re.search(r'Sys_Error:|script (?:compile|runtime) error|Segmentation fault', console, re.I)})
result = {'evidence': str(runtime), 'checks': checks, 'snapshots': snapshots, 'counts': counts}
(runtime / 'result.json').write_text(json.dumps(result, indent=2))
print(json.dumps(result, indent=2))
assert all(checks.values())
