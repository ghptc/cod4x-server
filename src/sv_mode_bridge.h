/* Authenticated ingress only. AGPL-3.0-or-later. */
#ifndef SV_MODE_BRIDGE_H
#define SV_MODE_BRIDGE_H
#include "q_shared.h"
#include "sys_net.h"
qboolean SV_RconModeIngress(const char *raw, int power, const netadr_t *reply, qboolean framing);
qboolean SV_RconModeFraming(const byte *wire, int length);
qboolean SV_RconModeCommand(const char *raw);
void SV_ModeBridgeFrame(void);
#endif
