/* Promod bot population and human admission. See docs/bots.md. AGPL-3.0-or-later. */
#include "server.h"
#include "cmd.h"
#include "cvar.h"
#include "qcommon.h"
#include "qcommon_io.h"
#include "sv_bot_policy.h"

static cvar_t *bot_enable, *bot_ai_ready;
static bot_fill_state_t fill_state = BOT_FILL_ACTIVE;
static int next_fill;

static int BotHumanCount(client_t *exclude)
{
    int i, humans = 0;
    for (i = 0; i < sv_maxclients->integer; ++i) {
        client_t *cl = &svs.clients[i];
        if (cl != exclude && cl->state >= CS_CONNECTED && cl->netchan.remoteAddress.type != NA_BOT)
            ++humans;
    }
    return humans;
}

void SV_BotManagerHumanJoined(void)
{
    fill_state = BotFill_Join(fill_state);
}

void SV_BotManagerHumanLeaving(client_t *cl)
{
    if (cl->state >= CS_CONNECTED && cl->netchan.remoteAddress.type != NA_BOT)
        fill_state = BotFill_Leave(fill_state, BotHumanCount(cl));
}

static void BotKickAll(void)
{
    /* Set pause before disconnect callbacks can run. */
    fill_state = BotFill_Pause(BotHumanCount(NULL));
    SV_RemoveAllBots();
    Com_Printf(CON_CHANNEL_SERVER, "Bots removed; Auto-Fill paused.\n");
}

static void BotAutoFill(void)
{
    if (Cmd_Argc() != 2 || (strcmp(Cmd_Argv(1), "0") && strcmp(Cmd_Argv(1), "1"))) {
        Com_Printf(CON_CHANNEL_SERVER, "Usage: bot_autofill <0|1>\n");
        return;
    }
    if (!strcmp(Cmd_Argv(1), "1")) {
        Cvar_SetBool(bot_enable, qtrue);
        fill_state = BOT_FILL_ACTIVE;
    } else {
        fill_state = BotFill_Pause(BotHumanCount(NULL));
    }
}

static void BotStatus(void)
{
    int i, bots = 0, pending = 0;
    const char *state = fill_state == BOT_FILL_ACTIVE ? "active" :
        fill_state == BOT_FILL_PAUSED_EMPTY ? "paused-awaiting-human" : "paused-with-humans";
    for (i = 0; i < sv_maxclients->integer; ++i) {
        client_t *cl = &svs.clients[i];
        if (cl->state < CS_CONNECTED) continue;
        if (cl->netchan.remoteAddress.type == NA_BOT) ++bots;
        else if (cl->state != CS_ACTIVE) ++pending;
    }
    Com_Printf(CON_CHANNEL_SERVER, "BOT_STATUS enabled=%d state=%s humans=%d connecting=%d bots=%d ready=%d pure=%d\n",
        bot_enable->boolean, state, BotHumanCount(NULL), pending, bots, bot_ai_ready->boolean, sv_pure->integer);
}

void SV_BotManagerInit(void)
{
    bot_enable = Cvar_RegisterBool("bot_enable", qfalse, 0, "Enable the experimental Promod bot integration");
    bot_ai_ready = Cvar_RegisterBool("bot_ai_ready", qfalse, 0, "Set by the server AI script after loading map navigation");
    Cmd_AddPCommand("bot_kickall", BotKickAll, 80);
    Cmd_AddPCommand("bot_autofill", BotAutoFill, 80);
    Cmd_AddPCommand("bot_status", BotStatus, 20);
}

void SV_BotManagerMapStart(void)
{
    /* The policy survives maps/rounds. Readiness and game objects do not. */
    if (bot_ai_ready) Cvar_SetBool(bot_ai_ready, qfalse);
    next_fill = 0;
}

client_t *SV_BotManagerFreeHumanSlot(void)
{
    int i;
    if (!bot_enable || !bot_enable->boolean) return NULL;
    for (i = sv_privateClients->integer; i < sv_maxclients->integer; ++i) {
        client_t *cl = &svs.clients[i];
        if (cl->state >= CS_CONNECTED && cl->netchan.remoteAddress.type == NA_BOT) {
            SV_DropClient(cl, "A human player is connecting");
            if (cl->state == CS_FREE) {
                next_fill = svs.time + 2000;
                return cl;
            }
        }
    }
    return NULL;
}

void SV_BotManagerFrame(void)
{
    int i, bots = 0, humans, target;
    char name[32];
    if (!bot_enable || !bot_enable->boolean || !bot_ai_ready->boolean ||
        fill_state != BOT_FILL_ACTIVE || sv.state != SS_GAME || sv.restarting ||
        !sv_pure->boolean || strcmp(sv_g_gametype->string, "sd")) return;
    if (next_fill > svs.time && next_fill - svs.time < 3000) return;
    next_fill = svs.time + 250;
    /* Do not consume slots while humans wait in the existing connection queue. */
    for (i = 0; i < 10; ++i)
        if (svs.connectqueue[i].lasttime && svs.connectqueue[i].lasttime + 21 >= Com_GetRealtime()) return;
    humans = BotHumanCount(NULL);
    target = BotFill_Target(humans, sv_maxclients->integer);
    for (i = 0; i < sv_maxclients->integer; ++i)
        if (svs.clients[i].state >= CS_CONNECTED && svs.clients[i].netchan.remoteAddress.type == NA_BOT) ++bots;
    if (bots > target) { SV_RemoveBot(); return; }
    if (bots >= target) return;
    Com_sprintf(name, sizeof(name), "[BOT] Promod %02d", bots + 1);
    SV_AddBotClient(name);
}
