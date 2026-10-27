# Final feature candidate: military names and native S&D

Status: candidate implementation, **not gameplay certified**. Feature freeze
resumes after this focused delivery; no unrelated development is authorized.
No production/homologation runtime, deployment policy or RCON bridge is changed.
Owner approval is required for merges and a separate supervised homologation.

## Ownership and behavior

Engine population management consumes Bot Warfare's existing root
`scriptdata/botnames.txt` convention when `bot_use_names=1`. Configuration owns
the 15-name military pool; the workspace copies it and includes its content in
the configuration fingerprint. Assignment happens only in `BotAddOne`, before
`SV_AddBotClient`. Existing bots and humans are never renamed. Round restarts
retain native client userinfo. Subsequent admissions take the first unused name,
including collision checks against humans after native name cleaning, ignoring
case. Missing, invalid, oversized or exhausted pools use unique numbered Promod
fallbacks. Name input is bounded to 8192 bytes and 31 ASCII display bytes per
line; overlong and unsafe lines are rejected rather than truncated. Blank lines
are ignored; allowed characters are letters, numbers, spaces, dots and hyphens.
Zombies uses its existing naming path. Changing the pool affects new bots only.

`bot_sd_objectives=1` starts the pinned Bot Warfare S&D routines after the
existing combat core's `bot_spawned` event. Enabling it midround takes effect
on the next spawn. Disabling cancels held input and outstanding navigation
within the 100ms goal watchdog; controllers remain idle/retry until the next
spawn. `bots_play_obj` stays zero because the stock all-gametype initializer and
its callback replacements are not installed.

Preparation extracts only S&D routines and their helpers. It removes the stock
preplant defender lookup of the dropped bomb, and reactions to remote enemy
plant/defuse activity. Navigation uses public sites and the announced planted
bomb; teammate carrier ownership remains normal. Bad paths have bounded waits
and the attacker retries another site. Promod exposes its existing defuse object
through a reference; native creation, callbacks, timers and outcomes are intact.
Carrier tests use authoritative `carryObject`, not Bot Warfare's absent flag.
Use input passes through the existing Bot Warfare adapter and native player
button path. Native Promod validates ownership, team, contact, health and the
full hold timer. Short renewable input leases release on interruption; death
and round end explicitly clear use. No production code teleports, grants bombs,
invokes plant/defuse callbacks, sets bomb outcomes or reads enemy carrier data.

Pinned inputs are unchanged: Bot Warfare v2.2.0 at
`7b52b462e40fa68287b9e54602e52da83b17766c`, Promod LIVE V2.20 EU and all
eight header hashes in `bots/dependencies.json`. Licensed extracted/generated
scripts stay private. Source terms and credits: [third-party-bots.md](third-party-bots.md).
The preserved PoC remains read-only.

## Evidence and remaining gates

Local engine build passes. Existing and focused parser/overlay Python tests,
native population policy, rotation and voting harnesses pass. Workspace packaging
and operation mocks are run without SSH or service changes. Hosted mandatory CI
must pass on final PR heads; existing workflows are retained without changes.

`tests/run_sd_native.py` creates a new loopback process and verifies pinned
Promod/header identities. Its native fixture uses **test-only positioning** to
exercise legitimate pickup, interrupted plant/defuse and real native completion.
Accepted Crash evidence: `/tmp/cod4x-sd-native-qakidgli/results.json` shows plant
5150ms, defuse 7100ms, both interruptions, carrier death/drop/recovery, death during defuse, native
round reset, pure=1 and all 12 requested names retained across the round. Strike
(`/tmp/cod4x-sd-native-tuz9t_ot`), Winter Crash (`4hrkqryt`) and Backlot
(`v4up0t8v`, with the same `/tmp/cod4x-sd-native-` prefix) also passed. It does not prove autonomous navigation or real-client gameplay.
Rejected runs are retained privately and are not qualification evidence.

The separate `--scenario navigation` fixture observes actual AI navigation/use,
with combat suppressed solely in the test fixture; no positioning is used.
Neither synthetic fixture certifies combat decisions, HUD, human bomb priority,
interruption under fire, every supported map or a full competitive match.
Admission collisions/overflow, bot administration,
Promod/Zombies gameplay regressions and the supported-map matrix must be recorded
before qualification approval. Independent Principal source architecture/security review approved draft review
on 2026-10-27; gameplay/qualification approval and final CI remain pending. Do not promote this
candidate based only on connected/active bots or prepared waypoint coverage.

## Rollback and freeze

Revert the focused engine, catalog and workspace changes together and rebuild
the prior reviewed artifact. Preserve the previous immutable artifact and config
hash for operational rollback. There is no data migration. Setting
`bot_sd_objectives=0`/`bot_use_names=0` stops new objective/name activation but
is not an approved replacement for exact-artifact rollback. No merges,
deployments, bridge activation or production promotion are performed here.
After approved merges, prepare one pinned homologation candidate, obtain owner
deployment approval, supervise real-client gameplay and exact-artifact rollback,
then request qualification approval before proposing production promotion.
