# Zombies Classic qualification

## Decision log — 2026-10-27

- Fetched engine protected master `db09ce3807cc4a7334bf6477b90f552876c9501c`.
  PR #20 is merged, including the undefined death-inflictor field guard and
  missing zombie spawn-angle initialization. Keep both private source overlays.
- Workspace PR #15 is merged at
  `6c5b4b3a0ff92d2898a179904335c5c85e8863ee`. RCON activation remains a separate
  authorization/qualification gate; this change does not enable it.
- Config master was `8fc7c3d16e52e76750e8f3604847b8e01abd18b9`.
  [Config PR #12](https://github.com/ghptc/cod4-config-server/pull/12) changes
  only existing Zombies policy values: `btd_anticamp=0` and
  `btd_msg2="^7Server admins are ^4pitta"`. Original message wording, rotating
  message implementation, name color, and mod credits remain intact.
- Inspected verified private plaintext GSC: `_anti_camp_time.gsc` starts its
  punishment timer only for values 2/3; `_anti_camp_teleport.gsc` creates map
  exclusion triggers only for 1/3. `_initialize.gsc` calls both dispatchers.
  Zero suppresses both before they start. No engine changes, geometry bypass,
  new commands, or zombie balance changes are needed.
- Preserve original assets and all eight integrity headers through the existing
  locked preparation and workspace packaging pipeline. Never commit extracted
  scripts or generated runtimes. `sv_pure=1` remains mandatory.

## Repeatable checks

Use a newly prepared private runtime packaged by workspace master against the
reviewed config checkout. See [death/wave regression](btd-death-regression.md)
for preparation constraints and existing lifecycle reproductions.

```sh
python3 -m unittest discover -s tests -p 'test_*.py'
python3 tests/run_btd_regression.py --runtime PRIVATE_RUNTIME --game GAME_DATA --binary bin/cod4x18_dedrun --scenario classic --fixed
python3 tests/run_btd_regression.py --runtime PRIVATE_RUNTIME --game GAME_DATA --binary bin/cod4x18_dedrun --scenario classic --fixed --classic-control timer
python3 tests/run_btd_regression.py --runtime PRIVATE_RUNTIME --game GAME_DATA --binary bin/cod4x18_dedrun --scenario classic --fixed --classic-control teleport
python3 tests/run_btd_regression.py --runtime PRIVATE_RUNTIME --game GAME_DATA --binary bin/cod4x18_dedrun --scenario lifecycle --fixed
python3 tests/run_btd_integration.py --runtime PRIVATE_RUNTIME --game GAME_DATA --catalog CONFIG_CHECKOUT --workspace WORKSPACE_CHECKOUT
```

Classic uses the actual vendor timer dispatcher, checks for exclusion triggers,
and holds a synthetic player stationary at a vendor-blocked elevated Crash
position beyond an accelerated timeout. Independent negative controls restore
each original mechanism and must detect it. They test timer activation and
teleport-trigger creation, not every punishment or every map location.
The integration runner injects obsolete nested private camping/message values
and requires canonical policy at startup, every supported map, and restart.
The original lifecycle and Promod integration remain separate required checks.

## Local evidence

Engine build `make -j4` passed from the engine master above; tested executable
SHA-256 `ea3d0097320095f7d9080248b6f4ea63a65d646a3bd10f68794a8756a6368918`.
Config head `51a5286d08081e115088a5cf3d082ad6bf283dc4` passed its existing
Configuration check and 22 catalog tests. No original input bytes were edited.

- Python/native unit suite: 44 tests, success with one optional public-client
  checkout test skipped (`COD4X_CLIENT_SOURCE` unset). Sandboxed native execution
  was blocked by SIGSYS; the authorized unsandboxed rerun passed.
- Classic native VM: passed, `/tmp/btd-death-regression-beqflkln`.
  Timer and teleport negative controls detected their restored mechanisms,
  `/tmp/btd-death-regression-ebw3iwns` and
  `/tmp/btd-death-regression-hfrxj8_o`; no script errors in these runs.
- BTD all-map integration: 71/71 checks, all 15 maps and restart,
  `/tmp/cod4-btd-qualified-iwscbz7o`, against workspace master above. Checks
  include canonical configuration precedence, eight headers, pure mode, UDP
  administration, denied mode activation, and clean shutdown.
- Fixed lifecycle passed at `/tmp/btd-death-regression-uzdhldmv`: death callback,
  respawn, vendor zombie spawning/death handlers, wave two, two UDP admission
  handshakes and Strike/Crash transitions. Fixed expression passed at
  `/tmp/btd-death-regression-tdv5m0d3`; the original missing-field expression
  defect was reproduced at `/tmp/btd-death-regression-maz0tp6d`.
- Independent context/reviewer agent found no blocking issues. Its initial
  position-test concern was resolved by asserting the expected elevated height
  and horizontal position before the stationary interval.

Full local logs remain private at those paths. These are synthetic results;
they do not certify human gameplay or a remote deployed image.

## Delivery gates and rollback

Owner merge approval is required for both focused PRs after mandatory checks and
independent review. No service was authorized for deployment by this work.
After owner merge and explicit homologation authorization, use the existing
workspace master command, verifying its resolved master revisions and image:

```sh
COD4_BTD_ASSETS='/tmp/cod4-btd-package/Before The Dawn Alpha 001' COD4_INTEGRITY_HEADERS=/tmp/cod4-btd-prepared/integrity/addiwdheaders ./scripts/deploy-homolog.sh zombies
```

Run from the operator's configured ec2-workspace checkout. Do not approve its
final promotion/production-artifact prompt from startup health alone. First
verify the running homologation digest and obtain supervised real-client combat,
death/respawn, waves, camping, elevated positions, message, reconnection and map
transition evidence. No current remote digest is asserted here; preserved
incident inspection is historical. Keep production on its known-good Promod.
Declining that prompt exits nonzero but leaves the successful homologation
candidate running and preserves the existing `.state/approved`; it is not a
rollback. The prompt records approval for later promotion, not a production
deployment.

Rollback the Classic policy by reverting config PR #12 and rebuilding through
the existing reviewed master workflow; retain PR #20's safety fixes. Runtime
rollback must use the existing workspace procedure and exact previous approved
digest with operator authorization. Do not overwrite preserved PoC evidence.
