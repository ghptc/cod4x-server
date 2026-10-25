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
