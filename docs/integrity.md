# Administrative IWD headers

The optional startup setting `fs_localizedHeadersPath` loads eight administrator
provided headers from its `addiwdheaders/` directory: localized_english_iw00.dat
through localized_english_iw06.dat and jcod4x_00.dat. With an empty setting, the
existing upstream loader remains in use. `sv_pure` is not disabled or bypassed.

All eight inputs must exist, be nonempty, smaller than 16384 bytes and have a
length divisible by four. The loader computes keyed checksums using the current
filesystem checksum feed, and publishes the additional checksum list only after
every file validates. Filesystem shutdown clears the list and count.

The working source was previously uncommitted on fix/localized-iwd-integrity.
This change preserves that filesystem implementation verbatim. The separate
20-line PURE_DIAG block in sv_client.c is temporary diagnostic instrumentation;
it is preserved privately, not included here. Existing upstream verification,
including CoD4x client IWD handling, is otherwise unchanged.

No runtime memory configuration changes were found in the source diff. Existing
com_hunkMegs/com_zoneMegs defaults are upstream behavior, not part of this patch.
Private build binaries and A/B diagnostic artifacts are not tracked.

Run `python3 tests/test_integrity_headers.py` for malformed/missing input and
atomic-publication checks against the actual loader function. It compiles a
small native harness with a deterministic checksum stub; it is not a test of
the checksum algorithm or of client-side pure authentication. The historical
PoC loaded all eight real headers with pure enabled; human-client validation
remains separate.
