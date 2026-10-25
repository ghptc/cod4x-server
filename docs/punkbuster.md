# Promod PunkBuster warning policy

Confirmed against the installed LIVE V2.20 EU `mod.ff` SHA-256
`930c9123b679394c18683f890d8e792d3b31cafacadda2c3293e5e066e9fb1c2`.
`promod/servercheck.gsc::errorMessage` broadcasts the reported warning with
`iprintlnbold` every two seconds when PB is disabled, LAN_MODE is false and
PROMOD_PB_OFF is false. It does not kick or freeze the player. This HUD warning
is separate from actual engine PB authentication and IWD pure verification.
`src/common.c::Com_Init` disables sv_punkbuster if native PB initialization fails;
setting that cvar to 1 is not a substitute for a working PB service.

The installed `promod/modes.gsc` accepts `_pb` for match/knockout modes, as
documented in the [Promod author's readme](https://github.com/promod/promod4/blob/master/readme.txt).
`custom_public_pb` is invalid. `custom_public_lan` suppresses the warning but
also disables antilag/smoothing; do not use it as a cosmetic workaround.

For a server whose owner explicitly accepts operation without PB, prepare the
private runtime using the existing arguments plus `--allow-no-punkbuster`.
Then set `promod_allow_no_punkbuster 1` before loading the map. This acknowledges
that PB is absent; it does not provide anticheat. Leave the option/cvar off on
servers whose policy requires PB, and repair PB there instead.

The local generator derives `promod/servercheck.gsx` from the exact hash-verified
installed source rawfile, adding only this explicit policy condition to the PB
HUD warning. All pure/IWD, health, connection and other server checks remain.
No compiled proprietary assets are edited or committed. Generated private
scripts retain the Promod attribution/license obligations documented in
`docs/third-party-bots.md`. Reprepare without the option to remove this overlay;
set the cvar to 0 to restore the warning while the overlay remains loaded.

Validation: `python3 -m unittest discover -s tests -p test_punkbuster_policy.py`.
Local runtime compilation and graphical warning on/off validation are recorded
in the PR. A headless server cannot prove that a human HUD stopped displaying
the message. Graphical validation remains pending until the owner tests it;
no EC2 service or runtime setting is changed by this PR.
