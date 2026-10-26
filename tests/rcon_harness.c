/* Isolated boundaries for test_rcon.py. Real functions are appended at build time. */
#include "cvar.h"
#include <assert.h>
#include <strings.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <unistd.h>
#define CON_CHANNEL_SERVER 0
#define CON_CHANNEL_SYSTEM 0
#define CON_CHANNEL_CVAR 0
#define CON_CHANNEL_DONT_FILTER 0
#define CRITSECT_CVAR 0
#define SV_OUTPUTBUF_LENGTH 4096
#define SERVERDATA_RESPONSE_VALUE 0
#define SERVERDATA_AUTH_RESPONSE 2

typedef struct { int sock; } netadr_t;
typedef struct { byte *data; int cursize, readcount; } msg_t;
typedef struct { uint64_t steamid; char rconUsername[64]; int lastpacketid; } rconUser_t;
typedef struct { int cmd_argc, availableBuf; char *cmd_tokenized; char **cmd_argv; } cmdTokenizeParams_t;
static cmdTokenizeParams_t tokens;
static char tokenbuf[16384], *args[1024], logs[16384], response[4096];
static char nullstring[1];
static cvar_t password_var, cheats;
static cvar_t *sv_rconPassword = &password_var, *cvar_cheats = &cheats;
int cvar_modifiedFlags;
static struct { netadr_t redirectAddress; } svs;
static struct { int rconBucket; } querylimit;
static int executed, ban_seconds, source_id;
static void Cmd_TokenizeStringInternal(const char *, qboolean, cmdTokenizeParams_t *);
static int Cvar_SetVariant(cvar_t *, CvarValue, qboolean);
static void Com_Printf(int channel, const char *fmt, ...) {
    (void)channel;
    va_list ap; va_start(ap, fmt);
    vsnprintf(logs + strlen(logs), sizeof(logs) - strlen(logs), fmt, ap);
    va_end(ap);
    if (!strcmp(fmt, "Bad rcon")) strcpy(response, "Bad rcon");
    if (strstr(fmt, "shorter than 8")) strcpy(response, "shorter than 8");
}
#define Com_PrintError Com_Printf
static void Sys_EnterCriticalSection(int n) { (void)n; }
static void Sys_LeaveCriticalSection(int n) { (void)n; }
int Q_stricmp(const char *a, const char *b) { return strcasecmp(a,b); }
static void FreeString(const char *s) { free((void *)s); }
static char *CopyString(const char *s) { return strdup(s); }
void Q_strncpyz(char *d, const char *s, int n) { snprintf(d,n,"%s",s); }
static void Cmd_TokenizeString(const char *s) {
    tokens = (cmdTokenizeParams_t){0, sizeof(tokenbuf), tokenbuf, args};
    Cmd_TokenizeStringInternal(s, qfalse, &tokens);
}
char *Cmd_Argv(int n) { return n < tokens.cmd_argc ? args[n] : ""; }
int Cmd_Argc(void) { return tokens.cmd_argc; }
#define SV_Cmd_Argv Cmd_Argv
static void Cmd_EndTokenizedString(void) {}
void Cvar_Set2(const char *name, const char *value, qboolean force) {
    assert(!strcmp(name,"rcon_password"));
    CvarValue v = {.string = value};
    Cvar_SetVariant(sv_rconPassword, v, force);
}
static int MSG_ReadByte(msg_t *m) { return m->readcount < m->cursize ? m->data[m->readcount++] : -1; }
static int MSG_ReadLong(msg_t *m) {
    int v = 0; for (int i=0;i<4;i++) v |= (MSG_ReadByte(m) & 255) << (8*i); return v;
}
static void MSG_BeginReading(msg_t *m) { m->readcount=0; }
static void MSG_Init(msg_t *m, byte *b, int n) { (void)n; *m=(msg_t){b,0,0}; }
static void MSG_WriteLong(msg_t *m, int v) { for(int i=0;i<4;i++) m->data[m->cursize++]=(unsigned)v>>(8*i); }
static void MSG_WriteShort(msg_t *m, int v) { m->data[m->cursize++]=v; m->data[m->cursize++]=v>>8; }
static int NET_SendData(int sock, msg_t *m) { (void)sock; if(m->cursize==14) memcpy(&source_id,m->data+4,4); return m->cursize; }
static char *NET_AdrToString(netadr_t *a) { (void)a; return "127.0.0.1"; }
static int SVC_RateLimit(int *b,int n,int ms) { (void)b;(void)n;(void)ms;return 0; }
static void SV_FlushRedirect(char *b, qboolean last) { (void)b;(void)last; }
static void Com_BeginRedirect(char *b,int n,void (*f)(char *,qboolean)) { (void)b;(void)n;(void)f; }
static void Com_EndRedirect(void) {}
static void Cmd_ExecuteSingleCommand(int a,int b,const char *s) {
    (void)a;(void)b; executed=1; snprintf(response,sizeof(response),"EXECUTED:%s",s);
}
static int SV_PlayerBannedByip(netadr_t *a,char *b,int n) { (void)a;(void)b;(void)n;return 0; }
static int Auth_Authorize(const char *u,const char *p) { (void)u;(void)p;return -1; }
static uint64_t Auth_GetSteamID(const char *u) { (void)u;return 0; }
static int Com_GetRealtime(void) { return 1000; }
static void SV_PlayerAddBanByip(netadr_t *a,const char *r,int until) { (void)a;(void)r;ban_seconds=until-1000; }
