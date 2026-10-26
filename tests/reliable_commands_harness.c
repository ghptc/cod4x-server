/* Isolated I/O boundaries; production functions are appended by the test. */
#include "server.h"
#include "msg.h"
#include "qcommon_io.h"
#undef assert
#include <assert.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

serverStatic_t svs;
static cvar_t maxclients_var, fps_var, downloadrate_var, allow_var, pure_var,
              www_var, url_var, disconnected_var;
cvar_t *sv_maxclients = &maxclients_var, *sv_fps = &fps_var;
cvar_t *sv_maxDownloadRate = &downloadrate_var, *sv_allowDownload = &allow_var;
cvar_t *sv_pure = &pure_var, *sv_wwwDownload = &www_var;
cvar_t *sv_wwwBaseURL = &url_var, *sv_wwwDlDisconnected = &disconnected_var;
static int drops, oob, transport_calls, closed, refreshed;
static int send_window = 10000, buffered;
static byte transport[131072], fixture[33001];
static int transport_len, filepos;
static client_t *refreshed_client;

void Com_Printf(conChannel_t c, const char *f, ...) { (void)c; (void)f; }
void Com_PrintNoRedirect(conChannel_t c, const char *f, ...) { (void)c; (void)f; }
void Com_PrintWarning(conChannel_t c, const char *f, ...) { (void)c; (void)f; }
void Com_DPrintf(conChannel_t c, const char *f, ...) { (void)c; (void)f; }
void Com_Error(int code, const char *format, ...) {
    (void)code; (void)format; abort();
}
int Com_sprintf(char *out, int size, const char *format, ...) {
    va_list ap; va_start(ap, format);
    int n = vsnprintf(out, size, format, ap); va_end(ap); return n;
}
void Q_strncpyz(char *out, const char *in, int size) {
    assert(size > 0); snprintf(out, size, "%s", in);
}
void NET_OutOfBandPrint(netsrc_t source, netadr_t *address, const char *format, ...) {
    (void)source; (void)address; assert(!strcmp(format, "disconnect")); ++oob;
}
void SV_DelayDropClient(client_t *client, const char *reason) {
    (void)client; assert(!strcmp(reason, "EXE_SERVERCOMMANDOVERFLOW")); ++drops;
}
qboolean FS_VerifyPak(const char *name) { return !strcmp(name, "mods/fixture/test.iwd"); }
long FS_SV_FOpenFileRead(const char *name, fileHandle_t *handle) {
    assert(FS_VerifyPak(name)); *handle = 1; filepos = 0; return sizeof(fixture);
}
int FS_Read(void *out, int size, fileHandle_t handle) {
    assert(handle == 1 && size >= 0 && filepos + size <= (int)sizeof(fixture));
    memcpy(out, fixture + filepos, size); filepos += size; return size;
}
qboolean FS_FCloseFile(fileHandle_t handle) { assert(handle == 1); ++closed; return qtrue; }
void SV_DropClient(client_t *client, const char *reason) {
    (void)client; (void)reason; assert(!"unexpected download rejection");
}
void SV_WriteChecksumInfo(msg_t *msg, const char *name) {
    assert(FS_VerifyPak(name)); MSG_WriteLong(msg, 1234);
}
int ReliableMessageGetDataSendWindowSize(netreliablemsg_t *channel) {
    (void)channel; return send_window;
}
int ReliableMessageGetSendBufferSize(netreliablemsg_t *channel) {
    (void)channel; return buffered;
}
int ReliableMessageSend(netreliablemsg_t *channel, byte *data, int len) {
    (void)channel; assert(len <= (int)sizeof(transport));
    memcpy(transport, data, len); transport_len = len; ++transport_calls; return len;
}
void SV_SendClientGameState(client_t *client) {
    /* Verify the completion handler closes its transfer before refreshing. */
    assert(!client->download && !client->downloadName[0] && !client->wwwDl_var01);
    refreshed_client = client; ++refreshed;
}
enum { DLSUBCMD_SERVERDL, DLSUBCMD_FILEINIT, DLSUBCMD_WWWRD, DLSUBCMD_FAIL };
