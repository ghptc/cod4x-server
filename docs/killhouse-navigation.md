# Killhouse navigation recovery

## Root cause and scope

Protected baselines on 2026-10-27: engine
`dc11efab474a4ad81d91ca158f2bada827c9dfae`, config
`ec4432e36e723f83b4a4e4033d4d5fd4b6a6963d`, workspace
`6c5b4b3a0ff92d2898a179904335c5c85e8863ee`. Death-inflictor guarding,
spawn-angle initialization, Classic `btd_anticamp=0`, the administrator message,
`sv_pure=1`, eight administrative headers and native voting remain intact.
Production and existing evidence runtimes were not changed.

Killhouse navigation is present in the original BTD Alpha 001 fastfile. The
map directory selects global offset 4827 in `waypoints/PeZBOT_WP_4.csv`.
Keys 4827..4927 contain 101 nodes. Key 4928, column 1, is `"end "`, with a
trailing ASCII space. Every other relevant loader sentinel is `"end"`.
`LoadStaticWaypoints()` compares that cell literally with `"end"`; the padded
marker fails comparison and is tokenized as an XYZ vector. Only token zero
exists. Undefined coordinate tokens reach `atof()` (`svr/pezbot.gsc:1928`, called
from coordinate conversion at line 2029), terminating the native server.
This is a malformed terminal cell, not missing navigation or missing coordinates
inside the 101-node graph.

The exact native negative control records `BTD_NAV_MARKER value=[end ] length=4`
and the original stack. Original fastfile SHA-256 remains
`50911fdd0273b50e26983723619881acfaed4aa65f4d91a799a341464c2224a6`;
its decompressed payload has exactly one `end ` followed by NUL at offset
2219104. PeZBOT plaintext source is pinned to
`ebe235fd9a6f5879c1aacb7b79e1ff87fb99d617ca8dd347737e5e88abc91f09`.

## Small correction and private preparation

`tools/btd/prepare.py` generates private `svr/pezbot.gsx` from that pinned
plaintext source. One ASCII insertion normalizes the marker only when all of
map name, table name, offset, node count and original padded value match this
specific defect. It then executes the original terminal check. No coordinates,
children, node types, pathfinding, zombie health/speed/damage, wave defaults or
player callbacks are changed. Other malformed inputs still fail.

The original FF is copied byte-for-byte. The original script has CP1252 comment
bytes, so navigation generation uses a reversible Latin-1 byte mapping rather
than UTF-8 replacement/recoding. Removing the insertion reconstructs every
original source byte. Existing death and spawn overlays are preserved.
No graph regeneration or new waypoint coordinates are necessary. Altering the
serialized fastfile in place would risk pointer/offset corruption and is avoided.
The generated proprietary source and all extracted tables stay outside Git.

The preparation manifest records the third overlay hash and pinned
`navigation_source_sha256`. The companion workspace change validates the exact
three-overlay set and file identities. Legacy two-overlay preparations remain
usable only without navigation declarations/files and without requested Killhouse.
Missing, changed, extra, unpinned or symlinked navigation is rejected. No checks
are bypassed to package the new runtime.

## Graph and geometry evidence

Private export validation found 101 distinct finite XYZ nodes and 374 directed
edges. Every child index is in range, every edge is reciprocal, and every node
is reachable from every other node. There are no duplicate origins/self-links.
All nodes are `stand`; this table has no angle column. Spawn angles are provided
by the existing initialized-vector fix, not invented from waypoint data.
All 25 vendor spawn positions associate with this connected graph; maximum
nearest-node distance is 153.463451349 engine units. Proximity alone is not
collision clearance, and graph connectivity alone does not prove gameplay.

`tools/btd/navigation.py` validates private CSV exports, including exact node
keys and terminal shape, three ASCII numeric coordinates representable as finite
native floats, strict child syntax, index bounds, reciprocal links, connectivity
and all 25 spawn indices. Synthetic tests reject malformed/undefined/nonfinite
coordinates, malformed markers, disconnected graphs and invalid links.

## Private table inspection provenance

Existing local OpenAssetTools Unlinker v0.34.0 was used only for inspection:
SHA-256 `fe36b530f638b87410a3a651663217824c89c98209211ac4265e733b1409ea23`.
It is not a preparation/runtime dependency and was not downloaded or committed.

```sh
/tmp/cod4x-oat-v0.34.0/Unlinker --no-color --include-assets stringtable -o /tmp/killhouse-nav-inspect/tables /tmp/cod4-btd-prepared/mods/btd_alpha_001/mod.ff
python3 tools/btd/navigation.py --table /tmp/killhouse-nav-inspect/killhouse-fixed-table.csv --spawns /tmp/btd-allies-inspect/btd_gametypes/survival/_survival_spawns.gsc
```

The private validation copy replaces the unique bytes `4928,end ,0,0` with
`4928,end,0,0`; this copy is never packaged. Original CSV SHA-256:
`784b1dbf458d6281ef3c67c39898d5ec88f00b642c9944a542890850fa11ba40`;
validation CSV: `4c5623e87bf6757f0934cf47efa058744bfdfa3090b0f9f902e3d04dcca34bc8`.
Both have 1104 rows and identical shapes; all node cells remain unchanged.
The private spawn source matches its existing preparation lock.

## Reproduction and current qualification gate

Prepare a NEW private runtime using the existing authorized recipe and package
it against the reviewed workspace/config checkout. Preserve the source package,
existing PoC, and older evidence directories. For native tests:

```sh
python3 tests/run_btd_navigation.py --runtime PRIVATE_RUNTIME --game GAME_DATA --binary bin/cod4x18_dedrun --original-waypoints --expect-waypoint-defect
python3 tests/run_btd_navigation.py --runtime PRIVATE_RUNTIME --game GAME_DATA --binary bin/cod4x18_dedrun
python3 -m unittest discover -s tests -p 'test_*.py'
python3 tests/run_btd_integration.py --runtime PRIVATE_RUNTIME --game GAME_DATA --catalog CONFIG_CHECKOUT --workspace WORKSPACE_CHECKOUT
python3 tests/run_promod_integration.py --runtime FRESH_PROMOD_RUNTIME --game GAME_DATA --catalog CONFIG_CHECKOUT --workspace WORKSPACE_CHECKOUT
```

The native navigation fixture uses actual vendor zombies, authored graph nodes
and native collision traces, not synthetic movement or damage notifications.
Fixture-only grace and initial-wave size shorten waiting; AI speed, damage,
enemy health and production configuration stay unchanged. The fixture gives
only its synthetic player high health so the same zombie can be observed through
an extended chase; this is not balance or player-survival evidence. A second
synthetic survivor keeps the vendor's normal sole-survivor game-over logic from
ending the initial suicide/respawn case; it is removed before the wave trial.

Spawn-to-node checks and continuous chest-height trajectory checks use native
rays and point floor traces, not swept collision-hull tests. A tracked obstacle
detour does not cover every graph edge, elevated route or many-player condition.
Synthetic client behavior does not certify graphical client gameplay. Full
private logs are never committed.

## Final local evidence

Native Killhouse: **12/12** checks at
`/tmp/btd-navigation-bp4wboij/results.json`. The final fixture and runner hashes
match that run. Native original-failure control: **2/2** checks at
`/tmp/btd-navigation-_0ak_ar_/results.json`, preserving the original marker and
exact undefined-coordinate stack. Both retain the original FF bytes.

| Native measurement | Result |
| --- | --- |
| Loaded nodes / floor-supported visible spawn links | 101 / 25 |
| Maximum spawn-link distance | 153.463 units |
| Settled elevation above lowest authored surface | 232 units |
| Initially blocked direct path | 684.002 units |
| Continuous tracked-zombie route / waypoint changes | 820.466 units / 3 |
| Closest approach / attributed melee | 35.3553 units / passed |
| Native firearm hits / vendor-credited kills | 25 / 5 |
| Vendor wave two / native death and respawn | passed / passed |
| Elevated camping without punishment / teleport | passed |
| Killhouse → Crash → Killhouse / script errors | passed / none |

Fixture SHA-256:
`aee120ec5da1d122bbc798cd0bd830947ee1447fd30eac69b50f18943d4e0fbc`;
runner: `6b8de903314e4e61ea5ff7b7cab252538d0f966e97607f308adaf0992cc4fe5d`.
Generated navigation overlay:
`10fb2268d2ea64c14d0a7040e180151265a4b2827ebc44068e82831a18ff9c56`.
Native executable:
`ea3d0097320095f7d9080248b6f4ea63a65d646a3bd10f68794a8756a6368918`.
Results also record prepared manifest and baseline/fixture configuration hashes.

Existing 15-map integration passed 71/71 checks at
`/tmp/cod4-btd-qualified-p1egu0_k`: both startup/restart, all supported maps,
configuration precedence, pure mode, eight headers, administration and no script
errors. Engine unit suite: 59 tests, success with one optional public-client test
skipped. Native vote and rotation suites passed. All seven existing BTD native
expression/death/Classic/negative-control/lifecycle scenarios passed; aggregate
private evidence: `/tmp/killhouse-baseline-regression-results.json`, including
lifecycle `/tmp/btd-death-regression-ossnz59o`.
Freshly generated pinned Promod overlays passed **53/53** checks at
`/tmp/cod4x-promod-integration-0gz_upfe`, including all map loads, ready-up,
voting, match transitions and bot administration. Companion workspace: all
50 Python tests and the complete mocked operations suite passed. Independent
review passed after corrections to tokenizer parity and native evidence gates.
Hosted CI status and owner review remain explicit PR gates.

Killhouse stays outside the Zombies rotation and preparation's original rotation
map list. Do not describe loader success as full playability. Owner approval is
required before merge; existing mandatory CI must pass. After approved merges,
prepare homologation using the existing reviewed workflow and request explicit
operator authorization before deploying it. Then require supervised real-client
chase/obstacles, elevated/camping positions, attacks/kills, waves, death/respawn,
reconnection and transitions. Only then review the rotation/manifest qualification
change. No merge, deployment or promotion is automatic.

Rollback: revert the focused preparation/packaging PRs through the existing
reviewed process; retain the death/spawn fixes and Classic policy. Existing
legacy prepared runtimes remain supported for the original 15 maps. Any service
rollback requires operator approval and the exact previously approved artifact.
