"""Native authenticated bridge policy; no game assets or Docker privileges."""
from pathlib import Path
import subprocess
import tempfile
import unittest
ROOT = Path(__file__).resolve().parents[1]
class ModeBridge(unittest.TestCase):
    def test_native_policy_and_ipc(self):
        with tempfile.TemporaryDirectory() as d:
            binary=Path(d)/'bridge'
            subprocess.run(['gcc','-m32','-D_GNU_SOURCE','-ffunction-sections','-fdata-sections',
                '-Wl,--gc-sections','-fno-pie','-no-pie',str(ROOT/'tests/test_mode_bridge.c'),'-o',str(binary)],check=True)
            subprocess.run([str(binary)],check=True)

    def test_source_rcon_restores_context_after_rejected_command(self):
        from test_rcon import function
        fixture=r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <strings.h>
#define SV_OUTPUTBUF_LENGTH 4096
#define CON_CHANNEL_DONT_FILTER 0
static int current=73,client=8,auth_power=20,ended,executed;
static uint64_t identity=99;
static char invoker[64]="previous";
int Cmd_GetInvokerPower(void){return current;}
int Cmd_GetInvokerClnum(void){return client;}
uint64_t Cmd_GetInvokerSteamID(void){return identity;}
const char *Cmd_GetInvokerName(char *out,int n){snprintf(out,n,"%s",invoker);return out;}
void Cmd_SetCurrentInvokerInfo(int p,int c,uint64_t id,const char *name){current=p;client=c;identity=id;snprintf(invoker,sizeof(invoker),"%s",name);}
int Auth_GetClPowerBySteamID(uint64_t id){return auth_power;}
const char *Auth_GetNameBySteamID(uint64_t id){return "admin";}
void HL2Rcon_SourceRconFlushRedirect(char *s){}
void Com_BeginRedirect(char *b,int n,void(*f)(char*)){}
void Com_EndRedirect(void){ended++;}
void Com_Printf(int channel,const char *fmt,...){}
void Q_strncpyz(char *out,const char *value,int n){snprintf(out,n,"%s",value);}
void Q_strchrrepl(char *s,char from,char to){for(;*s;s++)if(*s==from){*s=to;break;}}
int Q_stricmpn(const char*a,const char*b,int n){return strncasecmp(a,b,n);}
int Cmd_GetPower(const char *s){return !strcmp(s,"rcon_password")?-1:100;}
void Cmd_ExecuteSingleCommand(int a,int b,const char*s){executed++;}
void HL2Rcon_StatusCommand(void){}
'''
        fixture+=function('src/hl2rcon.c','void HL2Rcon_ExecuteConsoleCommand(')
        fixture+=r'''
int main(void){
 const char *bad[]={"x","abcdefghijklmnopqrstuvwxyz0123456789","change_mode zombies","rcon_password","rcon_password attacker"};
 for(unsigned i=0;i<5;i++){
  HL2Rcon_ExecuteConsoleCommand(bad[i],123);
  assert(current==73 && client==8 && identity==99 && !strcmp(invoker,"previous"));
  assert(ended==(int)i+1 && executed==0);
 }
 auth_power=100;HL2Rcon_ExecuteConsoleCommand("rcon_password",123);assert(executed==1 && current==73);
 return 0;
}
'''
        with tempfile.TemporaryDirectory() as d:
            source=Path(d)/'source.c';source.write_text(fixture);binary=Path(d)/'source'
            subprocess.run(['gcc',str(source),'-o',str(binary)],check=True)
            subprocess.run([str(binary)],check=True)
