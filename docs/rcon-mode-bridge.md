# Authenticated RCON mode bridge

Baseline: protected master `701a7c5df46c5723705dad0408afa44fb89b0ad9`.
The previous `change_mode` preflight remains nonmutating for console, command
buffers and GSC. Authenticated UDP and Source RCON have a separate native ingress
for exactly `change_mode promod`, `change_mode zombies`, or `change_mode` status.
Both registration and ingress require power 100. A command-power metadata change
cannot lower the native floor. No console/GSC invocation inherits an ambient
"authenticated" flag.

Only the authenticated ingress submits a fixed packet over nonblocking Linux
`SOCK_SEQPACKET` to `/run/cod4-mode-bridge/control.sock`. The engine checks the
host peer is UID zero. No path, executable, image reference, shell, Docker API,
password, account name or arbitrary argv crosses this interface. The host validates
kernel peer credentials against the current production container and executable.
No endpoint is mounted or activated by this change. Windows fails closed.

UDP framing is checked against the complete original payload, including ignored
newline/NUL suffixes and truncation, before accepting a mode command. Source
requests are checked against their complete packet frame. Modes reject quotes,
comments, separators, controls and extra arguments. Mode request logging omits raw
arguments. The existing UDP password and Source account authentication remain
responsible for authenticating the administrator.

Authentication hardening found necessary during this investigation:

- Unregistered commands/cvars no longer bypass low-power Source/Webadmin checks
  via `Cmd_GetPower == -1`. Registered command permissions remain unchanged.
- Source login identity comes from the exact record returned by `Auth_Authorize`,
  not a second username/SteamID-handle lookup. Zero-ID account logins are rejected;
  the authenticated master-console login remains supported.
- Webadmin carries the exact matched session record through dispatch and logout;
  numeric or duplicate names cannot select another account.
- Sub-100 password administrators cannot reset equal/higher-ranked accounts;
  power-100 recovery remains available.
- Source command early exits restore the old invoker and redirect state.

## Asynchronous feedback

Initial output is **submitted**, with an unpredictable operation ID; it is not
acceptance or success. There is no synchronous controller/Docker wait in the game
loop. The frame poll accepts only bounded fixed-enum replies matching that ID.
Embedded NUL, truncated, malformed or mismatched replies are discarded.

After host preflight accepts a durable operation, the engine queues a fixed player
broadcast and acknowledges on the next normal game frame. The host then recreates
the runtime. An engine that disappears cannot cancel the accepted host job; a
still-running engine that fails notification acknowledgment causes denial before
mutation. Network delivery of the notice is not a guaranteed player receipt.

The initiating UDP endpoint receives a safe asynchronous update where possible.
Source clients can poll the status command. The host survives process replacement
and the replacement engine refreshes status; after reconnecting, use:

```text
/rcon change_mode
```

Status reports operation ID, mode, phase and a fixed explanation. Accepted/pending
is never completion. Success requires host verification; `rolled_back` means the
transition failed and the previous exact runtime was verified restored.
`recovery_required` requires operator intervention. Availability is the last host
response and is revalidated for every request.

## Trust and qualification

The qualified engine, native plugins, installed GSC and private authentication
configuration are trusted code/authority. Direct GSC execution cannot submit a
mode request, but a malicious mod that steals or changes the existing credential
can authenticate normally. The bridge is not a sandbox for a compromised game
process. Host authority is still restricted to the two approved immutable images.
Command-policy managers and credential administrators belong to authentication
TCB; do not delegate that authority to untrusted accounts.

Classic UDP RCON is plaintext and has no cryptographic packet nonce. Durable host
request IDs prevent host-request replay/duplicates; they do not repair captured
UDP credentials or network-packet replay. Activation requires protected
administrative transport and explicit operator acceptance of the legacy protocol
boundary. No password is forwarded to the host or added to status/logging.

See workspace `docs/authenticated-mode-bridge.md` for host trust, locking, rollback,
threat model and the gated installation/qualification procedure. Both modes need
independent actual-client qualification, and both images must contain protocol
`C4M1`. No production bridge installation, merge or deployment is automatic.

## Checks

```sh
make -j4
python3 -m unittest discover -s tests -p 'test_*.py'
python3 tests/run_map_rotation.py
python3 tests/run_map_voting.py
```

Native policy fixtures execute the actual bridge, framing, authentication,
Source/Web console, role-reset and session-record functions. Loopback RCON tests
execute the production parser/authentication path, including invalid framing,
unauthenticated requests and numeric-name identity binding. Live-game compatibility
uses the existing disposable Promod/BTD/allied runners with the host endpoint
absent; this verifies disabled-bridge compatibility, not an enabled production
transition. Complete real-image RCON round trips and external rollback remain
operator qualification gates after reviewed merges.

Rollback: retain the host CLI, remove the bridge socket mount/stop the host bridge
only with operator authorization, and revert the focused feature through review.
Do not undo authentication repairs merely to disable switching. Keep production
on its existing approved image until separate activation approval.

Local review evidence (2026-10-27): engine unit suite 79 tests, one optional
client-checkout skip; map rotation/voting checks passed. Protected baselines:
engine `701a7c5df46c5723705dad0408afa44fb89b0ad9`, workspace `b77684d`,
configuration `9f0fa1a0b0c1483ea20a89fc7beaf26c9b7c2201`.
