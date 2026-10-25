# Local bot integration validation — 2026-10-25

Code revision: `91ab44eb0ea736ab424f976b373bf36c06acb60e`.
Separate integrity revision: `2dbc966fc6e064aebd22be5776c9fa5a1e052174`.
The clean validation clone used the bot revision plus the integrity filesystem
patch in its working tree; the branches were not merged or rewritten.

Fresh build: Linux ELF32, Intel 80386, custom build 1232. GCC 14.2.0
(Debian 14.2.0-19), NASM 2.16.03, existing local build image
`sha256:92528811226fabd05fee63074e22b7b5afd0fa9d63d5994bd3a8f74c8543cbfe`.
Executable SHA-256:
`05b7c3e38f293a664cab530ea68a36a34affba85352671f1419a292e1356bb11`.
The inherited PIE/text-relocation linker warnings remain; there were no compiler
errors. No release, tag, image publication or CI configuration was created.

Six integrity loader harness tests and the native bot-policy assertions passed.

| Runtime scenario | Duration | Assertions | Shots logged | Kills logged |
|---|---:|---|---:|---:|
| policy | 75.23 s | Passed | 0 | 1 |
| rotation | 135.17 s | Passed | 297 | 18 |
| burst | 30.17 s | Passed | 35 | 2 |
| final gameplay | 45.13 s | Passed | 179 | 8 |

The policy test verified 12 bots initially, rejection of an invalid g_password
without eviction, admission of a valid UDP challenge/connect by replacing one
bot, pause with a connected human, pause retention on Backlot, last-human
reactivation, empty-server kickall guard across a map change, manual resume,
and pause-without-removal. Readiness may legitimately be zero during round
end while the native pause state remains unchanged.

Rotation covered Crash → Backlot → Strike → Crossfire → Crash. Every map
restored 12 bots; classes, opposing teams, navigation, targets, shots and
Promod-attributed kills were observed. The burst test admitted six simultaneous
loopback challenge/connect fixtures into a server initially filled with 12
bots, leaving six connecting humans and six bots. No bot-induced full response
occurred. The final 45-second gameplay run used the fresh commit-identified
build, not the historical PoC executable.

All accepted runs had zero GSC/fatal errors and sv_pure=1. The three Promod
artifacts and all eight real administrative headers matched their input hashes
after testing. The first policy fixture used the wrong password cvar and was
rejected as evidence; it remains archived. No server restriction was bypassed.

Raw evidence, exact command/input records, the binary and the validation diff
are preserved privately under `~/Projects/cod4x-poc-001-preserved/new-integration`.
The original 580 preserved files and both original Git states were rechecked
unchanged. No generated binaries, full logs, vendor source, headers or game
assets are committed here.

## Remaining qualification

The integration defaults off and is experimental. UDP fixtures do not establish
Steam authentication, human-client pure/download compatibility or graphical
human gameplay. Full match ready-up, bomb planting/desarming, all 21 waypoint
maps, smoke/grenade interactions, long-duration operation and EC2/Bard resource
headroom are not certified. Those are follow-up gameplay/qualification work,
not authorization to deploy or begin unrelated administration commands.

## Final compatibility follow-up

Engine revision `3b7ff13c091d22a9ec8eae49b8fa96af44b73b2a` built successfully
as custom build 1234, with the same separate integrity overlay. Its SHA-256 is
`b4cc80169bdaf9e7c5c6a90b942c86b268ad7b00b2ff63c0ca863283c81236ba`. The extra protocol-21-only restriction was removed from bot-slot
reclamation: legacy protocols already accepted by upstream validation can now
reserve a slot for their existing update path too. A 30.21-second regression
confirmed that a protocol-7 request reclaimed a bot slot and reached the
updater's protected CS_ZOMBIE state without a full-server rejection. With no
network, the upstream update backend cannot resolve; the fixture correctly
reports pending update rather than successful authentication. Eleven bots plus
that reserved updater slot is expected, not a leaked free slot.

Script revision `4c72816` restores all-player model-readiness and smoke metadata
registration. The perception core requires this metadata for human opponents
as well as bots. No Promod callbacks or automatic admin permissions were added.
The final 45.13-second gameplay regression passed with these scripts and the
legacy-compatible executable: 12 classes, both teams, navigation, targets,
168 shots and 9 kills, with zero GSC/fatal errors and pure enabled.
AI source SHA-256: `85d365e5fff7fb43974beb5c5bfe71c7c38e31887033c4e24aea2453c2f66361`.

Real graphical-client combat and smoke behavior still require manual validation;
the metadata fix is not presented as a completed human-client test. The initial
legacy fixture assumed immediate backend rejection and was rejected as evidence;
its corrected pending-update expectation follows existing upstream behavior.
All earlier evidence remains preserved. No production service was changed.

## Population and difficulty controls — local qualification

Native code revision `7e6167e56d4816e8022a0bfb8419bd9290c1b7e0`, clean
Linux ELF32/i386 build 1244, SHA-256
`a897db668b4e40d957b34a01a5cc88be8d1b4b6efd5d57384b937124f9520b38`.
The same pinned GCC/NASM image was used. Test revision `bb40706` additionally
waits for native AI readiness before manual-add assertions; native code is
unchanged. Six integrity tests and the expanded C policy/count-parser tests pass.

Accepted isolated scenarios: controls (117 s), existing policy (75 s), active
rotation (135 s), missing waypoints (30 s), and all 21 installed map wrappers
with zero bots (240 s). Counts 0/2/3/4/12, caps, invalid arguments, slot removal
and reuse, map-persistent pause/limit, last-human resume and missing-navigation
rejection all passed. Six simultaneous human handshakes displaced six bots;
a seventh displaced another bot after bot_enable was disabled. These fixtures
do not enter the graphical game world. A real unauthenticated RCON request was
denied without changing population. Existing command-power routing is retained;
new mutation commands register power 80, status 20.

Mixed bots selected multiple real BW tiers in 1..7; easy/hard/fixed changes
produced the expected original aim profiles. The legacy fixed profile remains
the default. Active rotation still showed combat and navigation; no script or
fatal errors were recorded in accepted runs. sv_pure=1 and all eight headers
remain intact. Early fixed-time manual-add tests hit legitimate round-transition
rejections and are retained as rejected evidence; readiness is never bypassed.

Evidence and exact private artifacts are preserved outside Git under
`~/Projects/cod4x-gameplay-controls/20261025`. No EC2 access or deployment was
performed for these changes. Graphical FPS/PB/human combat and voice tests
remain separate pending qualifications.
