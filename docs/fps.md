# Promod 40–333 FPS menu policy

The owner reproduced `SET COM_MAXFPS WITHIN 40-250` and restricted movement at
333 FPS in a real client; 250 works. The exact string and range expression are
present in the **zlib-decompressed menu assets** of the installed LIVE V2.20 EU
fastfile. They are not readable GSC source or a server cvar. Searching compressed
`mod.ff` with strings cannot rule out this check.

The matching [author source](https://github.com/promod/promod4/blob/d22de10be2625674f252be29448530220db48228/ui_mp/hud.menu)
has the upper bound in DVAR_ENFORCER and the ENFORCE message condition. The
compiled menus expand this into three comparisons: xpbar visibility, talkers
visibility, and the FPS warning item's visibility. The shared predicate also
activates xpbar's sound loop. Client HUD enforcement is confirmed; the reported
movement symptom still requires post-fix graphical validation. No GSC
freezeControls call or server timestamp gate specific to 250/333 was found.
This PR does not claim to have traced every closed-source client input effect.

SV_UserMove rejects duplicate/old timestamps and requires pure authentication;
SV_ClientThink bounds future times; ClientThink_real clamps timing and rejects
nonpositive deltas. Nominal 125/250/333 FPS intervals are 8/4/3 ms respectively.
These findings do not justify relaxing any server command-time or pure check.
The previous client config's value of 85 does not explain the explicit HUD rule.

No existing installed ruleset dvar configures this upper bound. Do not enable
sv_cheats, change LAN mode, hide the whole enforcement HUD or disable pure.

## Local rebuild

`tools/promod/fps333.py` derives two editable menu sources from the actual pinned
installed fastfile using the original [OpenAssetTools](https://github.com/Laupetin/OpenAssetTools)
v0.34.0 typed parser/linker. It changes only the upper bound and message to 333;
40 and all other predicates remain. All other menu objects are reused from the
original fastfile. Two menu-list containers are required to load the modified
menu objects before the original inventory. This is a source rebuild, not a
binary search-and-replace.

Use the official `oat-linux.tar.gz` v0.34.0 archive, SHA-256
`f8a60b5bda51fa3e7eb2dda6494b42b2e7c6298b0fe1894d75db0c8eee660c22`.
The script verifies both executable hashes, rejects unknown Promod hashes and
existing output directories, and fails on tool-reported errors even if exit
status is zero. OAT is GPL-3.0; it is an external local build tool, not a server
dependency. No tool binaries or proprietary assets are committed.

```sh
python3 -m unittest discover -s tests -p test_fps_menu.py
python3 tools/promod/fps333.py --promod /private/pml220/mod.ff \
  --oat /private/oat-v0.34.0 --output /private/fps333-build
```

Output: `project/zone_out/fps333/mod.ff`, private editable sources, bounded build
logs and a manifest. Before accepting it, the tool reparses it and verifies the
original inventory, unchanged extracted assets and complete boolean expression
trees, preserving precedence and every unrelated check. Local qualification
compared 141 extracted assets, with only xpbar/talkers changed. No other menus,
GSC scripts or localization changed. The original mod.ff and IWDs stay intact.
Fastfile output compression may vary between runs; use the actual output hash
in its manifest rather than assuming a fixed generated hash.

Keep generated mod assets private and preserve the original embedded Promod
license/notices. Derived menu changes dated 2026-10-25 remain under PModEPL;
see docs/third-party-bots.md. Keep editable derived source available with any
authorized distribution. Original game assets are never redistributed here.

For later approved homologation, first prepare a separate runtime from the
original pinned inputs, then copy only the verified derived mod.ff into **that
copy**, recording the manifest/hash. Keep both IWDs/eight integrity headers
unchanged and mount this runtime read-only. Clients must receive the updated
mod.ff through the normal download/reconnect path; no client installation edits
or integrity bypasses are proposed. Do not alter the global pinned original hash
to pretend the derived file is an original input.

## Acceptance and rollback

Local headless tests validate asset loading and bot compatibility, not rendered
FPS or movement. Real-client post-fix checks at 125, 250 and 333 remain pending.
Also test 39/40 and 334: values outside 40–333 must still trigger enforcement.
Observe WASD displacement and jumping after freeze/ready-up periods, HUD text,
pure/download/reconnect and the same map/team/class at each rate. Capture client
version, actual rendered FPS and console errors. Physics can depend on FPS;
accepting 333 is an explicit competition-policy change, not proof of identical
125/250/333 physics. Keep tournament rules separate.

Rollback uses the original verified private mod.ff plus normal reconnect and
client asset negotiation; no engine or IWD integrity change is involved.
No EC2 inspection, deployment or client configuration change is authorized by
this PR.
