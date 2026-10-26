# Zombies connection investigation — 2026-10-26

The reported `CL_CGameNeedsServerCommand: a reliable command was cycled out`
has **not been reproduced** by this investigation. No production protocol,
validation, buffer limits, or asset bytes were changed. This work starts from
protected master `cb0f0f4` and adds behavioral characterization for continued
investigation.

## What the code and assets establish

- Server command storage has 128 slots. Unsent replaceable commands can be
  compacted/coalesced; sent commands remain pending until acknowledged. A 129th
  outstanding unique critical command requests an overflow disconnect.
- Download payload messages use `SV_SendReliableServerCommand` and its separate
  reliable transport. The native fixture verifies they do not consume the
  gameplay command ring. Download duration and command cycling can therefore
  interact through connection/loading lifecycle; they are not proved to share
  a cause merely because both appear during a connection.
- The current shared configuration disables HTTP redirection
  (`sv_wwwDownload=0`). The server defaults `sv_maxDownloadRate` to 1,024 KiB/s
  shared across downloading clients. This is a configured limit, **not measured
  transfer throughput**. Congestion-window backpressure further constrains sends.
- Original BTD payload sizes are `mod.ff` 12,033,844 bytes,
  `btd_weapons.iwd` 307,567, `btd_music.iwd` 17,789,555 and `btd_images.iwd`
  3,070,864: **33,201,830 bytes total**. Disabling music does not remove the
  original IWD from the referenced-package list. No asset trimming is proposed.
- `SV_DoneDownload_f` closes the transfer and requests a fresh gamestate.
  That callback is covered; actual gamestate payload delivery remains uncovered.

## Real-client attempt and limits

A disposable loopback server used the existing BTD runtime with fresh writable
home, canonical configuration, integrity headers, `war`, and `mp_convoy`.
An isolated game directory and new Proton prefix contained no downloaded BTD
assets or copied private player profile. Only already-installed client engine
patches were copied into that prefix. The client log identified CoD4x 21.1;
no client update was applied. The server identified build 1270.

The client initialized but exited before reaching the loopback server.
Its log contains shutdown and audio initialization errors, not the reported
reliable-command error. Consequently there are no valid clean-download elapsed
times, transport traces, successful connections, or gameplay measurements.
Further client launches and GUI input stopped when the operator requested it.
The disposable server was stopped. The client and production installations were
not changed by these tests.

## Behavioral tests and independent review

Run `python3 -m unittest discover -s tests -p test_reliable_commands.py -v`.
The harness compiles unchanged production functions with actual 32-bit engine
types and message writers. Seven scenarios passed:

1. Retransmission is byte-identical until a directly assigned acknowledgment;
   500 commands cross multiple ring wraps in batches of ten.
2. Coalescing and pre-active compaction preserve already-sent command text.
3. An unacknowledged producer reaches the 128-command boundary and requests
   the existing overflow disconnect on command 129.
4. A size-limited recovery message retains its unsent tail for a later send.
5. A 33,001-byte deterministic download payload arrives byte-for-byte through
   the transport fixture without changing the gameplay command ring.
6. Transport backpressure pauses reads; two downloading clients share the
   configured download budget.
7. Download completion closes its file, clears transfer state, and invokes the
   gamestate boundary afterward.

Filesystem, congestion window, transport delivery and gamestate callback are
fixtures. Acknowledgments bypass the packet parser. No real frame callbacks,
client command consumption, network loss, real download throughput, or actual
gamestate payload are exercised. No coverage percentage is claimed.
An independent reviewer ran all seven cases and reported no critical or high
findings. The existing production coalescing fallthrough compiler warning
remains; no production code was altered to suppress it.

## Remaining P0 experiments

When the operator authorizes client sessions again, compare clean download,
cached reconnect and delayed asset loading on the same client/server revisions.
Capture command generation, sent/acknowledged sequence numbers, gamestate
baseline and client CGame execution sequence alongside monotonic transfer
sizes/timing. Separate lost ordinary command packets before reliable gamestate
from more than 128 commands received while CGame has not executed them.

The out-of-window ACK branch currently replaces the acknowledgment with the
server sequence and returns. Whether a stale packet during long loading reaches
that branch is unproved and not covered by the new harness. The two channels'
ordering at gamestate transmission also requires a real trace. Do not reset
client execution sequences, widen buffers, or weaken ACK validation based on
these hypotheses.
