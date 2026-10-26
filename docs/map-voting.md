# Player map voting

Final gameplay backlog addition: player-initiated, human-only native next-map
voting. Implemented for local qualification; real graphical client acceptance
and owner review remain before rollout. No deployment is part of this feature.

## Inspection and decision

Inspected canonical engine master `8bc5f3ed2c750b199bb084de350ef1cf2687eb9d`
and the hash-locked Promod LIVE 2.20 input in `bots/dependencies.json` before
implementation. Relevant native paths are `Cmd_CallVote_f` in `src/g_sv_cmds.c`,
`Cmd_Vote_f` in `src/g_cmds.c`, `CalculateRanks`/`CheckVote` in
`src/asmsource/_g_main_mp.asm`, and `ExitLevel` in `src/g_sv_main.c`.

Native `g_allowVote=1`, `g_oldVoting=1` and `g_voteAllowMap=1` already offer
unprivileged next-map votes restricted to the rotation. Other native allow cvars
can disable kick, restart, gametype and immediate rotation votes. However:

- Rotation membership used substring matching, accepting partial map names.
- Only semicolons were rejected before constructing map/gametype console text.
- Bots were not excluded from casting or the CalculateRanks electorate.
- `g_voteMaxVotes` is a per-client limit, not a timed cooldown.
- Calling another vote could execute a pending passed vote early.
- The native yes parser inspected the wrong character for uppercase/numeric yes.
- Promod's `promod/comp.gsc` unconditionally resets `g_allowVote` to zero at
  competition initialization, including the canonical `match_mr12_pb` mode.

Thus a configuration-only change in `cod4-config-server` cannot meet the
requirements. This patch keeps the native tally, UI/configstrings, majority,
execution delay, next-map cvar and automatic rotation. It adds validation and a
human electorate refresh immediately before the existing assembly majority check;
it introduces no alternate vote service, client protocol or GSC voting framework.

## Opt-in setup (local preparation only)

Use the existing verified private preparation inputs with
`tools/bots/prepare.py --allow-map-voting` in addition to the usual required
arguments. This derives a private `promod/comp.gsx` with exactly the one
`setDvar("g_allowVote",0);` statement removed. Unknown or ambiguous input fails
closed. All other competition rules remain byte-for-byte unchanged. Original
assets and integrity headers are unchanged and no proprietary script is committed.
The manifest records `map_voting_policy_overlay`. Repreparing without the flag
removes this overlay and restores the original restriction.

Execute `config/player-map-voting.cfg` before loading the first map in that
prepared runtime, after the canonical mode CFG. The file enables only next-map
votes: 30-second ballot, strict human majority (abstentions count against passing),
two calls per player per native session, and 120 seconds between accepted vote
calls server-wide. The cooldown range is 30–900 seconds and persists across map
changes in the same server process. Invalid calls consume neither quota nor
cooldown. New calls are rejected during a ballot and during its native 3-second
passed-vote execution delay. Allow cvar changes are read on every new call.

The mode's `sv_mapRotation` remains the allowlist; do not copy a second map list.
The supported rotation syntax is whitespace-separated key/value pairs, such as
`gametype sd map mp_crash gametype sd map mp_strike`. Map identifiers must contain
only ASCII letters, digits and underscores, be shorter than 64 bytes, and exactly
match a `map` value. Missing/extra arguments, prefixes, paths, line breaks,
quotes and console metacharacters are rejected. The administrator's native
`g_voteAllowMap=2` remains available outside this rotation-only profile.

## Exact player console commands

For the current canonical Promod rotation:

```text
/callvote map mp_crash
/callvote map mp_strike
/callvote map mp_crossfire
/callvote map mp_backlot
/vote yes
/vote no
```

The slash is the CoD4 client console command prefix. Native `vote y`, `vote 1`,
`vote n` and `vote 0` aliases also work; yes/no letters are case-insensitive.
Map identifiers match rotation spelling exactly. The caller automatically votes
yes. Each eligible player can cast once. A successful ballot sets
`g_votedMapName` after the native execution delay; it selects the next map when
the current match ends. It does **not** interrupt the current match. Ordinary
rotation resumes after that selection is consumed by native `ExitLevel`.

Eligible clients have completed native admission into `CS_ACTIVE`, are
`CON_CONNECTED`, and are human non-spectators. This uses the server's existing
client authentication/admission policy; it adds no RCON, administrator power or
new account requirement. Bots and spectators can neither call nor cast votes and
are absent from the majority denominator. Already-cast human ballots retain the
native disconnect semantics; this patch does not introduce identity tracking or
reconnect-proof ballot persistence.

In this profile players cannot call `map_rotate`, `map_restart`, `typemap`,
`g_gametype`, kick or arbitrary console commands. Existing authenticated admin
`map`, `map_rotate`, restart and RCON controls keep their native privileges and
behavior. Set `g_allowVote 0` to reject further calls. To fully roll back, prepare
without `--allow-map-voting`, omit the opt-in CFG and use the previously qualified
engine artifact through the normal owner-controlled workflow.

## Validation and limits

Run `python3 tests/run_map_voting.py` with GCC multilib and NASM. It compiles the
production native handlers and extracts the exact production `CheckVote` assembly
body into an isolated executable with mocked game/network I/O. It covers accepted
map selection, successful/failed ballots, ties/abstentions, one/two/three humans
with ten bots, bot-only rejection, duplicate/invalid ballots, aliases, spectators,
clients not yet active, quota, disabled voting, concurrent and pending votes,
cooldown boundaries, injection, partial maps and maps outside rotation.

Run `python3 -m unittest discover -s tests -p 'test_*.py'` for overlay, integrity,
FPS and existing PB policy tests. The map-vote overlay tests prove that only the
known prohibition is removed and reject unknown/duplicated source. These are
native unit/integration tests, not a real-client gameplay certification.

Before owner-approved rollout, qualify the prepared private overlay across a
match end and map change with authenticated real clients, both human-only and
bot-filled servers. Verify vote HUD/results, unchanged administrative map
controls and continued automatic rotation. Neither EC2 nor any running service
is changed by these tests.

Local qualification on 2026-10-26: `make -j4`, the native vote harness, all 14
Python regression tests and `git diff --check` passed. Fresh private preparation
used the locked Promod/Bot Warfare/header inputs. On both Crash and Strike in
`match_mr12_pb`, voting stayed enabled with rotation-only maps and the 120-second
cooldown; pure remained 1 and all eight administrative headers loaded with no
script errors. Repreparing without the opt-in flag removed the overlay, recorded
false in the manifest, and restored Promod's voting prohibition on both maps.
These disposable local runtime checks used zero clients, exercised administrator
map changes, and left all services untouched. Full build retained the inherited
PIE/text-relocation linker warnings. Private logs remain outside Git.
