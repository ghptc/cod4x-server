# Human-only Promod Ready Up

The prepared Promod overlay now requires confirmation from every human assigned
to allies or axis, with at least one such human present. Spectators, unassigned
players and bots do not enter the quorum. Team/class selection and bot AI are
unchanged. This supersedes the bot auto-ready policy in the historical
[promod runtime integration report](promod-runtime-integration.md).

## Root cause and correction

`tools/bots/prepare.py::bot_readyup` previously marked each bot ready when it
had a team and class, and counted bots without those assignments as not ready.
Original Promod's `level.players.size<1` guard includes bots. Consequently a
bot-only population could satisfy `all_players_ready`, enter the five-second
countdown and start a match without a human confirmation.

The overlay now adds one human/team eligibility predicate to the original
`promod/readyup.gsc` loop. Before the existing player initialization and input
logic, it clears and skips ineligible players. Each original 50 ms iteration
rebuilds the eligible-human and pending-confirmation counts from `level.players`.
Completion additionally requires a positive human count. No slot-indexed or
persistent ready-state registry is introduced. A changed team clears that
human's confirmation and restores the original unready scoreboard icon/client
state; returning from spectator requires confirmation again. The original use
button, recording confirmation, HUD and five-second countdown remain in place.
The last-player reminder uses the same eligible population.

The pinned script has a nonempty-player guard, rather than an additional
minimum-human setting. Its guard and all other competition rules remain; the
new positive-human guard prevents bots from satisfying that requirement.
Preparation still verifies the locked Promod inputs and rejects missing or
ambiguous replacement anchors. Extracted proprietary scripts remain private.

## Lifecycle trace

- Map initialization: original `_globallogic::Callback_StartGameType` initializes
  a fresh game and sets `promod_do_readyup` for the configured match mode.
  `startGame` invokes the original Ready Up implementation. The overlay
  initializes its population there, rather than in bot admission or map wrappers.
- Bot admission: `bots/promod_ai.gsc::attach` retains original auto-assignment,
  validated loadout selection and `menuAcceptClass`. Bots never run Ready Up
  input/recording threads and never enter ready/not-ready counts.
- Human input: original `selfLoop` toggles readiness with the use button, gated
  by current human/team eligibility. Existing recording-menu confirmation still
  applies. Team and spectator changes are observed by the next original loop
  iteration; a disconnect removes the entity from `level.players` and terminates
  its input thread through the original disconnect notification.
- Match start: the existing completion latch, countdown, state changes and
  `map_restart(true)` run unchanged after all eligible humans confirm. This
  retains Promod's original countdown behavior once confirmation completes.
- S&D rounds: ordinary `map_restart(true)` preserves game state and does not
  request initial Ready Up again. Original halftime/timeout Ready Up rules remain.
- Match end: the existing gated terminal `exitLevel` and native rotation consume
  an approved next-map vote or select the rotation map. Fresh map state enters
  Ready Up again. Neither engine rotation nor native voting was modified.
- Native callvote: `G_VoteClientEligible` remains independent, excluding bots
  through the native address/connection/team predicate for calling, casting and
  majority calculations. Ready Up adds no Yes/No vote implementation.

## Reproduction and limits

Run the dedicated qualification against a disposable copy of verified inputs:

```sh
python3 tests/run_human_readyup.py --runtime /path/to/prepared-private-runtime \
  --game '/path/to/licensed/Call of Duty 4'
python3 -m unittest discover -s tests -p 'test_*.py'
python3 tests/run_map_voting.py
python3 tests/run_map_rotation.py
```

The runner verifies all three locked Promod assets and eight administrative
headers, creates its own private directory and loopback server, derives the
current Ready Up overlay from the original fastfile, and installs the existing
test-only plugin there. It never edits its runtime input, the preserved PoC or
any existing service. `sv_pure=1` remains enabled. It uses the existing prepared
competition/voting/match-end overlays; prepare inputs with `--allow-map-voting`
and `--allow-no-punkbuster` for this local fixture.

Synthetic humans use real engine entities and native use-button fields. Human
team/spectator transitions invoke original Promod menu handlers; disconnects
use native `clientkick`. Late admission is simulated by converting an existing
entity, not by authenticating a graphical client. Recording confirmation is
fixture-satisfied because its menu requires a graphical client. The fixture
shortens S&D to two rounds and disables vote cooldown locally. Before accelerated
administrative suicides it initializes an undefined `throwingGrenade` field to
false; the pinned original death handler reads it before normal grenade tracking
may initialize it. This fixture accommodation does not alter production scripts. Full MR12,
graphical controls/HUD/recording menus, network reconnects across maps and
long-duration gameplay remain manual validation. `CS_ACTIVE` and Promod's
`game["state"]="playing"` alone are not evidence that Ready Up ended: the latter
also holds during waiting. Snapshots assert `rdyup`, `ready_up_over`, human quorum,
pending confirmations and actual round/map transitions.

The production policy caps total population at 12, so the mixed cases use
11 bots plus one human or 10 bots plus two humans. A simultaneous 12 bots plus
humans is outside the existing population policy and was not enabled for testing.

## Accepted runtime evidence

All 24 checks passed at `/tmp/cod4x-human-readyup-zhambz98/results.json`
with the final production overlay and committed fixture. An independent earlier
run at `/tmp/cod4x-human-readyup-7lkn057s/results.json` also passed all 24 checks
with the same production overlay, before the fixture timing/death-field hardening.

| Observation | Runtime evidence |
| --- | --- |
| Fresh Crash, 12 bots, no humans | eligible=0, pending=0, bot_ready=0, over=0, rdyup=1 |
| All bot ready flags deliberately set | Cleared on next iteration; waiting remains active |
| One human, 11 bots | eligible=1, pending=1, over=0 |
| Two humans, only one confirmed | eligible=2, pending=1, human_ready=1, over=0 |
| Both humans spectator | eligible=0, pending=0, human_ready=0, over=0 |
| Return from spectator / direct team switch | eligible=2, pending=2, human_ready=0 |
| Disconnect and late join | Counts move 2 -> 1 -> 2; last human leaving stays waiting |
| Both humans confirm | eligible=2, pending=0, over=1; original countdown restarts into play |
| Bot call/cast versus human vote | Bot rejected; two of three humans approve Strike |
| Ordinary S&D round | Crash retained, rounds=1, rdyup=0 |
| Completed match with approved vote | Strike loaded, over=0, eligible=0, rdyup=1 |
| One human confirms on Strike | eligible=1, pending=0, over=1; original start succeeds |
| Completed match automatic rotation | Backlot loaded, over=0, eligible=0, rdyup=1 |

Purity stayed 1; eight administrative checksums loaded; no script compile/runtime
or fatal errors were detected. The private runtime contains snapshots and full
console evidence; full logs and proprietary derived scripts are not committed.
Engine executable SHA-256:
`a22a41222c786f00470a6cba1309dfa2b9d93ad1294b538b7c99ce8099c386e0`.
Ready Up overlay SHA-256:
`616c9e910dc27b1dd394dc3835bbb561c970ebad03a1fe31b4cce89bd7dd6f54`.
Dependency-lock SHA-256:
`a958f7fa4fd8d7165c01701e1a1c6e5180ec837ae4fc92dbe3fd7b4c2463ff93`.
Python regressions: 28 tests passed with one existing skip. Native callvote,
cast-vote/CheckVote and rotation harnesses passed. Socket/native harnesses were
rerun outside the restrictive sandbox after socket/SIGSYS failures.
Earlier rejected fixture runs remain privately under `/tmp/cod4x-human-readyup-*`;
they are not accepted evidence. Existing historical PoC evidence is unchanged.

## Dependencies and rollback

Base: master `36a9b058ed0b4dc1a9896f558db61a009ecae60e` (merged runtime integration).
Dependencies are unchanged in `bots/dependencies.json`: Bot Warfare v2.2.0
`7b52b462e40fa68287b9e54602e52da83b17766c`, Promod LIVE V2.20 EU with `mod.ff`
SHA-256 `930c9123b679394c18683f890d8e792d3b31cafacadda2c3293e5e066e9fb1c2`,
and the same eight administrative-header hashes. No dependency downloads or
engine-source changes are required. Related configuration/workspace repositories
need no edits for this correction; newly prepared artifacts receive the overlay.

Rollback: revert the focused commit and prepare a new artifact from the prior
reviewed inputs. This restores the previous bot auto-ready behavior, including
its bot-only-start limitation. Existing immutable artifacts and the preserved
PoC remain available. There is no persistent migration. Nothing is deployed.
