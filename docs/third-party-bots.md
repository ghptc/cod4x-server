# Third-party bot sources and notices

Bot Warfare: https://github.com/ineedbots/iw3_bot_warfare,
tag v2.2.0, commit 7b52b462e40fa68287b9e54602e52da83b17766c.
The tag's internal bw_version still says 2.1.0; use the Git revision and hashes.
Credits: INeedGames / INeedBots, CoD4x Team, PeZBOT team, Ability, Salvation.
The upstream README expressly permits use, hosting, modification and merging
with credit. No standard SPDX license file is supplied by that revision.
Its sources and waypoints are local verified inputs, not vendored in this fork.
Retain that README and its notices with any generated runtime distribution.

Promod LIVE V2.20 EU is a local input, not redistributed here. Its public source
license is PModEPL, in addition to Activision's map-tools terms:
https://github.com/cod4mw/promod/blob/d22de10be2625674f252be29448530220db48228/LICENSE.md.
Preserve original notices and modification dates, offer modifiable sources and
license derived mod assets under PModEPL when distributing/hosting them. The
integration GSC is offered under those same mod-asset terms. CoD4x engine changes
retain this repository's AGPL license and notices. No proprietary game assets,
Promod fastfiles, extracted rawfiles, or integrity header data belong in Git.

The preparation tool changes bot thread lifetime and weapon-class lookup, omits
stock bomb callback replacements and an unused weapon-drop helper, and creates
private map wrappers. All modifications are dated 2026-10-25 in generated files.
Those wrappers contain installed map initialization and must remain private
local test artifacts unless redistribution rights are independently verified.
