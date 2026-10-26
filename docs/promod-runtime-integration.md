# Promod runtime integration — 2026-10-26

These changes are coordinated across engine, configuration catalog and local
workspace consumer. No deployed environment was inspected or modified.

## Findings and ownership

| Symptom | Owning defect and correction |
| --- | --- |
| Manual canonical CFG exec restores rotation | The adapter executed shared, mode, then private CFGs. A private `server.cfg` therefore replaced the allowlist/rotation after the canonical policy. Execute shared, private (including nested execs), then mode, then native rotation. Private files remain intact. |
| Valid installed maps rejected | The effective overwritten rotation was sometimes only Crash; the catalog itself contained only four maps. The catalog now declares all 21 installed map scripts with pinned waypoints; packaging rejects selected maps outside the prepared manifest. Native votes continue to use the effective rotation, without a second allowlist. |
| Voting disabled during gameplay | Original `promod/comp.gsc` sets `g_allowVote=0`; workspace preparation omitted the existing opt-in voting overlay and the catalog omitted the native vote profile. Package `--allow-map-voting`, validate its presence for an enabled mode, and let the catalog own the existing native vote settings. |
| Bots block Ready Up | Original `promod/readyup.gsc` initializes every player as unready, waits for a use-button press and can open a recording-confirmation menu. Bots cannot complete those human controls. A small verified overlay evaluates bot team/class eligibility in that same loop and skips bot-only input/recording paths. Human paths remain unchanged. |
| Startup can keep an obsolete map | Inherited `+map mp_crash` expressed an explicit startup target and a private remaining-rotation cursor could survive configuration loading. The adapter now enters `+map_rotate`; the engine discards a remaining cursor when no server is running. The existing shuffle selects from the effective canonical rotation. |
| Completed match restarts the same map | The merged engine already contains the gated terminal-match correction and native no-repeat shuffle. Enable the existing `promod_auto_maprotate=1` and `sv_randomMapRotation=1` in the final mode policy. No second rotation implementation is added. |

## Exact startup and map lifecycle

`Com_Init` parses `+set` variables early, initializes the filesystem, executes
`default_mp.cfg`, reapplies startup variables, initializes the server/cvars, then
queues startup commands through `Com_AddStartupCommands`. Thus argument order
does not turn `+set` into a late CFG override. The workspace validates selected
mode metadata and passes its capacity before initialization; a conflicting
private capacity is rejected. Filesystem, purity and artifact-shadowing checks
remain in place.

The startup command buffer executes `canonical-shared.cfg`, ordered private
CFGs, `canonical-mode.cfg`, and `map_rotate`. `Cmd_Exec_f` inserts the requested
file at the front of the remaining buffer, so nested private execs finish before
the final mode CFG. The final mode owns the variables it declares, including
rotation, native vote profile and purity. Private credentials and permitted
environment settings (for example the download base URL) survive. PB-warning
policy is a shared default, preserving the existing private zero override.
Promod still enforces its other original competition settings after map load;
this change removes only its voting prohibition, not every `comp.gsc` rule.

Map scripts call the original initialization and the existing bot integration.
Promod competition setup no longer replaces the catalog vote setting in the
prepared voting profile. Cvars survive ordinary rounds and map changes; new
processes execute the same ordered startup. No recovery CFG exec is used by the
qualification fixture after startup.

## Ready Up and voting

The pinned Ready Up implementation iterates `level.players`, has a nonempty
player guard (`level.players.size<1`), and has no explicit minimum-human-player
setting. This guard and all original human controls remain unchanged. No
human-count threshold is replaced with a bot-inclusive count. If an alternate
asset revision introduces a different policy it must be reviewed: preparation
verifies the pinned rawfile identity and rejects missing/ambiguous substitutions.

For each bot in each Ready Up iteration, `ready` is true only when its current
persistent team is allies/axis and its class is defined. Ineligible bots remain
in the original not-ready count. Bots bypass recording-menu confirmation and
use-button polling. Eligibility is recalculated after late joins/team changes;
map/match entity recreation still initializes ready state through Promod. No
permanent `pers` readiness flag or global Ready Up disable is introduced.

`G_VoteClientEligible` is unchanged: native `CS_ACTIVE`, `CON_CONNECTED`, human
address type, and non-spectator team. Calling, casting and native `CheckVote`
share this electorate. Bots cannot call/cast or enlarge its majority. Native map
validation requires an exact safe identifier in the effective `sv_mapRotation`.
The mode enables next-map ballots only, with strict human majority, 30-second
ballots, two calls per player and the existing 120-second process-wide cooldown.
An approved vote sets `g_votedMapName` after the native delay; `ExitLevel`
consumes it at completed match end. Ordinary S&D rounds restart the same map;
subsequent automatic selection uses the existing shuffle and skips an immediate
repeat when alternatives exist.

## Files

Engine: `tools/bots/prepare.py` (private derived Ready Up overlay and manifest),
`src/sv_cmds.c` (fresh-process remaining cursor reset), existing policy/native
regressions, and `tests/promod_runtime.gsc`, `tests/promod_runtime_plugin.c`,
`tests/run_promod_integration.py` (disposable qualification only). The test plugin
is never installed by preparation or packaged by the workspace.

Catalog: `modes/promod/server.cfg` (owned purity, native vote profile and 21-map
rotation), `README.md` (one current ownership/loading contract, replacing
contradictory historical duplicate contracts).

Workspace: `scripts/runtime.py` (startup normalization and capacity conflict),
`scripts/common.sh` (prepare required overlays), `scripts/modes.py` (overlay
validation and shared PB policy), `tests/test_modes.py`, `tests/operations.sh`
and `README.md`. No map list is hardcoded in workspace implementation.

## Validation and rollback

Base engine: `5c2d5b094c34b6756993e8f59d9a91de52381e1b`.
Catalog change: `f87f3c3f5d54c3767c278f7a12cfd9342e21ca4b`.
Workspace change: `da41cb88b7580fbccb6300f017b7b68b9a26eb78`.
Pinned dependencies remain in `bots/dependencies.json`: Bot Warfare v2.2.0
`7b52b462e40fa68287b9e54602e52da83b17766c`, original Promod LIVE V2.20 EU
and all eight administrative-header hashes. No dependency revision changes.
The original PoC, existing prepared runtimes and licensed asset inputs remain
untouched; each qualification run creates a new private runtime copy.

Engine compilation (`make -j4`, GCC 16.2.1 20260810, NASM 3.02) passed as ELF32
build 1261, retaining inherited PIE/text-relocation warnings. Executable SHA-256:
`ba9214288205b2bae80624602a74de02aada9934ec91ca1956e00b3b8b945ec2`.
All 28 engine Python tests pass (one existing skip); native rotation and native
callvote/vote/CheckVote harnesses pass. All 21 workspace Python tests and the
stubbed operations suite pass; the latter makes no real SSH/deployment calls.

The combined runtime runner imports the actual workspace adapter/catalog
validator and translates only filesystem roots for its disposable local process.
Private fixtures contain nested obsolete Crash-only rotation, stale remaining
cursor, disabled voting/randomization/match rotation, and an obsolete public-mode
selection. RCON snapshots verify effective state, without relying on strings in
packaged scripts. An initial accepted combined run is preserved privately at
`/tmp/cod4x-promod-integration-kl93ewj8/results.json`.
It passed fresh startup and process restart, 12-bot automatic Ready Up, real UDP
human-priority admission, mixed Ready Up, original use-button behavior on a
synthetic human, bot team-change eligibility reset, bot vote rejection, invalid
map rejection, a 2-of-3 human ballot with a bot excluded, an actual accelerated
two-round S&D death/round/match lifecycle and approved-map selection, RCON
administration, and loading/navigation readiness/vote-policy retention on all 21
maps. Purity stayed 1 with eight headers and no script/fatal errors.

The final expanded run at `/tmp/cod4x-promod-integration-qj2dj9ok/results.json`
passed all 52 checks using the committed catalog/workspace changes above. It
also included an obsolete private `sv_pure=0` (restored by the final mode CFG),
verified that cooldown survives the match/map transition, waited for the real
120-second cooldown, and passed a second ballot with one synthetic human and
bots on the new map. Independent startups selected Backlot and Shipment. An
audit confirmed all three Promod files and all eight header hashes unchanged,
and both processes ended with pure=1. Native runtime ballot logs show the bot
cast left the yes count at one before the second human passed the 2-of-3 vote.

Native active-human gameplay is exercised using a **test-only** plugin that
marks existing entities as synthetic humans and invokes the original client
command path. Ready Up input sets the native use-button fields. Recording
confirmation is fixture-satisfied because its menu needs a graphical client.
Synthetic humans are restored to bots before restarts; they do not emulate a
network client's reconnect protocol. The real UDP admission fixture establishes
only a connected client. Match completion uses normal deaths but shortens the
round limit to two in the test script; it is not a full MR12 certification.
All-map loading/navigation is not all-map bomb-objective or combat certification.

Earlier rejected fixture runs remain under
`/tmp/cod4x-promod-integration-9_587aga`, `mgss_idi` and `6pgmrhkj`
(with the same directory prefix). They exposed stale synthetic bot input/lifecycle and
incomplete fixture button handling. They are not counted as accepted evidence.
The earlier snapshot reader also incorrectly depended on synchronous logging,
which original competition rules disable; snapshots now use local RCON cvars.

Graphical human ready/unready toggling, demo-confirmation UI, vote HUD/console
messages, authenticated reconnects across maps, full competitive matches,
plant/defuse, all-map combat and long-duration play remain manual validation.
The production command path is tested, not a substitute graphical client.

Rollback consists of reverting the three focused PRs and rebuilding the prior
reviewed artifact. Existing immutable artifacts/private files remain available;
there is no persistent data migration. Do not mix the old startup order with the
new configuration ownership contract. Nothing has been deployed or merged.
