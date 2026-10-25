#!/usr/bin/env python3
"""Verify gameplay or admission evidence produced by run_local.py."""
import argparse
import json
from pathlib import Path
import re

EXPECTED = {
    'status': ('active', 0, 12), 'invalid-password': ('active', 0, 12),
    'human-priority': ('active', 1, 11), 'pause-human': ('paused-with-humans', 1, 0),
    'paused-backlot': ('paused-with-humans', 1, 0), 'resumed': ('active', 0, 12),
    'still-paused-empty': ('paused-awaiting-human', 0, 0), 'manual-resumed': ('active', 0, 12),
    'pause-without-kick': ('paused-awaiting-human', 0, 12),
    'paused-new-human': ('paused-with-humans', 1, 0), 'empty-transition-resumed': ('active', 0, 12)
}


def main():
    p = argparse.ArgumentParser()
    p.add_argument('result', type=Path)
    a = p.parse_args()
    result = json.loads(a.result.read_text())
    prefix = a.result.with_name(a.result.name.removesuffix('.result.json'))
    console = prefix.with_suffix('.console.log').read_text(errors='replace')
    game = prefix.with_suffix('.games_mp.log').read_text(errors='replace')
    checks = {'server_exit_zero': result['exit_code'] == 0,
              'no_gsc_or_fatal_errors': not result['script_or_fatal_errors'],
              'pure_enabled': 'pure=1' in console and 'pure=0' not in console,
              'eight_headers': 'Loaded 8 administrative IWD checksums' in console}
    checkpoints = {}
    current = None
    for line in console.splitlines():
        if line.startswith('BOT_CHECKPOINT '): current = line.split()[1]
        match = re.search(r'BOT_STATUS enabled=1 state=(\S+) humans=(\d+) connecting=\d+ bots=(\d+) ready=(\d+) pure=(\d+)', line)
        if match and current:
            checkpoints[current] = (match[1], int(match[2]), int(match[3]), int(match[4]), int(match[5]))
    if result['scenario'] == 'legacy':
        checks['initially_full_of_bots'] = checkpoints.get('status') == ('active', 0, 12, 1, 1)
        checks['legacy_reaches_update_path'] = 'Going from CS_FREE to CS_ZOMBIE for HandshakeFixture' in console and 'Resolving cod4update.cod4x.ovh' in console
        checks['bot_slot_reclaimed'] = 'A human player is connecting' in console
        checks['no_bot_induced_full_response'] = 'Server is full' not in console
        checks['offline_update_pending_normally'] = any(e['label'] == 'legacy' and e['exit_code'] == 3 for e in result['events'])
    elif result['scenario'] == 'burst':
        checks['initially_full_of_bots'] = checkpoints.get('status') == ('active', 0, 12, 1, 1)
        checks['six_humans_replace_six_bots'] = checkpoints.get('burst-admitted', ())[:3] == ('active', 6, 6)
        checks['six_handshakes_accepted'] = console.count('HANDSHAKE_REPLY connectResponse') == 6
        checks['no_full_rejection'] = 'Server is full' not in console
        checks['fixtures_passed'] = any(e['label'] == 'burst' and e['exit_code'] == 0 for e in result['events'])
    elif result['scenario'] == 'policy':
        for name, expected in EXPECTED.items():
            observed = checkpoints.get(name)
            # Round end legitimately clears readiness while the fill policy stays paused.
            checks[name] = bool(observed and observed[:3] == expected and observed[4] == 1
                                and (expected[0] != 'active' or observed[3] == 1))
        events = {event['label']: event['exit_code'] for event in result['events']}
        checks['invalid_password_rejected'] = events.get('reject') == 2 and 'Invalid Password' in console
        checks['full_bot_handshake_accepted'] = events.get('admit') == 0
        checks['empty_paused_handshake_accepted'] = events.get('admit-paused') == 0
        checks['no_bot_induced_full_response'] = 'Server is full' not in console
    else:
        classes = re.findall(r'PMBOT CLASS slot=(\d+) team=(allies|axis) class=assault', game)
        shots = re.findall(r'PMBOT FIRE slot=(\d+) weapon=ak47_mp', game)
        positions = {}
        targets = set()
        for match in re.finditer(r'PMBOT SAMPLE slot=(\d+) state=playing pos=\(([^)]+)\).*?enemy=(-?\d+) wp=(-?\d+)', game):
            if int(match[4]) >= 0: positions.setdefault(match[1], set()).add(match[2])
            if int(match[3]) >= 0: targets.add(match[1])
        checks['twelve_classes'] = len({slot for slot, _ in classes}) == 12
        checks['opposing_teams'] = {team for _, team in classes} == {'allies', 'axis'}
        checks['waypoint_movement'] = len([slot for slot, points in positions.items() if len(points) >= 3]) >= 2
        checks['target_acquisition'] = len(targets) >= 2
        checks['multiple_bots_fired'] = len(set(shots)) >= 2
        checks['promod_combat'] = bool(re.search(r'\bK;.*\[BOT\].*ak47_mp', game))
        checks['twelve_slots_filled'] = checkpoints.get('status') == ('active', 0, 12, 1, 1)
        if result['scenario'] == 'rotation':
            for name in ['active-backlot', 'active-strike', 'active-crossfire', 'active-crash']:
                checks[name] = checkpoints.get(name) == ('active', 0, 12, 1, 1)
            for mapname in ['mp_crash', 'mp_backlot', 'mp_strike', 'mp_crossfire']:
                checks['ready-' + mapname] = 'PMBOT READY map=' + mapname in game
    summary = {'scenario': result['scenario'], 'checks': checks, 'passed': all(checks.values()),
               'checkpoints': checkpoints}
    prefix.with_suffix('.acceptance.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps(summary, indent=2))
    raise SystemExit(0 if summary['passed'] else 1)


if __name__ == '__main__':
    main()
