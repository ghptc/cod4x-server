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
Vendor loadouts, ammunition, damage, zombie construction and wave spawning remain
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
Allied preparation declares exactly six overlays with hashes; packaging checks
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

- Engine unit suite: 68 tests, passed with one optional public-client checkout
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
  original assets and the exact six-overlay manifest.
- Separate architecture, gameplay, native-testing and independent-review agents
  participated. Final source review found no blocking issue; native evidence and
  operator qualification are distinct gates.

Earlier native runs remain preserved, including scriptadmin connection rejection
(`/tmp/btd-five-allies-q1yrx1ow`), headless transport/visibility problems
(`/tmp/btd-five-allies-ecze7vy_`) and an old-fixture wave-respawn expectation
(`/tmp/btd-five-allies-b2dxxb4n`). Failed runs are not qualification evidence.
