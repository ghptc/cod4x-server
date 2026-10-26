# Traditional UDP RCON compatibility investigation

Investigation date: 2026-10-26. Server baseline:
`9e3ce3e17532574bbe25e24cbff0174df94c802d`.
No real credential was read or used. No remote runtime was contacted or changed.

## Findings

A 48-character alphanumeric password works through the traditional server UDP
parser and authentication function. It cannot be installed using `/rcon login`
in either of the two client binaries found in the owner's Steam/Proton installation.

| Implementation | Accepted login length | 16 | 32 | 48 | 64 |
| --- | --- | --- | --- | --- | --- |
| Installed `iw3mp.exe` login routine | 0–23 bytes | accept | reject | reject | reject |
| Installed `cod4x_021.dll` login routine | 0–28 bytes | accept | reject | reject | reject |
| Standalone UDP client against server-function harness | minimum 8 bytes; packet budget below | accept | accept | accept | accept |

The server minimum makes the usable overlap 8–23 bytes for both clients, or
8–28 for this CoD4x client alone. These are ASCII byte limits, not a general
Unicode character claim. Lengths 23/24 and 28/29 were also exercised.

Both clients reject an overlong login without replacing the previous stored
password. The login operation itself sends no authentication packet. A subsequent
`rcon status` can therefore send a stale password and produce `Bad rcon`. With no
previous login, the client instead asks the user to log in. This explains how
correctly copying a 48-character server password can still produce mismatches;
it is not evidence that the server truncates that password.

The installation contains a CoD4x DLL, but that alone does not establish which
implementation was active during the reported attempts. The discovered game
process was a zombie with no memory mappings. The owner was asked for only the
`/version` output to close that attribution gap. Neither the active remote cvar
nor the original failure packet was inspected; the incident's precise active
build and stale credential remain unverified.

## Parsing and serialization

`SV_ConnectionlessPacket` in `src/sv_main.c` skips the four-byte `0xffffffff`
marker, reads a line with `MSG_ReadStringLine`, tokenizes it, then dispatches
`rcon` to `SVC_RemoteCommand`. Authentication uses case-sensitive `strcmp` of
`SV_Cmd_Argv(1)` and `sv_rconPassword->string`, then enforces the eight-byte minimum.
On success it rereads the packet, skips the marker and four bytes `rcon`, skips
the quoted or unquoted password, and executes the remainder.

`MAX_STRING_CHARS` is 1024: the initial line buffer holds **1023 bytes**, excluding
the OOB marker and terminator. With `rcon PASSWORD COMMAND`, keeping the complete
initial line requires `password_bytes + command_bytes <= 1017`; quoting the
password costs two more bytes. The initial token can contain at most 1018
unquoted password bytes after `rcon `. The second read starts four bytes later,
so the harness still executes a one-byte command with 1017/1018-byte passwords;
1019 bytes cannot authenticate. This two-pass behavior is not a recommended
client packet budget. There is no separate 32/48/64-byte server authentication
limit. `%` becomes `.` in `MSG_ReadStringLine`, and newline/NUL terminate it;
the alphanumeric tests avoid those independent protocol restrictions.

The installed stock login machine code at VA `0x471a4b` compares length with
24 and accepts only below 24. The bundled `_cl_main_pc_mp.asm` independently
shows the equivalent maximum 23. The installed CoD4x DLL compares with 28 at
VA `0x6319561c` and rejects above it. The public client source
[CL_Rcon_f at the tested revision](https://github.com/callofduty4x/CoD4x_Client_pub/blob/17182c7bf04b859dea5c0db4acdb0b83c28d6dd2/src/cl_main.c#L4502)
uses `static char rcon_password[32]` and `strlen(...) < sizeof(...) - 3`:
maximum 28, despite the 32-byte storage. It sends four FF bytes, `rcon `,
stored password, a space, command arguments, and a NUL using `NET_SendPacket`.
Its message buffer is 1024 bytes including the OOB marker and terminator.
Setting a client cvar named `rcon_password` does not change this static storage.

## Reproduction and effective CFG values

Run the dependency-free server regression suite with a C compiler and Python:

```sh
python3 -m unittest discover -s tests -p test_rcon.py -v
```

It compiles the actual current `MSG_ReadStringLine`, tokenizer,
`Cvar_Set_f`, `Cvar_SetVariant`, `SVC_RemoteCommand`, and Source RCON auth function.
Synthetic `set rcon_password "..."` CFG files are read from temporary directories.
The real tokenizer/setter path must produce an exact effective string match;
only its length and equality result are printed. The harness supplies the
`Cvar_Set2` lookup boundary for the registered string cvar. It uses real loopback
UDP sockets with standalone packet serialization and tests quoted/unquoted
passwords, minimum length, mismatch, and packet boundaries.

For the actual public client serialization comparison, clone the public client
outside this repository at revision `17182c7bf04b859dea5c0db4acdb0b83c28d6dd2`, then:

```sh
COD4X_CLIENT_SOURCE=/tmp/cod4x-rcon-client-reference \
  python3 -m unittest discover -s tests -p test_rcon.py -v
```

That optional test compiles the actual public `CL_Rcon_f` function with engine
boundaries, first installs a disposable old login, attempts each new length,
and sends the resulting client packet to the same UDP harness. Lengths up to
28 succeed; 32/48/64 retain the old login and receive `Bad rcon`.
All five tests passed with the optional checkout enabled.

`tools/rcon/probe_client_login.py` separately executes the **installed binary
login instructions**, using Unicorn 2.1.4 in a disposable virtual environment.
It maps only the on-disk PE images with synthetic memory and stubs printing and
library boundaries. It never reads live client state, credentials or CFGs, and
never sends a packet. Pass the two installed binary paths to reproduce.
Both boundary tables above passed. Exact binary SHA-256 identities:

- `iw3mp.exe`: `f50f8a520581754e73cb7cae67b02adcbad5f2e71aaa412a013bb3ef57a391a5`
- `cod4x_021.dll`: `bf5965ea484e0b899119ebb99428b8f7aaf175f2052e610c1ce466119e6b0d2b`

These are function-level and emulated binary tests, not a graphical game session
or a full dedicated-server boot. Filesystem search precedence, later CFG
assignments, live homolog cvar state and the active historical DLL were not
verified. `execing server.cfg` proves queuing the file (`Cmd_Exec_f` calls
`Cbuf_InsertText`), not that no later command overrides its values.

## Verified fix and rollback

No traditional UDP authentication change is justified by these results. The
separate confirmed defect is Source RCON's rejection log exposing the entire
submitted login string, including account/password combinations. Remove that
argument while retaining the peer address. Regression tests cover both login
forms and preserve auth rejection ID -1 and the 20-second ban. The regression
fails against the previous plaintext logging statement and passes after the fix.
Production `src/hl2rcon.c` also passed i386 syntax compilation.

Rollback consists of reverting the logging-fix commit; no configuration,
credentials, services or protocol behavior were changed. No binary, third-party
checkout, game assets, dependency package or raw runtime log is included.
