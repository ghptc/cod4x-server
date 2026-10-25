# Preserved PoC 001 evidence

The working uncommitted PoC was preserved before fork changes, with 580 files
hash-verified into a private persistent archive. Neither original repository nor
the original /tmp workspace was overwritten. The archive contains local inputs,
raw logs, source snapshots, diagnostic builds and exact reproduction commands.
These are deliberately not committed as game assets or generated artifacts.

The original accepted combat run lasted 140.09 seconds: slots 0/1 used Promod
assault classes, acquired one another, traversed 224 Crash waypoints, fired
43/34 shots and produced Promod damage/kill records in both directions.
The independent 45.07-second slot test freed both slots, displayed an empty
status table and allocated the same slots again. Both final runs had zero
GSC/fatal errors, sv_pure=1 and unchanged executable, Promod files and eight
headers. Earlier failed attempts remain in the archive and are not passed tests.

This historical result is not a production certification or evidence that the
new Auto-Fill controller passes. Record those results independently. Match
ready-up, bomb objectives, online human clients, long-duration testing and
resource limits on EC2 were not certified by the original PoC.

See bots/dependencies.json, bots/promod_ai.gsc and tools/bots/prepare.py for the
minimal integration sources and exact private input identifiers. Preserve the
upstream README/notices with the local Bot Warfare checkout.
