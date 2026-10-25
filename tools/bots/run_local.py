#!/usr/bin/env python3
"""Run a disposable, network-isolated gameplay or admission regression."""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time
import sys

ROOT = Path(__file__).resolve().parents[2]
IMAGE = 'sha256:92528811226fabd05fee63074e22b7b5afd0fa9d63d5994bd3a8f74c8543cbfe'


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--runtime', type=Path, required=True)
    p.add_argument('--game', type=Path, required=True)
    p.add_argument('--image', default=IMAGE)
    p.add_argument('--image-binary', action='store_true', help='Test the immutable packaged executable instead of the mounted binary')
    p.add_argument('--scenario', choices=['gameplay', 'policy', 'rotation', 'burst', 'legacy', 'admin'], default='gameplay')
    p.add_argument('--seconds', type=int, default=90)
    a = p.parse_args()
    runtime = a.runtime.resolve()
    if not (runtime / '.bot-test-runtime').is_file():
        p.error('runtime must be created by prepare.py')
    binary = '/home/user/cod4/cod4x18_dedrun' if a.image_binary else '/runtime/cod4x18_dedrun'
    if a.image_binary:
        actual = subprocess.check_output(['docker', 'run', '--rm', '--pull', 'never', '--network', 'none',
                    '--read-only', '--entrypoint', 'sha256sum', a.image, binary], text=True).split()[0]
        if actual != json.loads((runtime / 'inputs.json').read_text())['binary_sha256']:
            p.error('Packaged executable does not match the prepared runtime binary hash')
    if a.scenario == 'policy' and a.seconds < 75:
        p.error('policy scenario requires at least 75 seconds')
    if a.scenario == 'rotation' and a.seconds < 135:
        p.error('rotation scenario requires at least 135 seconds')
    if a.scenario == 'admin' and a.seconds < 65:
        p.error('admin scenario requires at least 65 seconds')
    if not 20 <= a.seconds <= 600:
        p.error('seconds must be between 20 and 600')
    stamp = time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())
    name = 'cod4x-bots-' + a.scenario + '-' + str(os.getpid())
    home = runtime / 'runs' / name
    home.mkdir(parents=True)
    evidence = runtime / 'evidence'
    evidence.mkdir(exist_ok=True)
    prefix = evidence / (stamp + '-' + a.scenario)
    cmd = ['docker', 'run', '--pull', 'never', '--rm', '-i', '--name', name, '--network', 'none',
           '--user', f'{os.getuid()}:{os.getgid()}', '--read-only',
           '--tmpfs', '/tmp:rw,nosuid,size=128m', '--workdir', '/runtime',
           '--entrypoint', binary,
           '--mount', f'type=bind,src={runtime},dst=/runtime',
           '--mount', f'type=bind,src={a.game / "main"},dst=/runtime/main,readonly',
           '--mount', f'type=bind,src={a.game / "zone"},dst=/runtime/zone,readonly', a.image,
           '+set', 'dedicated', '1', '+set', 'net_ip', '127.0.0.1', '+set', 'net_port', '28971',
           '+set', 'fs_basepath', '/runtime', '+set', 'fs_homepath', '/runtime/runs/' + name,
           '+set', 'fs_game', 'mods/pml220', '+set', 'fs_localizedHeadersPath', '/runtime/integrity',
           '+set', 'sv_maxclients', '12', '+set', 'sv_pure', '1', '+set', 'g_gametype', 'sd',
           '+set', 'bot_enable', '1', '+set', 'bot_debug', '1', '+set', 'developer', '1',
           '+set', 'logfile', '2', '+set', 'g_logSync', '1',
           '+set', 'promod_mode', 'custom_public', '+map', 'mp_crash']
    schedule = [(10, 'status', 'bot_status\n'), (a.seconds-2, 'pure', 'sv_pure\nbot_status\n')]
    if a.scenario == 'admin':
        if not json.loads((runtime / 'inputs.json').read_text()).get('admin_rules_overlay'):
            p.error('admin scenario requires prepare.py --admin-rules')
        cmd[-2:-2] = ['+set', 'sv_promod_admin', '1']
        schedule += [(10.5, 'rcon-reject', None),
                     (11, 'bad-admin', 'mute nonsense\nmute 64\nmute 0 invalid\nsetteam 0 aliens\npromod_rule scr_sd_timelimit nan\npromod_rule scr_sd_roundlimit 0.5\npromod_rule sv_pure 0\n'),
                     (12, 'voice-mute', 'mute 0 voice\n'), (13, 'all-mute', 'mute 0 all\n'),
                     (14, 'unmute', 'unmute 0\n'), (15, 'spectator', 'setteam 0 spectator\n'),
                     (18, 'axis', 'setteam 0 axis\n'), (20, 'spectator-other', 'setteam 1 spectator\n'),
                     (22, 'allies', 'setteam 1 allies\n'),
                     (28, 'queue-rules', 'promod_rule scr_sd_timelimit 2.25\npromod_rule scr_sd_roundlimit 12\npromod_rule scr_sd_scorelimit 7\npromod_rule scr_sd_roundswitch 6\npromod_rule scr_team_fftype 0\npromod_rule sv_voice 1\n'),
                     (30, 'rules-before', 'scr_sd_timelimit\nui_timelimit\n'),
                     (32, 'reload-rules', 'map mp_crash\n'),
                     (40, 'rules-applied', 'scr_sd_timelimit\nui_timelimit\nscr_sd_roundlimit\nscr_sd_scorelimit\nscr_sd_roundswitch\nscr_team_fftype\nsv_voice\n'),
                     (41, 'default-time', 'promod_rule scr_sd_timelimit default\n'),
                     (44, 'other-map', 'map mp_backlot\n'),
                     (52, 'after-map', 'scr_sd_timelimit\nui_timelimit\nsetteam 0 spectator\n'),
                     (55, 'kick-reuse', 'clientkick 0\n'), (60, 'restored', 'bot_status\n'),
                     (62, 'empty-target', 'bot_kickall\nmute 0\nunmute 0\nsetteam 0 spectator\n')]
    if a.scenario == 'policy':
        # Only local stdin commands and real UDP handshake attempts inside the isolated namespace.
        schedule += [(12, 'password', 'g_password local-test\n'), (13, 'reject', None),
                     (14, 'invalid-password', 'bot_status\n'), (15, 'admit', None),
                     (16, 'human-priority', 'bot_status\n'), (18, 'pause-human', 'bot_kickall\nbot_status\n'),
                     (21, 'rotate-paused', 'map mp_backlot\n'), (25, 'paused-backlot', 'bot_status\n'),
                     (27, 'last-human-leave', 'clientkick 0\n'), (35, 'resumed', 'bot_status\n'),
                     (37, 'pause-empty', 'bot_kickall\n'), (39, 'rotate-empty', 'map mp_crash\n'),
                     (45, 'still-paused-empty', 'bot_status\n'), (47, 'manual', 'bot_autofill 1\n'),
                     (54, 'manual-resumed', 'bot_status\n'), (55, 'pause-without-kick', 'bot_autofill 0\nbot_status\n'),
                     (57, 'empty-again', 'bot_kickall\n'), (59, 'admit-paused', None),
                     (60, 'paused-new-human', 'bot_status\n'), (62, 'leave-paused-human', 'clientkick 0\n'),
                     (70, 'empty-transition-resumed', 'bot_status\n')]
    if a.scenario == 'rotation':
        schedule += [(25, 'rotate-backlot', 'map mp_backlot\n'), (35, 'active-backlot', 'bot_status\n'),
                     (55, 'rotate-strike', 'map mp_strike\n'), (65, 'active-strike', 'bot_status\n'),
                     (85, 'rotate-crossfire', 'map mp_crossfire\n'), (95, 'active-crossfire', 'bot_status\n'),
                     (115, 'rotate-crash', 'map mp_crash\n'), (125, 'active-crash', 'bot_status\n')]
    if a.scenario == 'burst':
        schedule += [(12, 'burst', None), (18, 'burst-admitted', 'bot_status\n')]
    if a.scenario == 'legacy':
        schedule += [(12, 'legacy', None), (18, 'legacy-completed', 'bot_status\n')]
    schedule.sort()
    prefix.with_suffix('.command.json').write_text(json.dumps(cmd, indent=2) + '\n')
    shutil.copy2(runtime / 'inputs.json', prefix.with_suffix('.inputs.json'))
    events = []
    start = time.monotonic()
    with prefix.with_suffix('.console.log').open('wb', buffering=0) as log:
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=log, stderr=subprocess.STDOUT)
        try:
            while proc.poll() is None and time.monotonic()-start < a.seconds:
                elapsed = time.monotonic()-start
                while schedule and elapsed >= schedule[0][0]:
                    at, label, command = schedule.pop(0)
                    proc.stdin.write(('echo BOT_CHECKPOINT ' + label + '\n').encode())
                    if command is not None:
                        proc.stdin.write(command.encode())
                        result = 0
                    else:
                        proc.stdin.flush()
                        if label == 'burst':
                            attempts = [subprocess.Popen(['docker', 'exec', name, '/runtime/handshake', '', f'127.0.0.{i}'],
                                        stdout=subprocess.PIPE, stderr=subprocess.PIPE) for i in range(2, 8)]
                            result = 0
                            for attempt in attempts:
                                out, err = attempt.communicate(timeout=10)
                                log.write(out + err)
                                result |= attempt.returncode
                        elif label == 'rcon-reject':
                            fixture = subprocess.run(['docker', 'exec', name, '/runtime/rcon_reject'], capture_output=True, timeout=10)
                            result = fixture.returncode
                            log.write(fixture.stdout + fixture.stderr)
                        elif label == 'legacy':
                            fixture = subprocess.run(['docker', 'exec', name, '/runtime/handshake', '', '127.0.0.2', '7'], capture_output=True, timeout=10)
                            result = fixture.returncode
                            log.write(fixture.stdout + fixture.stderr)
                        else:
                            password = 'wrong' if label == 'reject' else 'local-test'
                            fixture = subprocess.run(['docker', 'exec', name, '/runtime/handshake', password], capture_output=True, timeout=10)
                            result = fixture.returncode
                            log.write(fixture.stdout + fixture.stderr)
                    proc.stdin.flush()
                    events.append({'elapsed': round(elapsed, 2), 'label': label, 'exit_code': result})
                time.sleep(0.2)
            if proc.poll() is None:
                proc.stdin.write(b'bot_status\nsv_pure\nquit\n'); proc.stdin.flush()
            try:
                code = proc.wait(timeout=15)
            except subprocess.TimeoutExpired:
                subprocess.run(['docker', 'stop', '--timeout', '5', name], check=True, capture_output=True)
                code = proc.wait(timeout=15)
        finally:
            if proc.poll() is None:
                subprocess.run(['docker', 'stop', '--timeout', '5', name], capture_output=True)
                proc.wait(timeout=15)
    for filename in ['games_mp.log', 'qconsole.log']:
        source = home / 'mods/pml220' / filename
        if source.exists(): shutil.copy2(source, prefix.with_name(prefix.name + '.' + filename))
    text = prefix.with_suffix('.console.log').read_text(errors='replace')
    errors = re.findall(r'^.*(?:script (?:compile|runtime) error|Sys_Error:|Segmentation fault).*$', text, re.M | re.I)
    summary = {'scenario': a.scenario, 'duration': round(time.monotonic()-start, 2), 'exit_code': code,
               'script_or_fatal_errors': errors, 'events': events, 'evidence': str(prefix)}
    prefix.with_suffix('.result.json').write_text(json.dumps(summary, indent=2)+'\n')
    print(json.dumps(summary, indent=2))
    verdict = subprocess.run([sys.executable, str(Path(__file__).with_name('verify.py')),
                              str(prefix.with_suffix('.result.json'))])
    raise SystemExit(1 if code or errors or verdict.returncode else 0)


if __name__ == '__main__':
    main()
