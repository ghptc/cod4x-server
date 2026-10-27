# Traditional UDP RCON compatibility investigation

Current authenticated mode-bridge implementation and its disabled activation
gate are documented in [rcon-mode-bridge.md](rcon-mode-bridge.md). The historical
investigations below retain their original evidence and scope.

Investigation date: 2026-10-26. Server baseline:
`9e3ce3e17532574bbe25e24cbff0174df94c802d`.
No real credential was read or used. No remote runtime was contacted or changed.

## Findings

A 48-character alphanumeric password works through the traditional server UDP
parser and authentication function. It cannot be installed using `/rcon login`
in either of the two client binaries found in the owner's Steam/Proton installation.

| Implementation | Accepted login length | 16 | 32 | 48 | 64 |
| --- | --- | --- | --- | --- | --- |
| Installed `iw3mp.exe` login routine | 0–23 bytes | accept | reject | reject | reject |
| Installed `cod4x_021.dll` login routine | 0–28 bytes | accept | reject | reject | reject |
| Standalone UDP client against server-function harness | minimum 8 bytes; packet budget below | accept | accept | accept | accept |

The server minimum makes the usable overlap 8–23 bytes for both clients, or
8–28 for this CoD4x client alone. These are ASCII byte limits, not a general
Unicode character claim. Lengths 23/24 and 28/29 were also exercised.

Both clients reject an overlong login without replacing the previous stored
password. The login operation itself sends no authentication packet. A subsequent
`rcon status` can therefore send a stale password and produce `Bad rcon`. With no
previous login, the client instead asks the user to log in. This explains how
correctly copying a 48-character server password can still produce mismatches;
it is not evidence that the server truncates that password.

The installation contains a CoD4x DLL, but that alone does not establish which
implementation was active during the reported attempts. The discovered game
process was a zombie with no memory mappings. The owner was asked for only the
`/version` output to close that attribution gap. Neither the active remote cvar
nor the original failure packet was inspected; the incident's precise active
build and stale credential remain unverified.

## Parsing and serialization

`SV_ConnectionlessPacket` in `src/sv_main.c` skips the four-byte `0xffffffff`
marker, reads a line with `MSG_ReadStringLine`, tokenizes it, then dispatches
`rcon` to `SVC_RemoteCommand`. Authentication uses case-sensitive `strcmp` of
`SV_Cmd_Argv(1)` and `sv_rconPassword->string`, then enforces the eight-byte minimum.
On success it rereads the packet, skips the marker and four bytes `rcon`, skips
the quoted or unquoted password, and executes the remainder.

`MAX_STRING_CHARS` is 1024: the initial line buffer holds **1023 bytes**, excluding
the OOB marker and terminator. With `rcon PASSWORD COMMAND`, keeping the complete
initial line requires `password_bytes + command_bytes <= 1017`; quoting the
password costs two more bytes. The initial token can contain at most 1018
unquoted password bytes after `rcon `. The second read starts four bytes later,
so the harness still executes a one-byte command with 1017/1018-byte passwords;
1019 bytes cannot authenticate. This two-pass behavior is not a recommended
client packet budget. There is no separate 32/48/64-byte server authentication
limit. `%` becomes `.` in `MSG_ReadStringLine`, and newline/NUL terminate it;
the alphanumeric tests avoid those independent protocol restrictions.

The installed stock login machine code at VA `0x471a4b` compares length with
24 and accepts only below 24. The bundled `_cl_main_pc_mp.asm` independently
shows the equivalent maximum 23. The installed CoD4x DLL compares with 28 at
VA `0x6319561c` and rejects above it. The public client source
[CL_Rcon_f at the tested revision](https://github.com/callofduty4x/CoD4x_Client_pub/blob/17182c7bf04b859dea5c0db4acdb0b83c28d6dd2/src/cl_main.c#L4502)
uses `static char rcon_password[32]` and `strlen(...) < sizeof(...) - 3`:
maximum 28, despite the 32-byte storage. It sends four FF bytes, `rcon `,
stored password, a space, command arguments, and a NUL using `NET_SendPacket`.
Its message buffer is 1024 bytes including the OOB marker and terminator.
Setting a client cvar named `rcon_password` does not change this static storage.

## Reproduction and effective CFG values

Run the dependency-free server regression suite with a C compiler and Python:

```sh
python3 -m unittest discover -s tests -p test_rcon.py -v
```

It compiles the actual current `MSG_ReadStringLine`, tokenizer,
`Cvar_Set_f`, `Cvar_SetVariant`, `SVC_RemoteCommand`, and Source RCON auth function.
Synthetic `set rcon_password "..."` CFG files are read from temporary directories.
The real tokenizer/setter path must produce an exact effective string match;
only its length and equality result are printed. The harness supplies the
`Cvar_Set2` lookup boundary for the registered string cvar. It uses real loopback
UDP sockets with standalone packet serialization and tests quoted/unquoted
passwords, minimum length, mismatch, and packet boundaries.

For the actual public client serialization comparison, clone the public client
outside this repository at revision `17182c7bf04b859dea5c0db4acdb0b83c28d6dd2`, then:

```sh
COD4X_CLIENT_SOURCE=/tmp/cod4x-rcon-client-reference \
  python3 -m unittest discover -s tests -p test_rcon.py -v
```

That optional test compiles the actual public `CL_Rcon_f` function with engine
boundaries, first installs a disposable old login, attempts each new length,
and sends the resulting client packet to the same UDP harness. Lengths up to
28 succeed; 32/48/64 retain the old login and receive `Bad rcon`.
All five tests passed with the optional checkout enabled.

`tools/rcon/probe_client_login.py` separately executes the **installed binary
login instructions**, using Unicorn 2.1.4 in a disposable virtual environment.
It maps only the on-disk PE images with synthetic memory and stubs printing and
library boundaries. It never reads live client state, credentials or CFGs, and
never sends a packet. Pass the two installed binary paths to reproduce.
Both boundary tables above passed. Exact binary SHA-256 identities:

- `iw3mp.exe`: `f50f8a520581754e73cb7cae67b02adcbad5f2e71aaa412a013bb3ef57a391a5`
- `cod4x_021.dll`: `bf5965ea484e0b899119ebb99428b8f7aaf175f2052e610c1ce466119e6b0d2b`

These are function-level and emulated binary tests, not a graphical game session
or a full dedicated-server boot. Filesystem search precedence, later CFG
assignments, live homolog cvar state and the active historical DLL were not
verified. `execing server.cfg` proves queuing the file (`Cmd_Exec_f` calls
`Cbuf_InsertText`), not that no later command overrides its values.

## Verified fix and rollback

No traditional UDP authentication change is justified by these results. The
separate confirmed defect is Source RCON's rejection log exposing the entire
submitted login string, including account/password combinations. Remove that
argument while retaining the peer address. Regression tests cover both login
forms and preserve auth rejection ID -1 and the 20-second ban. The regression
fails against the previous plaintext logging statement and passes after the fix.
Production `src/hl2rcon.c` also passed i386 syntax compilation.

Rollback consists of reverting the logging-fix commit; no configuration,
credentials, services or protocol behavior were changed. No binary, third-party
checkout, game assets, dependency package or raw runtime log is included.

## Before the Dawn and change mode preflight (2026-10-26)

The `change_mode` command is a nonmutating administrative preflight. It is **not**
a deployed mode switcher. It requires power 100 in both command registration and
the handler; changing command power metadata cannot lower the handler's floor.
Authenticated UDP RCON retains its existing password/minimum-length checks;
Source RCON and in-game administration retain their existing authentication.

- `/rcon change_mode` reports current `fs_game` and no available switch targets.
- `/rcon change_mode zombies`, `promod` or `hardcore` reports that the qualified
  artifact controller is unavailable and explicitly leaves the runtime unchanged.
- Unknown identifiers receive the same unavailable result. Paths, URLs, separators,
  controls, uppercase IDs, extra arguments and IDs over 32 bytes are rejected.
- No request is enqueued, no shell is invoked, no file/cvar is written and no
  restart/download/build/deployment occurs. Thus simultaneous requests cannot
  start competing transitions. This does not test a future controller's lock.

The current engine cannot identify a canonical mode ID from `fs_game` alone, so
status deliberately reports the actual game directory rather than guessing a
mode name or inventing artifact availability.

### Original package and compatibility

Inspected the owner's newly downloaded `before_the_dawn_alpha_001.rar`, SHA-256
`dad2e94a92823844ab411f3dfadd0f2dacc491b9df3416db8b1a1f9fb9f4d410`.
The extracted root is `Before The Dawn Alpha 001`; its `btd_alpha_001` directory
contains the original fastfile and dependencies:

| Asset | SHA-256 |
| --- | --- |
| mod.ff | 50911fdd0273b50e26983723619881acfaed4aa65f4d91a799a341464c2224a6 |
| btd_images.iwd | 6db51738edb6f38e48a2e72a7cdb3cb3ff08482c5578a5e944cdd2f4b03daef0 |
| btd_music.iwd | 67f48b88d0cfec1e79287393afe8569313bf37bf2c7dcb9eed9a73e3103f5124 |
| btd_weapons.iwd | b98a1c765d655063cfd60a776887d09a6fcc25572dcaf5a4f74eaf7c26e167fa |

The IWDs contain images, sound and weapons respectively, with no GSC/CFG/license
files. The fastfile is the original IWffu100 version 5 format. It is neither
unpacked, decompiled, patched nor rebuilt by this integration. Exact hashes for
all nine CFGs and the original readme are in `tools/btd/dependencies.json`.

The readme identifies BTD Alpha 001, credits AbneyPark and the Before the Dawn
development team, and describes cooperative survival against increasing waves
of AI zombies, grace periods/ammo depots, configurable health/damage and a loss
when every survivor dies. This describes the original mod's AI, not Bot Warfare.
It also reports clipping/undermap bugs and an unresolved invulnerable-spectator
bug. These limitations are not corrected by engine integration.

Original instructions select `mods/btd_alpha_001` and `war`. The supplied map
rotation lists Convoy, Bloc, Bog, Broadcast, Countdown, Crash, Creek, Crossfire,
Farm, Overgrown, Pipeline, Showdown, Strike, Vacant and Cargoship. District
(`mp_citystreets`) and Killhouse are explicitly excluded for model-limit errors.
No other map is added based on filename or Promod support.

The supplied `server.cfg` contains sample passwords, an obsolete external download
URL, noncanonical settings and an exec of missing `btd_trade.cfg`. It is verified
as part of the input package but never copied/executed in the prepared runtime.
Original vendor defaults loaded are `btd_weaponcontrol.cfg`, `btd_gametype.cfg`,
`btd_settings.cfg`, `btd_zoom.cfg`, `btd_messages.cfg` and `btd_music.cfg`.
`btd_maprotation.cfg` supplies the dependency map inventory; canonical mode CFG
owns the actual rotation. `btd_admin.cfg` is retained privately but not executed;
admin identity/settings require a private operator CFG. The source CFGs contain
some uncommented prose and typos; their existing console diagnostics are retained,
not silently rewritten. No absent trade config is invented.

The readme retains ownership with the development team and credited third parties
and explicitly requests no fastfile decompilation. No redistribution license was
found in the package. Assets, extracted originals and notices remain private;
only authored integration code, policy CFGs and hashes are proposed publicly.
Custom music requires separate permission according to the package's own notice.
No public asset/image publishing is enabled by this work.

### Private preparation and configuration ownership

After extracting the owner's archive locally, use:

```sh
python3 tools/btd/prepare.py --source '/private/Before The Dawn Alpha 001' \
  --headers /private/addiwdheaders --binary bin/cod4x18_dedrun \
  --output /tmp/new-btd-runtime
```

Preparation checks every original file and all eight existing administrative
headers before creating a fresh output; it refuses overwrites, input/output
overlap, symlinked inputs and hash mismatches. It copies the four original assets,
original BTD CFGs except sample `server.cfg`, the readme notice, headers and engine.
It adds no Promod overlay, FPS transformation, AI wrapper or replacement zombie
implementation. Manifest map coverage means package inventory, not combat proof.

The companion catalog provides `modes/zombies/mode.cfg` and `server.cfg`.
The companion packaging recipe verifies BTD assets/binary and loads vendor CFGs
in the shared phase, followed by existing private CFGs, then canonical mode CFG
and native rotation. Credentials stay private; canonical mode settings win.
Promod files, settings, assets and preparation remain unchanged.

A real conflicting private `g_gametype=sd` exposed a string-latch bug: canonical
`war` equalled the current value, causing an early return that left private `sd`
pending. `Cvar_SetVariant` now checks the pending string too for latched writes.
The final canonical value replaces the earlier latch without changing the current
value before reinitialization. A focused test executes the actual setter.

### Switch mechanism and safety gate

`fs_game` is registered with flags 28, including `CVAR_INIT` (16), in
`src/filesystem.c`; ordinary console updates are write protected. It is **not**
a live switchable or latched mode selector. `FS_Restart` can rebuild search paths,
but it cannot supply an absent mod or select a different immutable image. Current
artifacts package only one selected mode. Use controlled container recreation
from an already qualified exact image; map changes alone are insufficient.
Players disconnect and must reconnect, completing target-mod asset loading.

Ownership remains: catalog config; engine authenticated command validation;
workspace image selection, health, recreation and rollback. See the companion
workspace README for the proposed transaction and remaining approval gates.
Do not mount a Docker socket, host shell or deployment credential in the game.
A writable request file in the persistent game home is not an authenticated admin
channel. GSC has `exec`/`execex`, and default engine invoker context is power 100;
a power check alone cannot authorize future host actions. A future bridge must
carry and verify authenticated ingress context, not trust GSC or a cvar.
No such bridge is implemented here.

Existing workspace approval is one artifact with a currently-running homolog
check, not a qualified multi-mode registry. Existing deployments are interactive
workstation operations. Crash recovery of an interrupted image replacement and
per-environment locking also need validation before enabling RCON requests.
These are concrete safety blockers, not grounds to weaken the current controls.

### Qualification status

The standalone original mod boots with pure enabled and eight headers. The real
loopback runner checks all 15 supplied maps, process restart, canonical precedence,
private RCON retention, invalid/unavailable/concurrent requests and protected
`fs_game`. It preserves `read_only` in generated configuration; it does not claim
an actual Docker `ReadonlyRootfs` or container-transition test.

```sh
python3 -m unittest discover -s tests -p 'test_*.py'
python3 tests/run_btd_integration.py --runtime /tmp/packaged-btd-runtime \
  --game /private/licensed-game --catalog /path/to/cod4-config-server \
  --workspace /path/to/ec2-workspace
```

Combat remains unqualified: native test-client survivors are kicked by the
original mod. A synthetic real-UDP admission enters the team path but lacks the
real client's asset/message acknowledgment lifecycle and overflows reliable
commands. Neither `CS_ACTIVE`, loaded maps nor non-player models prove zombie
navigation, attacks, damage, waves or victory/defeat. Those require an actual
client session before artifact approval. No workaround alters the original mod.

Promod→Zombies→Promod, failed-target startup recovery, concurrent actual switches,
container recreation/reconnect and exact-image promotion are specified but not
implemented/tested as mode transitions. Local workspace mocks cover only existing
deployment preservation/rollback. Production, homolog, EC2, Bard and existing
services are untouched. Rollback of this staged work is ordinary commit reverts;
there is no runtime migration or asset deletion to undo.

Accepted local evidence, with engine base
`591e191450b8b9084cafccf7f92b23790bae44a1` plus this branch's working changes:
BTD `/tmp/cod4-btd-qualified-biebk8zp/results.json` passed 53 checks; Promod
`/tmp/cod4x-promod-integration-9aouxfu4/results.json` independently passed 53 checks.
Both tested binary SHA-256
`7246c1b8d26bcd509160eaf12627e6299072af1655af16005710272b6a0df8e3`.
The Python suite passed 33 tests with one existing skip; workspace packaging/mode
suite passed 22 tests and the full existing operations mock suite passed. Build
passed with inherited PIE/text-relocation warnings. No proprietary code or full
runtime logs are committed. Initial failed private-conflict runs were preserved
locally and led to the verified latch fix; they are not counted as qualification.
