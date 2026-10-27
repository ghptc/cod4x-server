/* Native bot population and human admission. See docs/bots.md and
 * docs/zombies-allied-bots.md. AGPL-3.0-or-later. */
#include "server.h"
#include "cmd.h"
#include "cvar.h"
#include "qcommon.h"
#include "qcommon_io.h"
#include "sv_bot_policy.h"
#include "sv_bot_names.h"
#include "g_sv_shared.h"
#include "filesystem.h"

static cvar_t *bot_enable, *bot_ai_ready, *bot_fill_limit, *bot_skill;
static cvar_t *btd_allies_enable, *btd_allies_limit, *bot_use_names;
static bot_fill_state_t fill_state = BOT_FILL_ACTIVE;
static int next_fill;
static unsigned int next_name_index;

static int BotCount(void)
{
    int i, count = 0;
    if (!sv_maxclients || !com_sv_running || !com_sv_running->integer) return 0;
    for (i = 0; i < sv_maxclients->integer; ++i)
        if (svs.clients[i].state >= CS_CONNECTED && svs.clients[i].netchan.remoteAddress.type == NA_BOT) ++count;
    return count;
}

static qboolean BotAlliedMode(void)
{
    return fs_gameDirVar &&
        !strcmp(fs_gameDirVar->string, "mods/btd_alpha_001") &&
        !strcmp(sv_g_gametype->string, "war");
}

static int BotLimitValue(void)
{
    return BotAlliedMode() ? btd_allies_limit->integer : bot_fill_limit->integer;
}

static qboolean BotCanAdd(void)
{
    return com_sv_running && com_sv_running->integer &&
        bot_ai_ready->boolean && sv.state == SS_GAME && !sv.restarting &&
        sv_pure->boolean && ((BotAlliedMode() && btd_allies_enable->boolean) ||
        (bot_enable->boolean && !strcmp(sv_g_gametype->string, "sd")));
}

static qboolean BotQueueWaiting(void)
{
    int i;
    for (i = 0; i < 10; ++i)
        if (svs.connectqueue[i].lasttime && svs.connectqueue[i].lasttime + 21 >= Com_GetRealtime()) return qtrue;
    return qfalse;
}

/* Names are assigned once, never by renaming an existing player. Include humans
 * in collision checks without modifying their names. Re-read the small local
 * pool on admission so editing it affects only newly created Promod bots. */
static qboolean BotNameUsed(const char *name)
{
    int i;
    for (i = 0; i < sv_maxclients->integer; ++i) {
        char clean[BOT_NAME_BYTES];
        client_t *cl = &svs.clients[i];
        if (cl->state < CS_CONNECTED) continue;
        ClientCleanName(Info_ValueForKey(cl->userinfo, "name"), clean, sizeof(clean), qfalse);
        if (!Q_stricmp(clean, name)) return qtrue;
    }
    return qfalse;
}

static qboolean BotPoolName(char name[BOT_NAME_BYTES])
{
    fileHandle_t file;
    char data[BOT_NAMES_BYTES], candidate[BOT_NAME_BYTES], fallback[BOT_NAME_BYTES];
    unsigned int count = 0, index = 0, start, fallback_index = 0;
    qboolean have_fallback = qfalse;
    const char *cursor = data;
    int length = FS_SV_FOpenFileRead("scriptdata/botnames.txt", &file);
    if (!file) return qfalse;
    if (length <= 0 || length > sizeof(data)) {
        FS_FCloseFile(file);
        return qfalse;
    }
    if (FS_Read(data, length, file) != length) {
        FS_FCloseFile(file);
        return qfalse;
    }
    FS_FCloseFile(file);
    while (BotName_Next(&cursor, data + length, candidate)) ++count;
    if (!count) return qfalse;
    start = next_name_index % count;
    cursor = data;
    while (BotName_Next(&cursor, data + length, candidate)) {
        ClientCleanName(candidate, name, BOT_NAME_BYTES, qfalse);
        if (!BotNameUsed(name)) {
            if (index >= start) {
                next_name_index = index + 1;
                return qtrue;
            }
            if (!have_fallback) {
                Q_strncpyz(fallback, name, sizeof(fallback));
                fallback_index = index;
                have_fallback = qtrue;
            }
        }
        ++index;
    }
    if (have_fallback) {
        Q_strncpyz(name, fallback, BOT_NAME_BYTES);
        next_name_index = fallback_index + 1;
    }
    return have_fallback;
}

static qboolean BotAddOne(void)
{
    char name[BOT_NAME_BYTES];
    int number;
    if (BotAlliedMode()) {
        Com_sprintf(name, sizeof(name), "[BOT] Ally %02d", BotCount() + 1);
    } else if (!bot_use_names->boolean || !BotPoolName(name)) {
        /* Pigeonhole bound: with N slots at most N names can be occupied. */
        for (number = 1; number <= sv_maxclients->integer + 1; ++number) {
            Com_sprintf(name, sizeof(name), "[BOT] Promod %02d", number);
            if (!BotNameUsed(name)) break;
        }
    }
    return SV_AddBotClient(name) != NULL;
}

static int BotHumanCount(client_t *exclude)
{
    int i, humans = 0;
    if (!sv_maxclients) return 0;
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
    if (Cmd_Argc() != 1) { Com_Printf(CON_CHANNEL_SERVER, "Usage: bot_kickall\n"); return; }
    /* Set pause before disconnect callbacks can run. */
    fill_state = BotFill_Pause(BotHumanCount(NULL));
    if (BotCount()) SV_RemoveAllBots();
    Com_Printf(CON_CHANNEL_SERVER, "Bots removed; Auto-Fill paused.\n");
}

static void BotKillAll(void)
{
    int i, killed = 0;
    if (Cmd_Argc() != 1) { Com_Printf(CON_CHANNEL_SERVER, "Usage: bot_killall\n"); return; }
    if (com_sv_running && com_sv_running->integer && sv_maxclients &&
        sv.state == SS_GAME && !sv.restarting) {
        for (i = 0; i < sv_maxclients->integer; ++i) {
            client_t *cl = &svs.clients[i];
            if (cl->state == CS_ACTIVE && cl->netchan.remoteAddress.type == NA_BOT)
                killed += G_AdminSuicide(cl->gentity);
        }
    }
    Com_Printf(CON_CHANNEL_SERVER, "Killed %d bots\n", killed);
}

static qboolean BotCountArgument(int *count)
{
    if (Cmd_Argc() == 2 && BotControl_Count(Cmd_Argv(1), count)) return qtrue;
    Com_Printf(CON_CHANNEL_SERVER, "Usage: %s <count 0..12>\n", Cmd_Argv(0));
    return qfalse;
}

static void BotAdd(void)
{
    int count, added = 0, allowed;
    if (!BotCountArgument(&count) || !count) return;
    if (!BotCanAdd() || BotQueueWaiting()) {
        Com_Printf(CON_CHANNEL_SERVER, "Bots not ready, or a human connection is queued. No bots added.\n");
        return;
    }
    allowed = BotFill_Target(BotHumanCount(NULL), sv_maxclients->integer, BotLimitValue()) - BotCount();
    while (added < count && added < allowed && BotAddOne()) ++added;
    Com_Printf(CON_CHANNEL_SERVER, "Added %d bots.\n", added);
}

static void BotKick(void)
{
    int count, removed = 0;
    if (!BotCountArgument(&count) || !count) return;
    fill_state = BotFill_Pause(BotHumanCount(NULL));
    while (removed < count && BotCount() && SV_RemoveBot()) ++removed;
    Com_Printf(CON_CHANNEL_SERVER, "Removed %d bots; Auto-Fill paused.\n", removed);
}

static void BotLimit(void)
{
    int count;
    if (!BotCountArgument(&count)) return;
    Cvar_SetInt(BotAlliedMode() ? btd_allies_limit : bot_fill_limit, count);
    /* Enforce zero/reductions even while Auto-Fill is paused. */
    while (BotCount() > count && SV_RemoveBot()) {}
}

static void BotDifficulty(void)
{
    int skill;
    if (Cmd_Argc() == 2) {
        if (!strcmp(Cmd_Argv(1), "fixed")) skill = -1;
        else if (!strcmp(Cmd_Argv(1), "mixed")) skill = 0;
        else if (!BotControl_Count(Cmd_Argv(1), &skill) || skill < 1 || skill > 7) skill = -2;
        if (skill >= -1) { Cvar_SetInt(bot_skill, skill); return; }
    }
    Com_Printf(CON_CHANNEL_SERVER, "Usage: bot_difficulty <fixed|mixed|1..7>\n");
}

static void BotAutoFill(void)
{
    if (Cmd_Argc() != 2 || (strcmp(Cmd_Argv(1), "0") && strcmp(Cmd_Argv(1), "1"))) {
        Com_Printf(CON_CHANNEL_SERVER, "Usage: bot_autofill <0|1>\n");
        return;
    }
    if (!strcmp(Cmd_Argv(1), "1")) {
        Cvar_SetBool(BotAlliedMode() ? btd_allies_enable : bot_enable, qtrue);
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
    if (!com_sv_running || !com_sv_running->integer) {
        Com_Printf(CON_CHANNEL_SERVER, "BOT_STATUS server-not-running\n");
        return;
    }
    for (i = 0; i < sv_maxclients->integer; ++i) {
        client_t *cl = &svs.clients[i];
        if (cl->state < CS_CONNECTED) continue;
        if (cl->netchan.remoteAddress.type == NA_BOT) ++bots;
        else if (cl->state != CS_ACTIVE) ++pending;
    }
    Com_Printf(CON_CHANNEL_SERVER, "BOT_STATUS enabled=%d state=%s humans=%d connecting=%d bots=%d ready=%d pure=%d limit=%d difficulty=%s\n",
        BotAlliedMode() ? btd_allies_enable->boolean : bot_enable->boolean, state, BotHumanCount(NULL), pending, bots, bot_ai_ready->boolean, sv_pure->integer,
        BotLimitValue(), BotAlliedMode() ? "allied-mixed" : bot_skill->integer == -1 ? "fixed" : bot_skill->integer == 0 ? "mixed" : va("%d", bot_skill->integer));
}

void SV_BotManagerInit(void)
{
    bot_enable = Cvar_RegisterBool("bot_enable", qfalse, 0, "Enable the experimental Promod bot integration");
    bot_ai_ready = Cvar_RegisterBool("bot_ai_ready", qfalse, 0, "Set by the server AI script after loading map navigation");
    bot_fill_limit = Cvar_RegisterInt("bot_fill_limit", 12, 0, 12, 0, "Maximum AI bots; humans also consume the 12-slot population");
    bot_skill = Cvar_RegisterInt("bot_skill", -1, -1, 7, 0, "Bot skill: -1 original fixed profile, 0 mixed, 1..7 Bot Warfare tiers");
    btd_allies_enable = Cvar_RegisterBool("btd_allies_enable", qtrue, 0, "Enable the isolated BTD allied controller");
    btd_allies_limit = Cvar_RegisterInt("btd_allies_limit", 5, 0, 12, 0, "Maximum allied BTD bots");
    bot_use_names = Cvar_RegisterBool("bot_use_names", qfalse, 0, "Use Bot Warfare scriptdata/botnames.txt for new Promod bots");
    Cvar_RegisterBool("bot_sd_objectives", qfalse, 0, "Enable native Promod S&D objective navigation and use input");
    Cvar_RegisterBool("bot_debug", qfalse, 0, "Write bot gameplay evidence to the game log");
    Cmd_AddPCommand("bot_kickall", BotKickAll, 80);
    Cmd_AddPCommand("bot_killall", BotKillAll, 80);
    Cmd_AddPCommand("bot_autofill", BotAutoFill, 80);
    Cmd_AddPCommand("bot_status", BotStatus, 20);
    Cmd_AddPCommand("bot_add", BotAdd, 80);
    Cmd_AddPCommand("bot_kick", BotKick, 80);
    Cmd_AddPCommand("bot_limit", BotLimit, 80);
    Cmd_AddPCommand("bot_difficulty", BotDifficulty, 80);
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
    /* Existing bot slots yield even when AI/filling was subsequently disabled. */
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
    int bots, target;
    if (!com_sv_running || !com_sv_running->integer || sv.state != SS_GAME || sv.restarting) return;
    bots = BotCount();
    target = BotFill_Target(BotHumanCount(NULL), sv_maxclients->integer, BotLimitValue());
    if (bots > target) { SV_RemoveBot(); return; }
    if (!BotCanAdd() || fill_state != BOT_FILL_ACTIVE) return;
    if (next_fill > svs.time && next_fill - svs.time < 3000) return;
    next_fill = svs.time + 250;
    /* Do not consume slots while humans wait in the existing connection queue. */
    if (BotQueueWaiting()) return;
    if (bots >= target) return;
    BotAddOne();
}
