# HTTP and Web Console security boundaries

Independent review of protected engine master
`6c3f326ca2ebb5f72b7af32976560e9e52a3c516` confirmed three issues using isolated
production-function fixtures, without contacting a running game server:

- A pending HTTP request resized its receive buffer to the declared final length
  and then copied an entire larger TCP chunk. AddressSanitizer confirmed a heap
  overwrite. The same parser lacked a guaranteed form terminator and useful
  header/body limits; an empty session cookie caused an out-of-bounds read.
- Player names passed through the name cleaner and color converter into raw HTML
  in the authenticated Web Console. An isolated rendering fixture preserved
  event-bearing markup. An administrator viewing such a name could execute
  attacker-controlled script with that administrator's browser authority.
- HTTP session cookies and password-changing RCON command arguments entered
  diagnostic logs. Browser sessions also remained valid after password recovery.

Live HTTP/TCP reachability and exploitation were not tested. These are confirmed
code boundaries, not evidence that a production endpoint was compromised.

The HTTP server now accepts at most 16,384 bytes of headers and 65,536 bytes of
body. It sizes memory from checked received-byte counts, reserves a terminator,
requires complete CRLF header framing and exact method separators, and rejects
excess input, overlong lines, duplicate/overflowing lengths and unsupported
Transfer-Encoding. It supports a single request followed by connection closure;
HTTP pipelining and uploads are not supported by this administrative endpoint.
Client-side HTTP download/status parsing is unchanged.

Web text and console output are entity-escaped. Only fixed color spans are emitted
as markup, with space reserved for balanced closing spans. Console line breaks
and tabs remain readable. Cookies require the exact session name and a complete
64-character hexadecimal bearer. Responses add `SameSite=Strict` alongside
`HttpOnly`; this does not provide encryption or replace a CSRF token/Origin check.

HTTP bearer and URL logging is removed. UDP/Source RCON diagnostic logs retain the
request source and an argument-omitted marker, rather than arbitrary command
text. This deliberately reduces log detail because command aliases and cvar
setters can carry passwords. Command execution and authorized responses retain
their existing behavior.

Password and credential-record replacement revoke existing **browser** sessions.
This change does not expire browser sessions or invalidate established Source
RCON TCP connections after password rotation. Account connections continue to
check current permissions; established shared-password console connections retain
their original console identity. Connection revocation/auth generations, browser
expiry, protected administrative transport and CSRF defenses require separate
focused review. Credentials disclosed in historical logs require an operator-led
exposure assessment; no credential rotation is performed by this patch.

Validation: `make -j4` and the 83-test Python suite passed (one optional
client-checkout test skipped). The three new Web security tests execute actual
production functions. HTTP and HTML fixtures run with AddressSanitizer and
UndefinedBehaviorSanitizer; the session fixture verifies recovery invalidation.
They cover fragmented valid requests, excess bytes, length overflow/duplicates,
header/method/cookie boundaries, escaped markup, color truncation and console
formatting. UDP RCON tests use synthetic credential-command canaries and assert
that the canary is absent from captured diagnostic logs.

```sh
python3 -m unittest discover -s tests -p 'test_web_security.py'
python3 -m unittest discover -s tests -p 'test_*.py'
make -j4
```

Independent source review verified this focused change. Tests and review do not
establish whole-engine memory safety or a secure infrastructure baseline. This
patch does not install/enable the mode bridge, change production, deploy images,
rotate credentials or modify infrastructure. Retain the bridge release gates.
Rollback is a reviewed code revert; it reintroduces the documented weaknesses and
must not be used to bypass security qualification.
