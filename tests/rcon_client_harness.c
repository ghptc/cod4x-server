/* Boundaries for the optional, revision-pinned public CoD4x CL_Rcon_f probe. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
#include <assert.h>
#define CON_CHANNEL_DONT_FILTER 0
#define NA_UNSPEC 0
#define NS_CLIENT 0
#define CA_CONNECTED 3
#define qfalse 0
typedef struct { int type; } netadr_t;
static struct { int state; } clientUIActives;
static struct { struct { netadr_t remoteAddress; } netchan; } clc;
static netadr_t rcondst={1};
static char *arguments[4];
static int argument_count;
static int Cmd_Argc(void) { return argument_count; }
static char *Cmd_Argv(int n) { return arguments[n]; }
static int Q_stricmp(const char *a,const char *b) { return strcasecmp(a,b); }
static void Q_strncpyz(char *d,const char *s,int n) { snprintf(d,n,"%s",s); }
static void Q_strcat(char *d,int n,const char *s) { strncat(d,s,n-strlen(d)-1); }
static void Com_Printf(int c,const char *fmt,...) { (void)c;(void)fmt; }
#define Com_DPrintf Com_Printf
static int NET_StringToAdr(const char *s,netadr_t *a,int t) { (void)s;(void)t;a->type=1;return 1; }
static char *NET_AdrToString(netadr_t *a) { (void)a;return "127.0.0.1"; }
static void Cmd_Argsv(int first,char *dest,int size) {
    dest[0]=0;
    for(int i=first;i<argument_count;i++) {
        if(i>first) Q_strcat(dest,size," ");
        Q_strcat(dest,size,arguments[i]);
    }
}
static void NET_SendPacket(int source,int size,const char *message,netadr_t *to) {
    (void)source;(void)to; assert(fwrite(message,1,size,stdout)==size);
}
void CL_Rcon_f(void);
int main(int argc,char **argv) {
    assert(argc==2); int n=atoi(argv[1]); assert(n>0 && n<1200);
    char password[1200]; for(int i=0;i<n;i++) password[i]="Ab9"[i%3]; password[n]=0;
    arguments[0]="rcon"; arguments[1]="login"; arguments[2]="DisposableOld16X9"; argument_count=3;
    CL_Rcon_f();
    arguments[2]=password; CL_Rcon_f();
    arguments[1]="status"; argument_count=2; CL_Rcon_f();
    return 0;
}
