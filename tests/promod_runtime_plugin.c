/* Disposable test plugin ONLY: never package or load on a real server.
 * Synthetic active humans exercise actual game commands, not authentication or
 * graphical clients. The existing UDP handshake fixture covers admission. */
#include "../src/plugin_handler.h"
#include "../src/bg_public.h"
#include "../src/g_sv_shared.h"
extern void Plugin_AddCommand(const char *, xcommand_t, int);
static qboolean fixture_humans[MAX_CLIENTS];

static void RuntimeFixture(void)
{
    int slot = atoi(Cmd_Argv(1));
    char action[32], value[128];
    Q_strncpyz(action, Cmd_Argv(2), sizeof(action));
    Q_strncpyz(value, Cmd_Argv(3), sizeof(value));
    if (slot < 0 || slot >= level.maxclients || svs.clients[slot].state != CS_ACTIVE) return;
    if (!strcmp(action, "human")) {
        fixture_humans[slot] = qtrue;
        svs.clients[slot].netchan.remoteAddress.type = NA_IP;
        svs.clients[slot].lastUsercmd.buttons = 0;
        g_entities[slot].client->sess.cmd.buttons = 0;
        g_entities[slot].client->sess.oldcmd.buttons = 0;
        g_entities[slot].client->buttons = 0;
        g_entities[slot].client->buttonsSinceLastFrame = 0;
    } else if (!strcmp(action, "bot")) {
        fixture_humans[slot] = qfalse;
        svs.clients[slot].netchan.remoteAddress.type = NA_BOT;
    } else if (!strcmp(action, "use")) {
        int buttons = atoi(value) ? KEY_MASK_USE : 0;
        svs.clients[slot].lastUsercmd.buttons = buttons;
        g_entities[slot].client->sess.cmd.buttons = buttons;
        g_entities[slot].client->sess.oldcmd.buttons = buttons;
        g_entities[slot].client->buttons = buttons;
        g_entities[slot].client->buttonsSinceLastFrame = buttons;
    } else if (!strcmp(action, "callvote") || !strcmp(action, "vote")) {
        struct bgs_s *previous = bgs;
        char command[256];
        Com_sprintf(command, sizeof(command), !strcmp(action,"callvote") ? "callvote map %s" : "vote %s", value);
        bgs = &level_bgs;
        SV_ExecuteClientCommand(&svs.clients[slot], command, qtrue, qfalse);
        bgs = previous;
    } else if (!strcmp(action, "eliminate")) {
        int team = !strcmp(value,"axis") ? TEAM_RED : TEAM_BLUE;
        for (int i=0; i<level.maxclients; ++i)
            if (g_entities[i].client && g_entities[i].client->sess.cs.team == team)
                G_AdminSuicide(&g_entities[i]);
    }
    Com_Printf(CON_CHANNEL_SERVER, "RUNTIME_FIXTURE slot=%d human=%d voteTime=%d yes=%d no=%d\n",
        slot, fixture_humans[slot], level.voteTime, level.voteYes, level.voteNo);
}
void OnFrame(void)
{
    /* Synthetic humans have no network peer. Keep the fixture alive locally. */
    for(int i=0; i<level.maxclients; ++i)
        if(fixture_humans[i] && svs.clients[i].netchan.remoteAddress.type != NA_BOT)
            svs.clients[i].lastPacketTime = svs.time;
}
int OnInit(void)
{
    Plugin_AddCommand("runtime_fixture", RuntimeFixture, 100);
    return 0;
}
void OnInfoRequest(pluginInfo_t *info)
{
    info->handlerVersion.major=PLUGIN_HANDLER_VERSION_MAJOR;
    info->handlerVersion.minor=PLUGIN_HANDLER_VERSION_MINOR;
    Q_strncpyz(info->fullName,"Disposable Promod qualification fixture",sizeof(info->fullName));
}
