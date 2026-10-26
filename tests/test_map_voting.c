/* Exercise the production native handlers with mocked game/network I/O. */
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <strings.h>
#include "../src/g_sv_cmds.c"
#undef assert
#include <assert.h>

level_locals_t level;
serverStatic_t svs;
gentity_t g_entities[MAX_GENTITIES];
static gclient_t clients[MAX_CLIENTS];
cvar_t *g_allowVote, *g_oldVoting, *sv_serverid, *g_voteAbstainWeight;
scr_const_t scr_const;
static cvar_t enabled, disabled, rotationOnly, maxVotes, duration, cooldown, abstain;
static int argc, executed;
static const char *argv[6];
static char command[1024];
static const char *rotation = "gametype sd map mp_crash gametype sd map mp_strike";
extern void Cmd_Vote_f(gentity_t *ent);
extern void CheckVote(void);

int SV_Cmd_Argc(void) { return argc; }
char *SV_Cmd_Argv(int n) { return (char *)(n < argc ? argv[n] : ""); }
void SV_Cmd_ArgvBuffer(int n, char *out, int size) { snprintf(out, size, "%s", SV_Cmd_Argv(n)); }
const char *SV_GetMapRotation(void) { return rotation; }
void SV_SetConfigstring(int n, const char *s) { (void)n; (void)s; }
void SV_GameSendServerCommand(int n, int type, const char *s) { (void)n; (void)type; (void)s; }
void Cbuf_AddText(const char *s) { ++executed; snprintf(command, sizeof(command), "%s", s); }
char *va(const char *fmt, ...) { static char s[4096]; va_list ap; va_start(ap, fmt); vsnprintf(s, sizeof(s), fmt, ap); va_end(ap); return s; }
int Com_sprintf(char *s, int size, const char *fmt, ...) { va_list ap; va_start(ap, fmt); int n=vsnprintf(s,size,fmt,ap); va_end(ap); return n; }
int Q_stricmp(const char *a, const char *b) { return strcasecmp(a,b); }
void Q_strncpyz(char *d, const char *s, int n) { snprintf(d,n,"%s",s); }
char *Q_CleanStr(char *s) { return s; }
void Scr_AddString(const char *s) { (void)s; assert(0); }
void Scr_Notify(gentity_t *ent, unsigned short e, unsigned int n) { (void)ent; (void)e; (void)n; assert(0); }

static void setup(int humans, int bots)
{
    memset(&level,0,sizeof(level));
    memset(clients,0,sizeof(clients));
    level.clients=clients;
    level.maxclients=humans+bots;
    level.time=svs.time=1000;
    nextVoteTime=0;
    enabled.integer=1; disabled.integer=0; rotationOnly.integer=1;
    maxVotes.integer=10; duration.integer=30; cooldown.integer=120;
    abstain.value=1.0f;
    g_allowVote=g_oldVoting=sv_serverid=&enabled;
    g_voteAllowMap=&rotationOnly;
    g_voteAllowMaprotate=g_voteAllowKick=g_voteAllowRestart=g_voteAllowGametype=&disabled;
    g_voteTime=&duration; g_voteCooldown=&cooldown; g_voteMaxVotes=&maxVotes;
    g_voteAbstainWeight=&abstain;
    for(int i=0;i<level.maxclients;++i) {
        g_entities[i].client=&clients[i];
        clients[i].sess.connected=CON_CONNECTED;
        clients[i].sess.cs.team=TEAM_RED;
        svs.clients[i].state=CS_ACTIVE;
        svs.clients[i].netchan.remoteAddress.type=i<humans ? NA_IP : NA_BOT;
    }
    executed=0;
}
static void call(int slot, const char *map)
{
    argc=3; argv[0]="callvote"; argv[1]="map"; argv[2]=map;
    Cmd_CallVote_f(&g_entities[slot]);
}
static void cast(int slot, const char *choice)
{
    argc=2; argv[0]="vote"; argv[1]=choice;
    Cmd_Vote_f(&g_entities[slot]);
}
int main(void)
{
    const int seconds[] = {5, 30, 120};
    for (unsigned i=0; i<sizeof(seconds)/sizeof(*seconds); ++i) {
        setup(2,10); cooldown.integer=seconds[i]; call(0,"mp_crash");
        assert(nextVoteTime == 1000u + 1000u * seconds[i]);
        /* Finish the ballot; cooldown is measured from acceptance, not result. */
        level.voteTime=0; level.voteExecuteTime=0;
        svs.time=nextVoteTime-1; call(1,"mp_strike"); assert(!level.voteTime);
        svs.time=nextVoteTime; call(1,"mp_strike"); assert(level.voteTime);
    }
    setup(2,10); call(0,"mp_crash");
    assert(level.voteTime && level.voteYes==1 && level.numVotingClients==2);
    assert(!strcmp(level.voteString,"set g_votedMapName mp_crash\n"));
    cast(2,"yes"); assert(level.voteYes==1); /* bot cannot cast */
    cast(1,"invalid"); assert(!(clients[1].ps.eFlags & EF_VOTED));
    cast(1,"yes"); cast(1,"yes"); assert(level.voteYes==2);
    CheckVote(); assert(!level.voteTime && level.voteExecuteTime); /* humans win with ten bots */
    unsigned pending=level.voteExecuteTime;
    call(1,"mp_strike"); assert(level.voteExecuteTime==pending && !executed);
    level.time=pending+1; CheckVote(); assert(executed==1);
    assert(!strcmp(command,"set g_votedMapName mp_crash\n"));
    call(1,"mp_strike"); assert(!level.voteTime); /* global cooldown */
    svs.time=121000; call(1,"mp_strike"); assert(level.voteTime);

    setup(2,10); call(0,"mp_crash"); cast(1,"no");
    level.time=level.voteTime; CheckVote(); assert(!level.voteExecuteTime); /* tie fails */
    setup(3,10); call(0,"mp_crash");
    level.time=level.voteTime; CheckVote(); assert(!level.voteExecuteTime); /* abstentions count */
    setup(0,10); call(0,"mp_crash"); assert(!level.voteTime);
    G_UpdateVotingClients(); assert(level.numVotingClients==0);
    setup(1,10); call(0,"mp_crash"); CheckVote(); assert(level.voteExecuteTime); /* bots never inflate majority */

    const char *yes[]={"yes", "YES", "y", "Y", "1"};
    const char *no[]={"no", "NO", "n", "N", "0"};
    for (unsigned i=0;i<5;++i) {
        setup(2,10); call(0,"mp_crash"); cast(1,yes[i]); assert(level.voteYes==2);
        setup(2,10); call(0,"mp_crash"); cast(1,no[i]); assert(level.voteNo==1);
    }
    setup(2,1); call(0,"mp_crash"); clients[1].sess.cs.team=TEAM_SPECTATOR;
    cast(1,"yes"); assert(level.voteYes==1);
    setup(2,0); cast(1,"yes"); assert(!level.voteYes);
    setup(2,0); clients[0].sess.voteCount=10; call(0,"mp_crash"); assert(!level.voteTime);
    const char *invalid[]={"", "mp_cra", "mp_crash_extra", "mp_backlot", "mp_crash;quit", "mp_crash\nquit", "mp_crash\rquit", "mp_crash\"", "../mp_crash", "mp_crash //", "mp_crash\\quit"};
    for(unsigned i=0;i<sizeof(invalid)/sizeof(*invalid);++i) {
        setup(2,1); call(0,invalid[i]);
        assert(!level.voteTime && !nextVoteTime && !executed);
    }
    setup(2,1); argc=4; argv[0]="callvote"; argv[1]="map"; argv[2]="mp_crash"; argv[3]="quit";
    Cmd_CallVote_f(&g_entities[0]); assert(!level.voteTime);
    setup(2,1); g_allowVote=&disabled; call(0,"mp_crash"); assert(!level.voteTime);
    setup(2,1); g_voteAllowMap=&disabled; call(0,"mp_crash"); assert(!level.voteTime);
    setup(2,1); clients[0].sess.cs.team=TEAM_SPECTATOR; call(0,"mp_crash"); assert(!level.voteTime);
    setup(2,1); svs.clients[0].state=CS_CONNECTED; call(0,"mp_crash"); assert(!level.voteTime);
    setup(2,1); call(0,"mp_crash"); int end=level.voteTime;
    call(1,"mp_strike"); assert(level.voteTime==end && level.voteYes==1);
    setup(2,0); argc=2; argv[0]="callvote"; argv[1]="quit";
    Cmd_CallVote_f(&g_entities[0]); assert(!level.voteTime && !executed);
    assert(!Vote_MapInRotation("gametype map mp_crash x", "mp_crash"));
    puts("native map voting: accepted, rejected, invalid, cooldown, pending and bot majority passed");
}
