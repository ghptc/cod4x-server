/* Execute the actual bridge with controlled IPC boundaries; no host actions. */
#define socket test_socket
#define connect test_connect
#define getsockopt test_getsockopt
#define send test_send
#define recvmsg test_recvmsg
#define close test_close
#define time test_time
#include "../src/sv_mode_bridge.c"
#undef assert
#include <assert.h>
#include <stdarg.h>
static int sockets, sends, broadcasts, root_peer=1, nonce;
static unsigned char incoming[512];
static int incoming_size, incoming_flags;
static char output[2048], sent[256];
time_t test_time(time_t *p) { if(p) *p=1000; return 1000; }
int test_socket(int domain,int type,int protocol) { assert(domain==AF_UNIX && type&SOCK_NONBLOCK); sockets++; return 42; }
int test_connect(int fd,const struct sockaddr *a,socklen_t n) { assert(fd==42); return 0; }
int test_getsockopt(int fd,int level,int option,void *data,socklen_t *size) {
 assert(option==SO_PEERCRED); ((struct ucred*)data)->uid=root_peer?0:1000; return 0;
}
ssize_t test_send(int fd,const void *data,size_t size,int flags) {
 assert(fd==42 && flags&MSG_DONTWAIT); assert(size<sizeof(sent)); memcpy(sent,data,size);sent[size]=0;sends++;return size;
}
ssize_t test_recvmsg(int fd,struct msghdr *header,int flags) {
 assert(flags&MSG_DONTWAIT); if(!incoming_size) { errno=EAGAIN;return -1; }
 assert(incoming_size<255);memcpy(header->msg_iov[0].iov_base,incoming,incoming_size);
 header->msg_flags=incoming_flags;int n=incoming_size;incoming_size=0;return n;
}
int test_close(int fd) { assert(fd==42); return 0; }
qboolean Sys_RandomBytes(byte *data,int n) { memset(data,++nonce,n); return qtrue; }
void Com_Printf(conChannel_t channel,const char *fmt,...) {
 va_list ap;va_start(ap,fmt);vsnprintf(output,sizeof(output),fmt,ap);va_end(ap);
}
int Q_stricmpn(const char*a,const char*b,int n) { return strncasecmp(a,b,n); }
void SV_SayToPlayers(int cl,int team,char *text) { broadcasts++;assert(strstr(text,"accepted")); }
void NET_OutOfBandPrint(netsrc_t sock,netadr_t *adr,const char *fmt,...) { }
const char *Cvar_VariableStringBuffer(const char *name,char *buffer,int n) { snprintf(buffer,n,"mods/pml220");return buffer; }
static void reset(void) { close_channel();sockets=sends=broadcasts=0;output[0]=0;incoming_size=incoming_flags=0;root_peer=1; }
static void receive(const char *code,const char *id,const char *mode,const char *phase) {
 incoming_size=snprintf((char*)incoming,sizeof(incoming),"C4M1 %s %s %s %s",code,id,mode,phase);
}
int main(void) {
 const char *commands[]={"change_game","change_mode"};
 for(unsigned c=0;c<2;c++) {
  char command[160];
  reset();
  for(int p=0;p<100;p++) {snprintf(command,sizeof(command),"%s zombies",commands[c]);assert(SV_RconModeIngress(command,p,NULL,qtrue));assert(!sockets);}
  const char *invalid[]={"promod;quit","promod extra","../zombies","$(id)","promod\nquit"};
  for(unsigned i=0;i<sizeof(invalid)/sizeof(*invalid);i++) {snprintf(command,sizeof(command),"%s %s",commands[c],invalid[i]);assert(SV_RconModeIngress(command,100,NULL,qtrue));assert(!sockets);}
  snprintf(command,sizeof(command),"%s zombies",commands[c]);
  assert(SV_RconModeIngress(command,100,NULL,qfalse));assert(!sockets);
  assert(SV_RconModeIngress(command,100,NULL,qtrue));assert(sockets==1 && sends==1 && strstr(sent," zombies"));
 }
 assert(!SV_RconModeCommand("change_game_extra zombies"));
 const char *bad[]={"hardcore","Zombies","promod;quit","promod //comment","\"promod\"","promod extra","promod\nquit","../zombies","$(id)","promod\t"};
 reset();
 for(int p=0;p<100;p++) {assert(SV_RconModeIngress("change_mode zombies",p,NULL,qtrue));assert(!sockets);assert(strstr(output,"Permission denied"));}
 for(unsigned i=0;i<sizeof(bad)/sizeof(*bad);i++) {char raw[128];snprintf(raw,sizeof(raw),"change_mode %s",bad[i]);assert(SV_RconModeIngress(raw,100,NULL,qtrue));assert(!sockets);}
 assert(!SV_RconModeIngress("exec proxy.cfg",100,NULL,qtrue));
 assert(SV_RconModeIngress("change_mode promod",100,NULL,qfalse));assert(!sockets);
 assert(!SV_RconModeFraming((byte*)" promod\nquit",12));
 const byte nul[]={'p',0,'q'};assert(!SV_RconModeFraming(nul,sizeof(nul)));
 assert(SV_RconModeFraming((byte*)" promod\n",8));
 assert(!SV_RconModeFraming((byte*)"x%y",3));
 root_peer=0;SV_RconModeIngress("change_mode promod",100,NULL,qtrue);assert(!sends);
 reset();strcpy(cached,"old success");
 assert(submit(NULL,NULL));assert(!request_id[0]);
 SV_RconModeIngress("change_mode zombies",100,NULL,qtrue);
 assert(sockets==2 && request_id[0] && strstr(output,"submitted") && !strstr(cached,"old success"));
 char id[33];strcpy(id,request_id);assert(strstr(output,id));
 receive("accepted",id,"zombies","pending");incoming[incoming_size++]=0;incoming[incoming_size++]='x';
 SV_ModeBridgeFrame();assert(!broadcasts && channel<0);
 reset();SV_RconModeIngress("change_mode zombies",100,NULL,qtrue);strcpy(id,request_id);
 receive("accepted",id,"zombies","pending");SV_ModeBridgeFrame();assert(broadcasts==1 && ack_pending && channel>=0 && !strstr(sent,"C4M1 notified"));
 SV_ModeBridgeFrame();assert(strstr(sent,"C4M1 notified") && channel<0);
 reset();SV_RconModeIngress("change_mode promod",100,NULL,qtrue);
 receive("accepted","aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","promod","pending");SV_ModeBridgeFrame();assert(!broadcasts);
 reset();assert(submit(NULL,NULL));receive("rolled_back","aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","zombies","rolled_back");
 SV_ModeBridgeFrame();assert(strstr(cached,"result=rolled_back") && !broadcasts);
 puts("mode bridge: bounded IPC, root peer, strict grammar, permissions, reply binding and notification passed");
 return 0;
}
