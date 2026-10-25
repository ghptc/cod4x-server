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

- `bot_status`: enabled flag, fill state, humans, connecting humans, bots, AI
  readiness and pure status. Default command power: 20.
- `bot_kickall`: pause first, then remove every bot. Default power: 80.
- `bot_autofill 0`: pause without removing current bots. Default power: 80.
- `bot_autofill 1`: explicitly enable/reactivate filling. Default power: 80.

After an empty-server kickall, state is paused-awaiting-human and does not
reactivate by polling an already-empty server. An admitted human changes the
state to paused-with-humans; only that last human's actual disconnect (or the
explicit enable command) reactivates filling. The state is native process
memory and survives map/round changes. A process restart uses startup settings;
pause persistence across crashes/reboots is not implemented.

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
