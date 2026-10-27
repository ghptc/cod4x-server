/* Disposable loopback test driver. Never package in a server runtime image.
 * AGPL-3.0-or-later. Only activates clients that completed a real UDP admission.
 */
#include "../src/plugin_handler.h"
#include "../src/g_sv_shared.h"
#include "../src/q_math.h"
#include "../src/cvar.h"

extern void Plugin_AddCommand(const char *, xcommand_t, int);

static int driven[MAX_CLIENTS];
static int firing[MAX_CLIENTS];

static void Fixture(void)
{
    int slot;
    if (Cmd_Argc() != 3) return;
    slot = atoi(Cmd_Argv(2));
    if (slot < 0 || slot >= sv_maxclients->integer) return;
    client_t *cl = &svs.clients[slot];
    if (cl->state < CS_CONNECTED || cl->netchan.remoteAddress.type != NA_IP ||
        cl->netchan.remoteAddress.ip[0] != 127) return;
    if (!strcmp(Cmd_Argv(1), "activate")) {
        usercmd_t cmd = {0};
        cmd.serverTime = svs.time;
        /* Headless fixture has no graphical client's checksum/profile exchange.
         * This bypass is local to the explicitly activated test connection;
         * sv_pure, server checksums and production authentication are unchanged.
         */
        cl->pureAuthentic = 1;
        SV_ClientEnterWorld(cl, &cmd);
        driven[slot] = 1;
        Com_Printf(CON_CHANNEL_SERVER, "BTD_ALLIES_HUMAN_ACTIVE slot=%d\n", slot);
    } else if (!strcmp(Cmd_Argv(1), "fire")) firing[slot] = 1;
    else if (!strcmp(Cmd_Argv(1), "stop")) firing[slot] = 0;
}

void OnFrame(void)
{
    for (int slot = 0; slot < sv_maxclients->integer; ++slot) {
        if (!driven[slot]) continue;
        client_t *cl = &svs.clients[slot];
        if (cl->state != CS_ACTIVE || cl->netchan.remoteAddress.type != NA_IP ||
            cl->netchan.remoteAddress.ip[0] != 127) {
            driven[slot] = firing[slot] = 0;
            continue;
        }
        cl->lastPacketTime = svs.time;
        cl->reliableAcknowledge = cl->reliableSequence;
        if (!cl->gentity || !cl->gentity->client) continue;
        playerState_t *ps = &cl->gentity->client->ps;
        usercmd_t cmd = {0};
        cmd.serverTime = svs.time;
        cmd.weapon = ps->weapon;
        for (int axis = 0; axis < 3; ++axis)
            cmd.angles[axis] = ANGLE2SHORT(ps->viewangles[axis] - ps->delta_angles[axis]);
        if (firing[slot]) {
            char name[64];
            Com_sprintf(name, sizeof(name), "btd_allies_test_reload_%d", slot);
            if (Cvar_GetInt(name)) cmd.buttons = KEY_MASK_RELOAD;
            else {
                Com_sprintf(name, sizeof(name), "btd_allies_test_fire_%d", slot);
                if (Cvar_GetInt(name)) cmd.buttons = KEY_MASK_FIRE;
            }
        }
        SV_ClientThink(cl, &cmd);
    }
}

int OnInit(void)
{
    Plugin_AddCommand("btd_allies_fixture", Fixture, 100);
    return 0;
}

void OnInfoRequest(pluginInfo_t *info)
{
    info->handlerVersion.major = PLUGIN_HANDLER_VERSION_MAJOR;
    info->handlerVersion.minor = PLUGIN_HANDLER_VERSION_MINOR;
    Q_strncpyz(info->fullName, "Disposable allied bot qualification", sizeof(info->fullName));
}
