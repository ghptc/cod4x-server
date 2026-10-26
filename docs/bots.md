# Experimental Promod AI bots

This preserves the working Crash proof of concept and adds native population
control. It is not a production release. The engine feature defaults off.
Use `+set bot_enable 1` only in an isolated prepared runtime with `sv_pure=1`.

The native controller fills up to 12 occupied human/bot slots, adding at most
one bot per 250 ms after the GSC marks map navigation ready. Humans in connection
handshake, downloads and spectators count against capacity. Slots occupied by
zombies are not reused early. The existing private-slot rules remain intact.

Bot Warfare's own population controller and automatic host/menu permissions are
not loaded. Server scripts use the installed Promod team/class functions and
the pinned Bot Warfare perception, navigation and weapon-input core. Native
bot input is cleared on slot reuse. No damage, death, ready-up or bomb callback
is replaced. Objective planting/desarming remains disabled pending a separate
compatibility implementation. Match-mode ready-up and human-client pure checks
remain explicit test requirements, not implied by local bot gameplay.

## Bot commands

Counts are strict decimal integers in 0..12; invalid/trailing arguments do not
mutate state. All mutating bot commands use existing command power 80 and must
be sent through authenticated RCON, the local console, or authorized in-game
administration. `bot_status` remains power 20. No player host/admin permissions
are granted by Bot Warfare.

- `bot_add <count>`: add immediately when AI is ready, up to free slots and
  bot_limit. Zero is a no-op. Does not change the Auto-Fill state; pause filling
  first for a controlled partial population. Missing waypoints, round transition,
  disabled AI or a queued human connection reject the request without deferred
  additions; retry after readiness. Native allocation only uses CS_FREE slots.
- `bot_kick <count>`: pause Auto-Fill, then remove up to count bots. Zero is a
  no-op. Human clients are never selected.
- `bot_limit <count>`: maximum bots (default 12), also bounded by available
  space in the maximum 12-occupant population. Zero removes bots and prevents
  automatic creation. Reductions apply even while paused. The backing startup
  cvar is `bot_fill_limit`; limit is retained across maps/rounds.
- `bot_difficulty <fixed|mixed|1..7>`: the original integrated fixed profile
  is the default. Mixed reuses Bot Warfare's normal-distribution tier selection
  (center 3.5, standard deviation 1.75, bounds 1..7); 1..7 use its actual seven
  profiles without inventing level names/values. Current bots update within
  0.5 seconds; newly attached bots inherit the mode. Startup cvar `bot_skill`
  is -1 for fixed, 0 for mixed, 1..7 for tiers. Unsupported custom/randomized
  BW modes 8/9 are not exposed. Bomb/grenade/jump actions remain disabled.

- `bot_status`: enabled flag, fill state, humans, connecting humans, bots, AI
  readiness, pure, bot limit and difficulty. Default command power: 20.
- `bot_kickall`: pause first, then remove every bot. Default power: 80.
- `bot_autofill 0`: pause without removing current bots. Default power: 80.
- `bot_autofill 1`: explicitly enable/reactivate filling. Default power: 80.

After an empty-server kickall, state is paused-awaiting-human and does not
reactivate by polling an already-empty server. An admitted human changes the
state to paused-with-humans; only that last human's actual disconnect (or the
explicit enable command) reactivates filling. The state is native process
memory and survives map/round changes. A process restart uses startup settings;
pause persistence across crashes/reboots is not implemented.
Paused manual populations are not recreated after a full map load: zero stays
supported on every map. Enable Auto-Fill to restore the configured population.
Keep `bot_enable=1` before map startup even for zero/paused bots so that the AI
can initialize; changing it from 0 at runtime requires reloading the map.
Existing bot slots still yield during valid human admission if bot_enable was
subsequently disabled. All existing connection/auth/pure checks remain intact.

Human priority runs in SV_DirectConnect after challenge, protocol, ban, password
and queue-head validation but before a full-server response. If no public slot
is free, a bot is normally disconnected and its CS_FREE slot is assigned within
that same server-thread call. Later authentication/game/plugin denial can still
reject a connection for its own reasons. No bot is evicted for getchallenge or
getinfo. Twelve actual humans can legitimately fill the server. Filling also
waits while the existing human connection queue is live.

## Prepare local inputs

Keep a verified Bot Warfare checkout at the pinned revision and your own local
Promod/game files outside Git. See bots/dependencies.json for exact input hashes.

```sh
python3 tools/bots/prepare.py \
  --promod /path/to/private/pml220 \
  --bot-warfare /path/to/iw3_bot_warfare \
  --headers /path/to/private/addiwdheaders \
  --binary bin/cod4x18_dedrun \
  --output /path/to/private/bot-runtime
```

The tool copies inputs and generates local server overlays; it does not modify
the source game directory. Its root is independent of the installed game.
The eight-header runtime requires the separate administrative-IWD integrity PR
when testing with the corresponding reduced server data. The bot source branch
does not include that filesystem patch or temporary PURE_DIAG instrumentation.

Map initialization is taken from the actual verified installed mod.ff. The
loader tries .gsx before .gsc, allowing a wrapper that calls the installed map
initialization before starting AI. Twenty-one official waypoint sets are pinned;
missing navigation leaves AI readiness false, and the native controller does
not fill that map. Full map changes remove old bots through the existing engine
path. New map/round scripts rebuild perception/navigation and restore readiness.

## Tests and scope

```sh
gcc -std=c11 -Wall -Wextra -Werror tests/test_bot_policy.c -o /tmp/cod4x-bot-policy
/tmp/cod4x-bot-policy
make -j4
```

For isolated runtime regressions, compile `tests/bot_handshake.c` to
`<runtime>/handshake` using the runtime's own GCC/toolchain environment. The
fixture sends a real challenge/connect exchange only to namespace loopback;
it does not complete graphical-client authentication or enter gameplay.
Then run:

```sh
python3 tools/bots/run_local.py --runtime /private/bot-runtime --game /private/game --scenario policy --seconds 75
python3 tools/bots/run_local.py --runtime /private/bot-runtime --game /private/game --scenario rotation --seconds 135
python3 tools/bots/run_local.py --runtime /private/bot-runtime --game /private/game --scenario burst --seconds 30
python3 tools/bots/run_local.py --runtime /private/bot-runtime --game /private/game --scenario controls --seconds 117
python3 tools/bots/run_local.py --runtime /private/bot-runtime --game /private/game --scenario no-waypoints --seconds 30
python3 tools/bots/run_local.py --runtime /private/bot-runtime --game /private/game --scenario empty-rotation --seconds 240
```

The default image is the exact existing private local builder used in validation;
`--image` accepts an equivalent local runtime. Images are never pulled implicitly.
Every scenario invokes `verify.py` and fails on a rejected behavioral assertion,
not merely a process exit code. Runtime logs and input hashes stay outside Git.
The burst test uses six different loopback source addresses so the existing
per-address incomplete-connection DoS protection is not bypassed or disabled.

Use only disposable Docker runtimes, game directories mounted read-only, no
network/ports exposed to production, and distinct home directories. Basic debug
evidence is opt-in with `+set bot_debug 1`; this is ordinary test logging, not an
observability stack. Verify movement, targets, shots and Promod-attributed damage;
CS_ACTIVE alone does not pass gameplay acceptance.

The preserved original PoC is private at
`~/Projects/cod4x-poc-001-preserved`. Its accepted 140-second run observed 43 and
34 shots, mutual targeting, waypoint traversal and kills in both directions;
the 45-second slot test freed and reused slots 0/1. Raw logs, generated binaries
and proprietary inputs stay in that archive, not Git. New integration results
must be recorded separately; original PoC success does not certify Auto-Fill.

Rollback: start a previous verified executable without bot_enable, using the
original three Promod artifacts and eight headers. No production changes are
authorized here. No CI, image publishing, release or deployment is configured.

## Gameplay corrections

Prepared runtimes select from all four Promod weapon classes and validate primary
and pistol choices against the active mode. Human class reservations and the
class-availability display exclude bots; a zero class limit still disables that
class. Selection is checked again before reserving a human slot.

The companion Promod CFG sets `sv_randomMapRotation=1` and
`promod_auto_maprotate=1`. The native shuffle supplies the initial map and avoids
immediate automatic repeats. The prepared match-end overlay calls native
`exitLevel` only after a completed match; normal S&D rounds still restart.
Administrator map commands and PR #8's next-map vote keep their native paths.

Run `python3 tests/run_map_rotation.py`, `python3 tests/run_map_voting.py`, and
`python3 -m unittest discover -s tests -p 'test_*.py'`. For a **disposable** prepared
runtime, `tests/run_gameplay.py --runtime PATH --game PATH --scenario controls`
qualifies RCON removal, admitted-client preservation and all supported gun
inventories; `--scenario rotation` exercises the actual Promod round/match-end
routines and voted-map consumption. These fixtures do not certify graphical
clients, Steam authentication or a full human-played match.
