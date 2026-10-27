# Before the Dawn death and wave regression

The October 27 production exception is a death-callback failure, not a process
crash. The preserved stack identifies `_globallogic.gsc:5184`, entered through
`_callbacksetup.gsc:69` / `level.callbackPlayerKilled`: an existing inflictor's
undefined `targetname` is compared with `"zom"`. The game shuts down with
`Server disconnected`; a running container is therefore insufficient health.
The stack does not identify the actual damage source.

A disposable native player suicide reproduces that callback error and shutdown.
The source overlay adds a defined-field guard before comparison. It leaves the
zombie branch intact and does not modify VM comparison behavior or Promod.
After that correction, accelerated wave testing independently exposed a second
original-package defect: spawn structs contain only origin, while
`k3/_zombie.gsc:125` assigns their undefined angles to a native vector. A second
one-line overlay initializes angles to `(0, 0, 0)` in the spawn-point producer.
This second failure was not the production incident's recorded exception.

Preparation verifies every original input and pinned raw-source hash, reads
plaintext GSC raw members from the verified fastfile and generates private GSX
overlays. There is no bytecode decompilation or fastfile rebuild. The original
`mod.ff`/IWD/CFG bytes are retained. Generated third-party source remains in the
operator's private runtime and must not be committed or redistributed.
`inputs.json` records both overlay hashes; workspace packaging must validate them.

## Automated evidence

`python3 -m unittest discover -s tests -p test_btd_prepare.py` uses only synthetic
raw-source/package fixtures: input identity, missing/ambiguous conditions,
precise guard substitution, native-vector initialization and no original edits.

With authorized private runtime/game inputs, use the disposable runner below.
`--runtime` must contain `.bot-test-runtime`; every run copies inputs to a new
private `/tmp/btd-death-regression-*` directory. No remote service is touched.

```sh
python3 tests/run_btd_regression.py --runtime PRIVATE_RUNTIME --game GAME_DATA --binary PRESERVED_BINARY --scenario expression
python3 tests/run_btd_regression.py --runtime PRIVATE_RUNTIME --game GAME_DATA --binary PRESERVED_BINARY --scenario expression --fixed
python3 tests/run_btd_regression.py --runtime PRIVATE_RUNTIME --game GAME_DATA --binary PRESERVED_BINARY --scenario death
python3 tests/run_btd_regression.py --runtime PRIVATE_RUNTIME --game GAME_DATA --binary PRESERVED_BINARY --scenario death --fixed
python3 tests/run_btd_regression.py --runtime PRIVATE_RUNTIME --game GAME_DATA --binary PRESERVED_BINARY --scenario lifecycle --fixed --reproduce-spawn-defect
python3 tests/run_btd_regression.py --runtime PRIVATE_RUNTIME --game GAME_DATA --binary PRESERVED_BINARY --scenario lifecycle --fixed
```

The reproduction commands succeed only when the expected original failure is
observed. The fixed lifecycle run requires native player spawn, suicide, callback
completion, respawn, actual vendor zombie spawning/death handlers and progression
into wave two. Only fixture CFG values accelerate grace time/wave size; shipped
policy is unchanged. It then performs two real UDP admission handshakes with
intervening disconnects and native map transitions. Full logs and `results.json`
remain in the private evidence directory; script compile/runtime errors fail the
fixed run. `developer=1` is deliberate: the original private production CFG used
that setting, and `developer=0` can suppress script-error reporting.

The existing `run_btd_integration.py` covers all 15 installed maps, process restart,
CFG precedence, purity and denied RCON activation. It now explicitly enables script
error reporting. The existing Promod integration suite remains separate.

Synthetic players and UDP admission are not graphical client gameplay. Neither
playability nor production readiness is certified by these tests. Require
independent review, existing mandatory hosted CI, operator-approved merges,
master-based homologation deployment, and operator-supervised real-client death,
respawn, combat, waves, reconnection and map transitions before exact-image approval.
Keep recovered production Promod unchanged until explicit promotion authorization.
