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
calls server-wide. This standalone example is not the canonical managed Promod
policy described below. The cooldown range is 1–900 seconds and persists across map
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

## Canonical voting configuration audit (2026-10-26)

Promod policy belongs to `ghptc/cod4-config-server:modes/promod/server.cfg`,
inspected at `cee09c9001937170bcd521b75a43d1f610978f1a`. It requests five seconds.
The previous engine registration accepted only 30–900 seconds, rejecting this
valid policy. Lower only the engine minimum to one second; retain the existing
120-second default and 900-second maximum. One second keeps a positive timed
guard while allowing short mode policies. No Promod-specific engine branches
or copied mode policy values are needed. Managed packaging does not execute the
optional legacy example CFG above.

All native voting registrations were inspected in `Init_CallVote` in
`src/g_sv_cmds.c` and `G_RegisterCvars` in `src/g_sv_main.c`:

| Cvar | Engine default; domain | Consumption |
| --- | --- | --- |
| g_voteCooldown | 120; integer 1–900 seconds | Accepted call sets process-wide deadline |
| g_voteTime | 30; integer 10–90 seconds | Ballot deadline, native CheckVote |
| g_voteBanTime | 15; integer 1–240 minutes | Successful kick command |
| g_voteMaxVotes | 2; integer 1–10 | Caller session quota |
| g_voteKickMinPlayers | 5; integer 0–14 | Kick eligibility threshold |
| g_voteAllowMap | 1; integer 0–2 | Disabled / rotation only / any map |
| g_voteAllowMaprotate | true; boolean | Immediate rotation permission |
| g_voteAllowKick | true; boolean | Kick permission |
| g_voteAllowGametype | true; boolean | Gametype and typemap permission |
| g_voteAllowRestart | true; boolean | Restart permission |
| g_voteVoteGametypes | empty; string | Optional gametype allowlist |
| g_allowVote | true; boolean | Native vote enable gate |
| g_oldVoting | true; boolean, archive | Native versus script vote dispatch |
| g_voteAbstainWeight | 0.5; float 0–1, archive | Native majority abstention weight |
| g_votedMapName / g_votedGametype | empty; strings | Pending selection consumed/cleared at ExitLevel |

Every other explicit canonical value fits its existing domain. All other bounds,
defaults, map validation and gametype allowlist handling remain unchanged.
Selection strings are native state, not policy.

`SV_Init` registers callvote cvars before startup CFG execution. `Cmd_Exec_f`
inserts file contents at the front of the command buffer, so nested private
execs finish before the next startup exec. In `ghptc/ec2-workspace` at
`45d0aaf65aae95c1e2699bde5aac7a1dcd2d36e5`, `scripts/modes.py` copies canonical
files; `scripts/runtime.py` orders shared → private (including nested execs and
inherited sets) → canonical mode → native map rotation. No companion changes
are needed.

`Cvar_SetVariant` rejects out-of-domain writes, retaining the last valid value;
it does not clamp runtime CFG writes to the minimum. An invalid final mode value
can therefore leave an earlier private value effective. `Cvar_Register`
separately handles user-created pre-registration values and clamps during
registration. Both mechanisms remain intact. Callvote cvars are not latched.
Permission flags refresh on every call; duration, quota and cooldown are read on
each call. Updating cooldown affects the next accepted call, not an existing
deadline.

Map initialization re-registers game cvars while preserving current values;
callvote registration belongs to server initialization. The static cooldown
uses server time and survives map changes. A process restart resets the deadline
and session quota, then reapplies CFG precedence. Maps need no additional CFG
execution or policy copies.

The locked Promod fastfile contains one direct voting policy write:
`setDvar("g_allowVote",0);` in competition initialization. Existing preparation
with `--allow-map-voting` removes exactly that statement and rejects unexpected
or duplicate input. Packaging requires this verified overlay when voting is
enabled. No other direct voting-policy writes were found in that fastfile.
Original assets, hashes and integrity headers remain untouched.

The global cooldown starts only on accepted calls. Human-only eligibility,
per-session quota, ballot/pending-execution exclusion, permissions, validation
and majority calculation remain in the existing native implementation.

Reproduce on a freshly prepared private runtime using `bots/dependencies.json`
(Promod LIVE 2.20 and Bot Warfare `7b52b462e40fa68287b9e54602e52da83b17766c`)
with `--allow-map-voting`:

```sh
python3 tests/run_map_voting.py
python3 tests/run_vote_config.py --runtime /path/to/prepared-runtime \
  --game /path/to/game --catalog /path/to/cod4-config-server \
  --workspace /path/to/ec2-workspace
python3 tests/run_promod_integration.py --runtime /path/to/prepared-runtime \
  --game /path/to/game --catalog /path/to/cod4-config-server \
  --workspace /path/to/ec2-workspace
```

The config test copies inputs to a new temporary directory and uses loopback-only
processes. Test-only mode variants cover 5/30/120, missing configuration,
1/900 and invalid -1/0/901 across startup, same-map restart, map transition and
fresh processes. A conflicting nested private value loses to valid canonical
values; invalid writes retain the preceding valid value. It also checks all
other explicit canonical voting settings after transitions, runtime updates,
pure and eight headers. Gameplay tests use synthetic humans on real entities;
they do not certify graphical UI. Native tests exercise the exact cooldown
boundary for 5/30/120 seconds.

Rollback: revert this engine change and rebuild through the owner-controlled
workflow. The old engine will again reject canonical five-second policy.
Neither companion repository nor runtime assets need reverting. No deployment
is included.

Local qualification used engine base `75bb0f93201b442baaea55d388d5746a129fb2bb`.
Dependency lock SHA-256:
`a958f7fa4fd8d7165c01701e1a1c6e5180ec837ae4fc92dbe3fd7b4c2463ff93`.
Tested binary SHA-256:
`bbb66702d9c5dce730eb080f2d0847a5ba7f4e4be313b2515845e8598edf0397`.
All 180 config assertions passed in
`/tmp/cod4x-promod-integration-pfsqq32p/results.json`, including ten fresh
processes, three map lifecycle observations per process and all runtime bounds.
Missing configuration yielded 120; invalid final CFG values retained the valid
private 900; canonical 5, 30 and 120 overrode private 900 exactly. The native vote
harness passed, the Python suite passed 28 tests with one existing skip, and
workspace mode/precedence tests passed all 21 tests. Full build passed with the
inherited PIE/text-relocation warnings. Native 32-bit/UDP tests required execution
outside the syscall-restricted sandbox. Full logs and all proprietary inputs stay
outside Git; existing runtimes, production, homolog, EC2 and Bard were untouched.
The final real gameplay regression passed all 53 checks in
`/tmp/cod4x-promod-integration-5p1yqff4/results.json`: live calls rejected before
five seconds and accepted afterward, bot call/cast exclusion, human majority,
quota/permissions via the native harness, voted match-end selection, normal round
retention, all 21 installed maps, process restart and authenticated administrative
controls. Its policy was the unmodified canonical CFG, with no cooldown override.
