# Administration and runtime-only deployment

Use the server console or existing authenticated RCON. In-game administration
continues through the engine's existing authentication/command-power checks.
RCON is privileged; never put its secret in Git or verbose packet logs. All
commands below are server commands; prefix with the client's normal RCON command
when appropriate. No new network protocol or public port is introduced.

| Capability | Command | Default power / boundary |
|---|---|---|
| Identify slot/ID | `status`, `ministatus` | Console/RCON; ministatus 1 |
| Kick | `kick <slot> <reason>` | Existing 35; immediate |
| Permanent ban | `permban <user> <reason>` | Existing 80; stable player ID preferred |
| Temporary ban | `tempban <user> <30m|2h|1d> <reason>` | Existing 50; existing 30-day maximum |
| Unban | `unban <id>` | Existing 80; use the recorded ban identity |
| Server mute | `mute <slot> [voice|all]` | New 35; default all, current connection only |
| Unmute | `unmute <slot>` | New 35; current connection only |
| Team request | `setteam <slot> <allies|axis|spectator>` | New 80; deferred to game frame |
| Restart map/match | `map_restart` | Existing 50; ordinary restart, not fast_restart |
| Change/reload map | `map mp_crash` | Existing 60; full map load |
| Advance rotation | `map_rotate` | Existing console/RCON power 100 |
| Gameplay rules | `promod_rule <name> <value|default>` | New 80; full map reload required |

Do not duplicate kick/ban/map commands. Names and IDs for upstream ban commands
retain their existing parsing conventions; inspect their usage before acting.
The new player commands accept strict numeric connected slots only, reject
missing/invalid arguments, and cannot target an administrator of higher power.
Server mute uses the existing mutelevel field: 1 blocks voice, 2 blocks voice
and chat. Existing voice/chat gates enforce it; a reconnect/new occupant resets
this session state. Listener-side `muteplayer` is a separate existing feature.

Team/rule commands require `+set sv_promod_admin 1` before loading Promod S&D
and a private runtime prepared with `tools/bots/prepare.py --admin-rules` plus
the existing required arguments. Defaults stay unchanged when disabled.
Team changes use a small server-only helper that yields before calling the
installed Promod menu methods. Calling suicide/team methods directly from
Cbuf_Execute lacks G_RunFrame's animation context and crashed an early local
test; that direct path is removed. Handles refresh during each script load.
Pending helper threads cancel on disconnect/game end. No callbacksetup, ready-up,
damage or bomb callback is replaced, and no command text is constructed from
player input. Normal team-balance permissions may refuse a request. Humans keep
Promod's class menu; moved bots use its validated assault-selection methods.

## Rules

The existing custom_public ruleset assigns defaults before caching level.*
values. Merely setting scr_* at the console may be overwritten or leave cached
values unchanged. The optional private .gsx overlay retains every original
assignment and then applies only explicitly configured native overrides before
the cache is initialized. The IWD and compiled assets are not modified.

| Supported name | Meaning / accepted range |
|---|---|
| scr_sd_timelimit | Round minutes, finite 0..60; zero is unlimited |
| scr_sd_roundlimit | Integer 0..1000; zero follows Promod's unlimited behavior |
| scr_sd_scorelimit | Integer 0..1000 |
| scr_sd_roundswitch | Integer 0..1000 |
| scr_team_fftype | Integer 0..3, original disabled/enabled/reflect/shared modes |
| sv_voice | Integer 0..1; default remains Promod's disabled voice |

Only custom_public accepts these overrides; competition/match rules are not
silently changed. Examples: `promod_rule scr_sd_timelimit 2.25` and
`promod_rule scr_sd_roundlimit 12`, then explicitly `map mp_crash`. `default`
clears that override. A full map reload is the tested application boundary;
do not assume a fast round restart applies pending values. Changes do not
immediately alter a running round. For persistence, put valid values in private
server.cfg as `cod4x_rule_scr_sd_timelimit "2.25"`, etc. Other rules still belong
in the authorized private Promod ruleset, not a generic administration framework.

## Local validation and packaging

```sh
python3 -m unittest discover -s tests -p test_admin_rules.py
# After preparing a private runtime with --admin-rules and building the fixture:
gcc -std=c11 -Wall -Wextra -Werror tests/rcon_reject.c -o /private/runtime/rcon_reject
python3 tools/bots/run_local.py --runtime /private/runtime --game /private/game --scenario admin --seconds 65
```

Build the Linux i386 executable locally with the existing verified toolchain.
Before making an image, verify its ELF32/i386 format, revision and SHA-256.
`docker/Dockerfile.runtime` uses the pinned existing runtime image, copies only
that executable and required notices, and contains no development toolchain or
new dependency. Proprietary game/Promod assets and generated private overlays
are separate read-only mounts. The Compose file publishes only UDP 28962 to
container UDP 28960, with separate homologation configuration/home and bounded
Docker logs. Its required environment variables intentionally have no guesses.

After owner review/merge, on the **development machine**:

```sh
revision=$(git rev-parse HEAD)
context=$(mktemp -d)
cp bin/cod4x18_dedrun Copyright.md License.md copying.md "$context/"
docker build --pull=false -f docker/Dockerfile.runtime --build-arg COD4X_REVISION="$revision" -t "cod4x-server:homolog-$revision" "$context"
docker image inspect "cod4x-server:homolog-$revision"
docker save "cod4x-server:homolog-$revision" | gzip > "cod4x-runtime-$revision.tar.gz"
```

Prepare/review the private runtime/configuration and Compose environment locally
too. Keep previous images/configs/data for rollback. No floating latest tag,
registry publication, CI/CD, release or deployment is performed by these files.

## Future deployment — explicit approval required

Before using historical paths, inspect current containers/mounts/ports, free
memory/disk and backups. Preserve production UDP 28960 and Bard. Stop if 28962
belongs to another service or the proposed configuration touches shared writable
data. Review the exact image ID, private assets, credentials and Compose diff.

Transfer only the prebuilt image archive, required private runtime assets and
reviewed runtime configuration. EC2 must not receive source worktrees, compilers,
test suites, asset generators or Python deployment scripts. With a reviewed
`runtime.env` on the host, the manually approved runtime operations are:

```sh
gzip -dc /path/to/cod4x-runtime-REVISION.tar.gz | docker load
docker compose --env-file /opt/services/cod4/homolog/runtime.env -p cod4-homolog -f /opt/services/cod4/homolog/compose.runtime.yaml config --quiet
docker compose --env-file /opt/services/cod4/homolog/runtime.env -p cod4-homolog -f /opt/services/cod4/homolog/compose.runtime.yaml up -d --no-deps --pull never homolog
docker logs --tail 80 cod4-homolog
docker stats --no-stream cod4-homolog
```

These are future instructions, not authorization to execute them. Do not run
compose down, remove persistent data, modify production/Bard, open TCP ports,
change SG/IAM/firewall rules or create speculative host directories. Rollback
selects the previous reviewed image/config and recreates only homolog, retaining
its data. The upstream updater may wait about four minutes for its lock under a
read-only root; the image executable remains pinned. Missing steam_api.so is an
existing image warning, not silently repaired here. Graphical FPS/PB, human
team/class, voice/chat and authenticated low-power in-game checks remain pending.
