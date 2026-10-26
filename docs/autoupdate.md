# Self-updates in immutable deployments

Managed deployments can opt out of server self-updates at process startup:

```text
+set sv_autoupdate 0
```

The default is `1`, preserving ordinary upstream behavior. The Boolean cvar is
registered with `CVAR_INIT` in `Com_InitCvars`, after startup arguments are first
applied and before global configuration is executed. `Sec_Update` returns before
update requests, path setup, lock creation, downloads, renames or restarts when
it is disabled. Set it on the command line: `server.cfg` executes too late to
control this startup operation, and later console/CFG changes are write protected.
This option requires a binary built from the commit introducing it; older
binaries can silently accept an unused cvar without disabling their updater.

This only gates `Sec_Update`. `Sec_Init` still registers/tests cryptographic
hashes. Global configuration loading, filesystem/pure verification, the eight
administrative headers, Steam/client authentication, client-update backend,
plugins, game initialization and bot initialization keep their existing paths.
Disabling server self-updates does not disable the separate client updater.

## Cause of the read-only startup delay

`Com_Init` calls `Sec_Update(qfalse)` before `FS_InitFilesystem` and game startup.
After receiving an HTTP 200 update manifest, `Sec_Update` calls
`Sec_AutoaupdateLock` in `src/sec_update.c`. That function tries:

```c
fopen("<binary-directory>/autoupdate.lock", "wb")
```

Every failure enters a timed retry loop and prints that it is waiting for the
file to unlock. It does not inspect `errno`, check whether the file exists, or
acquire a kernel lock. On the reproduced read-only Docker filesystem, the actual
error was **EROFS (30)**, not a held lock. A permission-denied control produced
**EACCES (13)** with the same misleading wait, and a nonexistent directory
produced ENOENT (2). A held advisory lock did not prevent opening the file.

The loop starts at 240 seconds but tests `elapsed > 240` and sleeps 15 seconds
per retry. With a deterministic clock it sleeps 17 times, returning at 255
seconds. If an open eventually succeeds inside the retry loop, the inherited
code closes it, sleeps again and requests a restart. None of these legacy
retry/update semantics is changed for installations retaining the default.
There is no native disable option in the baseline source
`9e3ce3e17532574bbe25e24cbff0174df94c802d`.

The owner's supplied homolog evidence is consistent with this EROFS path. No
EC2 inspection was performed to read the live syscall errno. PID 1, Docker's
RestartCount, and stale kernel locks do not explain this loop: it is a failed
file-open retry before game initialization.

## Local verification (2026-10-26)

The committed regression suite extracts the real lock function and the updater's
early entry path, plus its actual cvar registration. Only the clock/sleep and
engine boundaries are substituted:

```sh
python3 -m unittest discover -s tests -p 'test_*.py' -v
python3 tests/run_map_rotation.py
python3 tests/run_map_voting.py
gcc -std=c11 -Wall -Wextra -Werror tests/test_bot_policy.c -o /tmp/bot-policy
/tmp/bot-policy
make -j4
```

All 20 Python tests, the native bot policy, native map rotation and native map
voting suites passed. The complete i386 engine compiled both on the host and
in the cached compatible Linux builder. The inherited linker text-relocation
warnings remain. A host-linked binary required GLIBC_2.43 and could not run in
the older fixture image; runtime tests therefore used the compatible builder's
binary, not the host binary.

Docker tests used newly created fixtures only, with a read-only root, UID 1000,
no published ports, a network namespace with no external connectivity, and the
engine directly as PID 1. Game main/zone directories were mounted read-only.
Only ordinary `/tmp` and game home state used tmpfs; there was no updater-specific
writable mount. Local proprietary inputs were read without changing their source
or the preserved PoC.

Two complete-engine fixtures shared an isolated loopback HTTP responder that
returned a synthetic HTTP 200 manifest:

| Startup | Manifest requested | Lock exists | Lock wait | Game initialized |
| --- | --- | --- | --- | --- |
| Default `sv_autoupdate=1` | yes | no | yes, initial 240-second message | blocked |
| Explicit `sv_autoupdate=0` | no | no | no | yes, approximately 0.54 seconds |

The default fixture was terminated after reproducing the wait, rather than
waiting four real minutes. A separate actual-lock-function fixture, under the
same read-only filesystem, reported `errno=30`, 17 simulated sleeps, 255 simulated
seconds. The early-return fixture recorded zero sleeps and no original updater
initialization-path calls. These timings are local observations, not a general
startup latency guarantee.

Longer immutable startup fixtures with the option disabled and with it omitted
both initialized Promod LIVE V2.20 EU on `mp_crash`, loaded all eight administrative
IWD checksums, retained `sv_pure=1`, and reported 12 bots, AI `ready=1`, no updater
wait messages, RestartCount 0 and an engine entrypoint. Namespace-local standalone
UDP RCON accepted a disposable credential and rejected a wrong one. The default
case used an unavailable update endpoint and exercised the existing request/error
path before continuing normally; the HTTP fixture above separately exercises
the default successful-manifest path.

These are startup, readiness and local authentication checks, not gameplay proof
from CS_ACTIVE or a human-client session. Both fixture modes reported missing
`steam_api.so`; online Steam authentication was not qualified, and no such
regression is inferred from that pre-existing fixture limitation. Existing
regressions cover integrity, gameplay policies and bot administration. No remote
production/homolog/Bard service was accessed, changed, stopped or restarted.

Exact local provenance:

- Server baseline: `9e3ce3e17532574bbe25e24cbff0174df94c802d` plus this focused change.
- Bot Warfare: `7b52b462e40fa68287b9e54602e52da83b17766c` (v2.2.0).
- Promod and all eight header identities: `bots/dependencies.json`, SHA-256
  `a958f7fa4fd8d7165c01701e1a1c6e5180ec837ae4fc92dbe3fd7b4c2463ff93`.
- Compatible builder: `sha256:eb0ec28505017cde1229c5b9a86a2d45be495df43d9959a3e242f44272080669`.
- Fixture base: `sha256:d7f12a859b8de231516e8ec811913a4ad4bd6a2e1f68b985c76a03aa1f46f79e`.
- Tested engine SHA-256: `909fb926118e3836c7aab722615860423c1ba03d01b499e5ec7f5a0af8d9021e`.
- Promod/bot/RCON fixture image: `sha256:9b5b23867ccda0f49f8c81f5db9e6b676e85ddb0d2eeb763b03d8328e9350281`.
- Final HTTP-manifest fixture image: `sha256:e1b4849f34191434039815ebef1e66d2222d745d87f86d9905c68e21c3435a70`.

The disposable source archive has no Git metadata, so its embedded version reports
`no-revision`; the explicit baseline, changed sources and binary hash above are
the fixture evidence. Test images are not release/deployment artifacts. No
binaries, game assets, downloaded dependencies or full runtime logs are committed.

## Managed runtime and rollback

The companion ec2-workspace change adds `+set sv_autoupdate 0` to the managed
startup arguments, preserving private CFG/map ordering, image identity, existing
mounts and read-only settings. It rejects attempts to enable the updater through
managed argv. Its local mock-only suite checks artifact provenance, promotion
boundaries and rollback without contacting EC2. Rebuild and qualify a new
immutable artifact from the reviewed engine revision before using those arguments.

A rollback uses the existing prior image/configuration identity, never runtime
binary replacement. Retain `ReadonlyRootfs=true`; do not create a writable
`autoupdate.lock` mount. Reverting the opt-out restores upstream updater behavior,
including the read-only wait if applied to an immutable runtime. Neither this
change nor its tests authorize a deployment or service restart.
