/* Fixed, nonblocking host mode-control IPC. AGPL-3.0-or-later.
 * Only authenticated RCON ingress calls SV_RconModeIngress. Console/GSC never do.
 * No shell, credentials, image identifiers or selectable endpoint cross this API.
 */
#include "sv_mode_bridge.h"
#include "qcommon.h"
#include "qcommon_io.h"
#include "server.h"
#include "netchan.h"
#include "sys_main.h"
#include "cvar.h"
#include <string.h>
#include <stdio.h>
#ifndef _WIN32
#include <sys/socket.h>
#include <sys/un.h>
#include <unistd.h>
#include <errno.h>
#include <time.h>

#ifndef BRIDGE_SOCKET
#define BRIDGE_SOCKET "/run/cod4-mode-bridge/control.sock"
#endif
static int channel = -1;
static time_t opened, next_status;
static qboolean notify_peer;
static qboolean ack_pending;
static netadr_t peer;
static char request_id[33];
static char cached[192] = "Host controller unavailable. Runtime unchanged.";

static qboolean mode_name(const char *name) { return !strcmp(name,"promod") || !strcmp(name,"zombies"); }
static qboolean identifier(const char *s)
{
    int i;
    if (!strcmp(s,"none")) return qtrue;
    if (strlen(s) != 32) return qfalse;
    for (i=0;i<32;i++) if (!((s[i]>='0' && s[i]<='9') || (s[i]>='a' && s[i]<='f'))) return qfalse;
    return qtrue;
}
static qboolean word(const char *s)
{
    const char *values[] = {"idle","pending","accepted","success","rolled_back","recovery_required",
        "disabled","denied","invalid","busy","replay","already_active","not_qualified","failed",
        "verifying","rolling_back","submitted","unavailable"};
    unsigned i;
    for(i=0;i<sizeof(values)/sizeof(*values);i++) if(!strcmp(s,values[i])) return qtrue;
    return qfalse;
}
static const char *result_text(const char *code)
{
    if(!strcmp(code,"success")) return "Host confirmed successful mode transition.";
    if(!strcmp(code,"rolled_back")) return "Transition failed; previous exact runtime restored.";
    if(!strcmp(code,"already_active")) return "Requested mode is already active.";
    if(!strcmp(code,"not_qualified")) return "Mode or current baseline not qualified; runtime unchanged.";
    if(!strcmp(code,"disabled")) return "Host bridge disabled; runtime unchanged.";
    if(!strcmp(code,"denied")) return "Host request denied; runtime unchanged.";
    if(!strcmp(code,"busy")) return "Transition already in progress or awaiting operator recovery.";
    if(!strcmp(code,"replay")) return "Duplicate request rejected.";
    if(!strcmp(code,"recovery_required")) return "Rollback not confirmed; operator recovery required.";
    if(!strcmp(code,"accepted")) return "Request accepted; transition is not complete.";
    if(!strcmp(code,"failed") || !strcmp(code,"invalid")) return "Request failed; query status before retrying.";
    if(!strcmp(code,"idle")) return "No transition in progress.";
    return "Transition pending; completion has not been confirmed.";
}
static void close_channel(void) { if(channel>=0) close(channel); channel=-1; notify_peer=qfalse; ack_pending=qfalse; request_id[0]=0; }
static qboolean submit(const char *mode, const netadr_t *reply)
{
    struct sockaddr_un address;
    struct ucred credentials;
    socklen_t size=sizeof(credentials);
    char message[128];
    byte entropy[16];
    int i,n;
    if(channel>=0) return qfalse;
    channel=socket(AF_UNIX,SOCK_SEQPACKET|SOCK_NONBLOCK|SOCK_CLOEXEC,0);
    if(channel<0) return qfalse;
    memset(&address,0,sizeof(address)); address.sun_family=AF_UNIX;
    memcpy(address.sun_path,BRIDGE_SOCKET,sizeof(BRIDGE_SOCKET));
    if(connect(channel,(struct sockaddr*)&address,sizeof(address))<0 ||
       getsockopt(channel,SOL_SOCKET,SO_PEERCRED,&credentials,&size)<0 || credentials.uid!=0) { close_channel(); return qfalse; }
    if(mode) {
        if(!Sys_RandomBytes(entropy,sizeof(entropy))) { close_channel(); return qfalse; }
        for(i=0;i<16;i++) snprintf(request_id+i*2,3,"%02x",entropy[i]);
        n=snprintf(message,sizeof(message),"C4M1 switch %s %s",request_id,mode);
    } else n=snprintf(message,sizeof(message),"C4M1 status");
    if(send(channel,message,n,MSG_DONTWAIT|MSG_NOSIGNAL)!=n) { close_channel(); return qfalse; }
    if(reply) { peer=*reply; notify_peer=qtrue; }
    opened=time(NULL);
    return qtrue;
}
#endif

qboolean SV_RconModeFraming(const byte *wire, int length)
{
    int i;
    if(length<0 || length>=1024) return qfalse;
    for(i=0;i<length;i++) {
        if(wire[i]==0 || wire[i]=='\n') { if(i!=length-1) return qfalse; }
        else if(wire[i]<32 || wire[i]>126 || wire[i]=='%') return qfalse;
    }
    return qtrue;
}

qboolean SV_RconModeCommand(const char *raw)
{
    while(*raw==' ') ++raw;
    return (!Q_stricmpn(raw,"change_game",11) || !Q_stricmpn(raw,"change_mode",11)) &&
        (!raw[11] || raw[11]==' ' || raw[11]=='\t' || raw[11]=='\n' || raw[11]=='\r' || raw[11]==';');
}

qboolean SV_RconModeIngress(const char *raw, int power, const netadr_t *reply, qboolean framing)
{
    const char *argument;
    char game[MAX_OSPATH];
    /* Recognize malformed variants too, so they cannot fall through tokenization. */
    while(*raw==' ') ++raw;
    if(!SV_RconModeCommand(raw)) return qfalse;
    if(power!=100) { Com_Printf(CON_CHANNEL_DONT_FILTER,"Permission denied: change_game requires power 100.\n"); return qtrue; }
    argument=raw+11;
    if(!framing || (*argument && *argument!=' ')) { Com_Printf(CON_CHANNEL_DONT_FILTER,"Invalid mode request.\n"); return qtrue; }
    while(*argument==' ') ++argument;
    if(*argument && strcmp(argument,"promod") && strcmp(argument,"zombies")) {
        Com_Printf(CON_CHANNEL_DONT_FILTER,"Unsupported mode. Use exactly change_game promod or change_game zombies. Invalid mode request; runtime unchanged.\n"); return qtrue;
    }
#ifdef _WIN32
    Com_Printf(CON_CHANNEL_DONT_FILTER,"Host controller unavailable on this platform. Runtime unchanged.\n");
#else
    if(!*argument) {
        Cvar_VariableStringBuffer("fs_game",game,sizeof(game));
        Com_Printf(CON_CHANNEL_DONT_FILTER,"Current fs_game: %s\nAvailable switch targets: %s (last host response; every request revalidated).\nMODE_STATUS %s\n",*game?game:"main",
            strstr(cached,"result=idle") || strstr(cached,"result=success") || strstr(cached,"result=accepted") || strstr(cached,"result=rolled_back") || strstr(cached,"result=already_active") ? "promod,zombies" : "none",cached);
        if(!submit(NULL,reply) && channel<0)
            Com_Printf(CON_CHANNEL_DONT_FILTER,"Host controller unavailable; cached status may be stale.\n");
    } else {
        if(channel>=0 && !request_id[0]) close_channel();
        if(channel>=0) Com_Printf(CON_CHANNEL_DONT_FILTER,"Transition request already in progress; use change_game for status.\n");
        else if(submit(argument,reply)) {
            snprintf(cached,sizeof(cached),"operation=%s mode=%s result=submitted phase=pending",request_id,argument);
            Com_Printf(CON_CHANNEL_DONT_FILTER,"MODE_STATUS %s (not yet accepted). Use change_game for status after reconnect.\n",cached);
        } else Com_Printf(CON_CHANNEL_DONT_FILTER,"Host controller unavailable. Runtime unchanged.\n");
    }
#endif
    return qtrue;
}

void SV_ModeBridgeFrame(void)
{
#ifndef _WIN32
    char message[256],version[8],code[32],id[40],mode[16],phase[32],canonical[256],announcement[128];
    struct iovec iov={message,sizeof(message)-1};
    struct msghdr header;
    int n;
    /* Give queued player notices a normal game-frame send before host handoff. */
    if(channel>=0 && ack_pending) {
        n=snprintf(message,sizeof(message),"C4M1 notified %s",request_id);
        send(channel,message,n,MSG_DONTWAIT|MSG_NOSIGNAL);
        close_channel();
        return;
    }
    if(channel<0) {
        if(time(NULL)>=next_status) { next_status=time(NULL)+2; submit(NULL,NULL); }
        return;
    }
    memset(&header,0,sizeof(header)); header.msg_iov=&iov; header.msg_iovlen=1;
    n=recvmsg(channel,&header,MSG_DONTWAIT);
    if(n<0 && (errno==EAGAIN || errno==EWOULDBLOCK)) {
        if(time(NULL)-opened>120) { strcpy(cached,"Host validation timed out; outcome unknown. Query status."); close_channel(); }
        return;
    }
    if(n<=0 || header.msg_flags&MSG_TRUNC || memchr(message,0,n)) { close_channel(); return; }
    message[n]=0;
    if(sscanf(message,"%7s %31s %39s %15s %31s",version,code,id,mode,phase)!=5) { close_channel(); return; }
    snprintf(canonical,sizeof(canonical),"%s %s %s %s %s",version,code,id,mode,phase);
    if(strcmp(canonical,message) || strcmp(version,"C4M1") || !word(code) || !word(phase) ||
       (!mode_name(mode) && strcmp(mode,"none")) || !identifier(id)) { close_channel(); return; }
    if(request_id[0] && strcmp(request_id,id)) { close_channel(); return; }
    snprintf(cached,sizeof(cached),"operation=%s mode=%s result=%s phase=%s",id,mode,code,phase);
    Com_Printf(CON_CHANNEL_SERVER,"MODE_STATUS %s\n%s\n",cached,result_text(code));
    if(notify_peer) NET_OutOfBandPrint(NS_SERVER,&peer,"print\nMODE_STATUS %s\n%s\n",cached,result_text(code));
    if(!strcmp(code,"accepted") && request_id[0]) {
        snprintf(announcement,sizeof(announcement),"^3Mode change to %s accepted. Server restarting; reconnect shortly.",mode);
        SV_SayToPlayers(-1,-1,announcement);
        ack_pending=qtrue;
        return;
    }
    close_channel();
#endif
}
