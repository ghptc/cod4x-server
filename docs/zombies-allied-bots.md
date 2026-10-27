# Native allied soldiers for Zombies Classic

Protected engine baseline: `24f5cfabfb2dabacfb154b3430c06607c9a19897`
(PR #24), configuration master
`9f0fa1a0b0c1483ea20a89fc7beaf26c9b7c2201`, workspace master
`da5360d`. PRs #20/#21/#23/#24 provide the death/spawn fixes, Classic policy,
Killhouse navigation and prepared map declaration. Existing Promod command
behavior includes PR #12. The earlier single-bot investigation on
`feat/zombies-allies-qualification`, evidence
`/tmp/btd-death-regression-fk40my4r`, is preserved; it does not qualify this work.

## Integration

Preparation is explicitly opt-in: add `--allies` to `tools/btd/prepare.py`.
Baseline preparation remains available. Allied preparation requires the companion
workspace asset-validation change; older packaging rejects its additional code.
No original inputs are edited or proprietary source files committed.

The independent authored controller uses native client inputs and reads BTD's
waypoint graph. It never initializes Bot Warfare or writes enemy pathfinding
state. Bots follow living human survivors and target only living vendor zombies.
First-use ammo-drop eligibility is initialized only when absent for any survivor.
The vendor pickup and grace-period cooldown still perform restocking. Both ammo
cooldown threads cancel on disconnect before resuming into a removed entity. Vendor loadouts, ammunition,
damage, zombie construction and wave spawning remain
authoritative. There are no scripted enemy damage/kill shortcuts.

The native manager gates creation on the exact BTD mod, `war`, pure mode and
script readiness. `btd_allies_enable=1` and `btd_allies_limit=5` are defaults;
a baseline runtime without the allied overlay never signals readiness. Explicit
`btd_allies_enable=0` disables the controller. Promod retains its existing
`bot_enable`, twelve-client fill policy and difficulty settings.

Five default allies cycle through three easy and two medium profiles. Easy bots
have a 1.4-second acquisition delay, 1-second shot interval and 65-unit horizontal
aim error; medium uses 0.9 seconds, 0.7 seconds and 40 units. Both use short firing
pulses and wait for native turning before checking human obstructions. These are
implementation settings, not measured balance against competent humans. The
vendor's unconditional player-versus-player damage protection is pinned and
preserved independently of aim checks.

Human-only overlays cover wave population calculations, stock survivor counts
and vendor elimination monitoring. Native allies remain combat targets for
zombies but cannot sustain a round after the last human survivor dies. Native
capacity accounting includes connected humans; allies yield public slots through
the existing validated connection path.

## Administration

Existing command names and strict decimal count range `0..12` remain unchanged:

| Command | Permission | Behavior |
| --- | --- | --- |
| `bot_add count` | 80 | Add within current limit and capacity |
| `bot_kick count` | 80 | Remove native allies and pause Auto-Fill |
| `bot_kickall` | 80 | Remove allies and pause before disconnect callbacks |
| `bot_killall` | 80 | Normal death callback for living native allies; keep connections |
| `bot_status` | 20 | Population, readiness, fill state and profile mode |

Enemies are script entities, never native bot clients. These commands do not
affect humans or enemy zombies. No single-bot kill command is added. Bots killed during an active wave wait for the vendor joining window; killing
them does not bypass Zombies respawn rules. Existing
`bot_autofill 1` explicitly resumes filling; the prior last-human-leaves pause
policy is retained across maps. `bot_limit` selects the BTD-specific limit in
BTD, leaving Promod's limit untouched. Status reports profile mode, not measured
per-profile population.

## Provenance and repeatable validation

Original fastfile SHA-256 remains
`50911fdd0273b50e26983723619881acfaed4aa65f4d91a799a341464c2224a6`.
All private source identities are pinned in `tools/btd/dependencies.json`.
Allied preparation declares exactly seven overlays with hashes; packaging checks
those identities and rejects undeclared source files and symlinks. The existing
three-overlay recipe, licenses, original configuration and eight administrative
headers remain preserved. `sv_pure=1` stays mandatory.

```sh
make -j4
python3 -m unittest discover -s tests -p 'test_*.py'
gcc -Wall -Wextra -Werror tests/test_bot_policy.c -o /tmp/allied-bot-policy
/tmp/allied-bot-policy
python3 tests/run_map_rotation.py
python3 tests/run_map_voting.py
python3 tests/run_btd_allies.py --runtime PRIVATE_PACKAGED_RUNTIME --game GAME_DATA --binary bin/cod4x18_dedrun
python3 tests/run_btd_navigation.py --runtime PRIVATE_BASELINE_RUNTIME --game GAME_DATA --binary bin/cod4x18_dedrun
python3 tests/run_btd_integration.py --runtime PRIVATE_BASELINE_RUNTIME --game GAME_DATA --catalog CONFIG_CHECKOUT --workspace WORKSPACE_CHECKOUT
python3 tests/run_promod_integration.py --runtime FRESH_PROMOD_RUNTIME --game GAME_DATA --catalog CONFIG_CHECKOUT --workspace WORKSPACE_CHECKOUT
```

The allied runner creates disposable loopback processes. Synthetic human clients
complete actual UDP admission and are classified as native humans. Its test-only
plugin enters them into the world, acknowledges reliable traffic and supplies
headless pure/profile completion; this does not test graphical client pure
verification or profile upload. The fixture raises only human health for sustained
observation and accelerates grace/initial-wave size. It does not grant ammunition
or fake enemy damage. Full private runtime logs stay outside Git.

## Delivery and rollback

Owner review and manual merge require green existing mandatory checks. No new
workflow, deployment system, image publication or monitoring is introduced.
After approved merges, prepare a fresh private artifact using the exact reviewed
engine and packaging revisions. Deployment requires separate operator approval;
qualification requires supervised graphical gameplay on homologation, including
five allies together, human kill dominance, navigation/obstacles, ammunition,
death/respawn, all-human elimination, waves, reconnection and map transitions.
Synthetic tests cannot certify those balance and graphical-client gates.

Production remains on its known-good Promod artifact. No production, AWS, Bard,
or existing running service is changed by this work. Roll back through reviewed
reverts or reprepare without `--allies`; retain accepted death/spawn, Classic and
Killhouse repairs. Any running-service rollback needs operator authorization and
the exact previously approved artifact. Preserve the old PoC and all failed and
successful qualification directories.

## Baseline verification in this change

The pre-commit native executable SHA-256 is
`2aac8c013b234a4dee8272bcb8e3fc09f5df3e35a7f8f936ccf0bb464e607b70`.
Existing linker text-relocation warnings remain; compilation succeeds.

- Engine unit suite: 70 tests, passed with one optional public-client checkout
  skipped (`COD4X_CLIENT_SOURCE` unset). Native execution requires an unsandboxed
  local test process because sandbox restrictions cause SIGSYS/socket failures.
- Native population policy, linked map rotation and map voting suites passed.
- Fresh Promod runtime: 53/53 checks, including bot administration and maps,
  `/tmp/cod4x-promod-integration-fi4rcfpt/results.json`.
- Original BTD preparation: 73/73 checks across all 16 maps and restart,
  `/tmp/cod4-btd-qualified-9ci8h2bm/results.json`.
- Existing native Killhouse suite: 12/12,
  `/tmp/btd-navigation-pxn0vvrh/results.json`, including native enemy navigation,
  melee, 20 bullet hits/five credited kills, wave progression and transitions.
  This baseline suite does not independently certify allied obstacle traversal.
- Companion packaging: all 50 Python tests and the full mocked Operations suite
  passed. Actual new private allied preparation plus packaging passed, retaining
  original assets and the exact seven-overlay manifest.
- Separate architecture, gameplay, native-testing and independent-review agents
  participated. Final source review found no blocking issue; native evidence and
  operator qualification are distinct gates.

Earlier native runs remain preserved, including scriptadmin connection rejection
(`/tmp/btd-five-allies-q1yrx1ow`), headless transport/visibility problems
(`/tmp/btd-five-allies-ecze7vy_`) and an old-fixture wave-respawn expectation
(`/tmp/btd-five-allies-b2dxxb4n`). Failed runs are not qualification evidence.

A further rejected run, `/tmp/btd-five-allies-kzstcxhj`, exposed missing
first-use vendor ammo-drop eligibility during native capacity refill; the
undefined-only pickup initialization above addresses that failure. A subsequent
removed-player cooldown error required the pinned seventh ammo safety overlay.


## Final allied native qualification

**52/52 checks passed** at
`/tmp/btd-five-allies-1efma7z3/results.json`, with no script errors and both
process shutdowns returning zero. The source audit at that same directory matches
all seven production overlays after removing exactly the two documented test-only
injections, and matches the observer fixture. Its dependency-lock SHA-256 is
`b145c6dcc94dfe2486fb8c0c9e8e165c387df7b321e10fcfa04540557882bb76`.

- Five default living allies, exactly three easy/two medium; no human/no wave.
- All five original client slots fired actual rounds at live vendor zombies.
  Combat snapshot: 13 attributed native allied bullet hits, 140 vendor melee
  damage events against allies, zero allied kills versus eight synthetic-human
  kills, and no allied damage to humans. Six positive/blocked shot-guard trials.
- Five actual administrative deaths and normal grace respawn; live-wave deaths
  respect the joining window. Kick, kickall pause, explicit re-add, empty killall,
  invalid counts, authenticated/denied RCON, and human preservation passed.
- Full capacity: 11 allies plus one actual human; a second human connection
  reclaimed one slot, leaving ten allies and two humans. Reconnection passed.
- Active wave three: ten living allies and two living humans before suicide;
  actual vendor end event had ten living allies and zero living humans.
- Killhouse→Crash→Killhouse, restart with five living allies, pure mode and eight
  administrative headers passed. Dynamic mode produced exactly 28 zombies for
  one human plus five allies, rather than the 58 that six counted players imply.
- Native horizontal following displacement from grace respawn to autonomous
  observation: slot zero 369.198 units; slot four 341.192 units. This does not
  qualify a dedicated allied obstacle/BFS route or all-map allied gameplay.

Runner SHA-256:
`c90818a77734a420d7130dd89e473e9ddc9cd8ef4e6dea63f86d7e4d865f0e06`;
observer fixture:
`0192315dd0eb0fc1ab0ee57413e1b5c6f1e06fd191e5fc58bd6f5a14725f6a34`.
The earlier seven-overlay run `/tmp/btd-five-allies-km2cjkwf` remains **50/52,
failed**: its assertions raced legitimate grace spawning and human respawn.
The accepted runner waits for normal spawn ticks and requires an active wave
before elimination; no game state or damage was fabricated to satisfy them.

Implementation is [engine PR #25](https://github.com/ghptc/cod4x-server/pull/25);
packaging is [workspace PR #17](https://github.com/ghptc/ec2-workspace/pull/17),
head `c118e84984f8a2351c75756fdc6e6a215732a3b2`. Linux and Windows CI passed
implementation head `58ac058b694ec687d2607b463fbc85a6a974921e`; workspace
Operations passed its final head. The final evidence/runner commit must retain
green mandatory Linux CI before owner merge. No merge or deployment is authorized
by these synthetic results; operator-supervised balance and real-client
qualification remain outstanding.
