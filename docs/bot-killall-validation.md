# bot_killall qualification — 2026-10-26

Based on master `da38202d05c47e040e30e79cd42eea3ad9793109`.
The command registers power 80, matching bot_kickall, and selects only active
NA_BOT connections. The gameplay helper skips dead/spectating entities and uses
player_die with self as attacker/inflictor and MOD_SUICIDE, matching GSC suicide.
It establishes and restores the server animation context for console execution.
Promod retains its death callback, scoring, round completion and spawn logic.
No population policy, bot tracking, script callback or kick command is changed.

Validation:

- `make -j4`: ELF32/i386 build 1259; GCC 16.2.1 20260810, NASM 3.02.
  Existing PIE/text-relocation linker warnings remain. Tested executable SHA-256:
  `419272b2d800daccc3025453f2fb3f0ecbfcde79184e973efc54a85e7ebd1446`.
- `python3 -m unittest discover -s tests -p 'test_*.py'`: 27 tests pass,
  one existing skip. Loopback socket tests require an environment permitting
  local UDP sockets. The new C fixture executes production command/death bodies
  for all alive, mixed alive/dead, human exclusion, empty population, repeated
  calls, simulated respawn, transition guard and unchanged connection/fill state.
  Registration asserts the same permission as bot_kickall; existing RCON tests
  exercise authentication. This fixture does not simulate full Promod rounds.
- `cc -std=c11 tests/test_bot_policy.c -o /tmp/bot-killall-policy` and executing
  it passes the existing population policy assertions.
- `python3 tests/run_bot_killall.py --runtime /tmp/cod4x-admin-final-runtime
  --game '/home/gabriel/.local/share/Steam/steamapps/common/Call of Duty 4'`:
  a new disposable runtime copy passed authenticated RCON, denied RCON,
  12 living bots killed, immediate repeat returning zero, natural S&D round
  respawn (11 living at the sample), a second successful kill, zero bots,
  unchanged 12 connections and paused Auto-Fill, and a connected human handshake
  preserved alongside 11 bots. Promod logged normal MOD_SUICIDE callbacks.
  Pure remained 1 with eight administrative headers and no script/fatal errors.
  Accepted private evidence: `/tmp/cod4x-killall-fh_u7dcj` (RCON/human),
  `/tmp/cod4x-killall-4n_lxtpz` (initial console regression).

Dependencies remain pinned in bots/dependencies.json: Bot Warfare v2.2.0 commit
`7b52b462e40fa68287b9e54602e52da83b17766c`, Promod LIVE V2.20 EU with the
existing artifact hashes. Test assets were copied; previous prepared runtimes,
PoC evidence, proprietary assets and original dependencies were not modified.
No generated artifacts or raw runtime logs are included in Git.

Rejected evidence remains under `/tmp/cod4x-killall-myu48uhg` (missing game
mount) and `/tmp/cod4x-killall-b3uedskk` (the initial direct death call exposed
missing animation context). The corrected helper passed both accepted runs.

Limits: the human handshake fixture remains connected, without entering the
world. Active human health exclusion is covered by the native fixture; graphical
human health, XP/score displays, bomb-carrier plant/defuse cases, full competitive
matches and long-duration play still require manual qualification. Self suicide
provides no human attacker credit. Default registered powers are tested; a
custom limited-power authenticated account was not provisioned locally.

Rollback: revert the focused feature commit and rebuild. No persistent state or
configuration migration is needed. No production service, EC2 or Bard changed.
