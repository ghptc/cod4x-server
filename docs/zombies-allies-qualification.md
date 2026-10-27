# Zombies allies compatibility gate (2026-10-27)

This is a test-only compatibility investigation, not delivery of five allied
soldiers. Production and existing prepared runtimes remain unchanged. Baseline:
engine protected master `dc11efa` (tree identical to Classic `4c3199e`), config
master `9fd5c9d`. Engine executable SHA-256:
`ea3d0097320095f7d9080248b6f4ea63a65d646a3bd10f68794a8756a6368918`.
BTD assets are pinned in `tools/btd/dependencies.json`; Bot Warfare v2.2.0 is
`7b52b462e40fa68287b9e54602e52da83b17766c`. No extracted source is committed.

## Why the Promod adapter cannot be enabled

Independent source review identified these constraints:

- Both BTD PeZBOT and Bot Warfare own `level.waypoints`/`waypointcount`.
  Loading the existing Promod navigation initializer can corrupt zombie AI.
- Bot Warfare scans human/player enemies even when a script target is set.
  Dedicated zombie targeting is required. BTD already rejects player-to-player
  damage, but that alone does not prevent firing at humans.
- BTD survival checks and wave scaling count player entities. Allies must not
  keep a game alive after human elimination or silently increase wave scaling.
- Native population creation currently requires S&D. The Promod adapter also
  depends on Promod class/loadout functions absent from BTD.

A new ally adapter must preserve vendor callbacks, namespace its own navigation,
prove native bullet combat, exclude humans from targeting, and qualify human
elimination, respawn and wave scaling before enabling a default population.
The attributed native PoC passed at `/tmp/btd-death-regression-fk40my4r`
with bullet damage, zombie melee damage and no script errors. It checks combat with one native client placed near an
actual vendor zombie. It uses no synthetic zombie damage notifications, weapon
grants or Bot Warfare initializer. A fixture-only damage observer delegates to
the vendor player callback. It does not prove navigation, five-client behavior,
human protection, weak difficulty balance, cleanup, or playable waves.

## Existing shared administration contract

The inspected protected implementation is `src/sv_bot_manager.c` and
[bot administration](bots.md). All counts are strict decimal `0..12`.

| Command | Power | Current behavior |
| --- | --- | --- |
| `bot_add <count>` | 80 | Add up to capacity/limit if ready; zero is a no-op |
| `bot_kick <count>` | 80 | Remove up to count and pause fill; zero is a no-op |
| `bot_kickall` | 80 | Pause first, then disconnect all native bots |
| `bot_killall` | 80 | Normal suicide for living active native bots; keep registrations |
| `bot_status` | 20 | Human, connecting, bot, readiness, limit and difficulty counts |
| `bot_limit <count>` | 80 | Change limit and enforce reductions, including zero |
| `bot_difficulty <fixed|mixed|1..7>` | 80 | Existing seven Bot Warfare profiles |
| `bot_autofill <0|1>` | 80 | Pause or explicitly resume population management |

Access uses existing authenticated RCON, local console or authorized game admin
permissions. There is no existing single-bot kill command. A compatible counted
kill extension needs a separate implementation and behavioral review; no alias
or second interface has been added. Promod pause state currently survives maps
and resumes after the last human leaves. Zombies needs its own configured
current-map kick pause and next-map restoration semantics, preserving Promod.
The engine's existing native bot eviction on human admission is reusable.
None of these commands has been certified for a new Zombies ally adapter.

## Voting and map transitions

The focused config change enables native votes only for rotation maps, with
`g_voteCooldown=5`, full human abstention weight and no kick/restart/gametype
votes. Existing engine handlers exclude bots from initiation, casting and quorum.
`/callvote map mp_crash` selects the next map; `/callvote map_rotate` schedules
an immediate switch using the existing engine path. This preserves Promod
semantics and does not manually manipulate BTD wave globals.

Native harness tests exercise a war rotation with five bots, rejected Killhouse,
human-only majority, queued transition execution exactly once and cooldowns
5/30/120. They are run by the existing mandatory Linux check. The private BTD
integration additionally checks catalog vote settings at startup, all supported
maps and restart; it does not simulate graphical vote UI or a vote during combat.
The config's existing Configuration check now executes its mode policy test.

## Killhouse is not qualified

Installed `mp_killhouse.ff` and `mp_killhouse_load.ff` exist. The pinned BTD source
has 25 explicit spawn positions. Native startup nevertheless fails before combat:
`svr/pezbot.gsc:1928`, cannot cast undefined to string, called by
`LoadStaticWaypoints()` at coordinate conversion line 2029. The disposable
negative control requires this exact stack; other errors fail the reproduction.

Evidence: `/tmp/btd-death-regression-urff_pp8/results.json` records
`waypoint_defect=true`. This expected-failure test does **not** qualify Killhouse.
Keep it outside rotation and the vote allowlist. Zombie navigation/attacks,
allied combat, wave progression and supervised gameplay on Killhouse remain
unvalidated; do not repair or invent waypoint coordinates without qualification.

## Reproduction and delivery gates

```sh
python3 tests/run_map_voting.py
python3 tests/run_btd_regression.py --runtime PRIVATE_RUNTIME --game GAME_DATA --binary bin/cod4x18_dedrun --scenario allies --fixed
python3 tests/run_btd_regression.py --runtime PRIVATE_RUNTIME --game GAME_DATA --binary bin/cod4x18_dedrun --scenario allies --map mp_killhouse --fixed --expect-waypoint-defect
```

Every native runtime test makes a new private directory and retains the inputs.
Preserve the Classic evidence listed in [Classic qualification](zombies-classic.md).
All-map voting policy integration: 89/89 checks, evidence
`/tmp/cod4-btd-qualified-18naigad`. Existing engine unit suite: 44 tests, success with one
optional public-client checkout skipped; native vote and rotation tests passed.
Sandbox execution denies sockets/32-bit syscalls; authorized local reruns passed.

BTD lifecycle with proposed voting policy passed at
`/tmp/btd-death-regression-uh2phcph`: native death, respawn, zombie spawn/death,
wave two, two admission handshakes and Strike/Crash map transitions, no script
errors. These transitions were administrative, not votes during combat.
Fresh pinned Promod preparation passed 53/53 integration checks at
`/tmp/cod4x-promod-integration-6yoxi62_`, including ready-up, voting, match/map
progression and administration. An earlier run against an older prepared runtime
failed five ready-up assertions (`/tmp/cod4x-promod-integration-072aw2aj`);
its ready-up overlay hash differs from current preparation. Do not reuse that
stale-runtime result as current regression evidence. Existing inputs were retained.
Mandatory Linux and Configuration CI passed on the initial PR revisions;
check final PR heads before merge.

Full five-ally creation, distribution, human slot reservation under load,
command lifecycle, human-only ready-up, wave/death safety, restoration and balance
remain required work. Do not represent this test PR as that implementation.
Require independent review and green mandatory CI before owner merge. Existing
active master ruleset requires Linux; a local review is not a GitHub approval.
Supervised graphical gameplay and explicit operator approval remain necessary
for any deployment or production promotion. No remote/runtime changes are made.
Rollback of voting is a revert of the focused config PR through the existing
reviewed workflow; test-only engine changes do not alter runtime behavior.
