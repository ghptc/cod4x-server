"""Execute production authorization functions at privilege and identity boundaries."""
from pathlib import Path
import subprocess
import tempfile
import unittest
from test_rcon import function
ROOT=Path(__file__).resolve().parents[1]

def execute(source):
    with tempfile.TemporaryDirectory() as d:
        path=Path(d)/'auth.c';binary=Path(d)/'auth';path.write_text(source)
        subprocess.run(['gcc',str(path),'-o',str(binary)],check=True)
        subprocess.run([str(binary)],check=True)

class AuthHardening(unittest.TestCase):
    def test_password_reset_cannot_take_over_higher_or_equal_role(self):
        source=r'''
#include <assert.h>
#include <stdint.h>
#include <stdarg.h>
#include <stdio.h>
#include <string.h>
#define CON_CHANNEL_DONT_FILTER 0
static int invoker=95,target=100,changed,argc=3;static char output[1024];
int Cmd_Argc(void){return argc;}
char *Cmd_Argv(int n){return n==1?"owner":"NEW_SECRET_CANARY";}
int Cmd_GetInvokerPower(void){return invoker;}
uint64_t Auth_GetSteamID(const char *name){return 42;}
int Auth_GetClPowerBySteamID(uint64_t id){return target;}
void Auth_ChangeAdminPassword(uint64_t id,const char *password){assert(id==42);changed++;}
void Com_Printf(int channel,const char *fmt,...){va_list ap;va_start(ap,fmt);vsnprintf(output,sizeof(output),fmt,ap);va_end(ap);}
#define Com_PrintError Com_Printf
'''
        source+=function('src/sv_auth.c','void Auth_ChangePasswordByMasterAdmin_f(')
        source+=r'''
int main(void){
 Auth_ChangePasswordByMasterAdmin_f();assert(!changed && !strstr(output,"NEW_SECRET_CANARY"));
 target=95;Auth_ChangePasswordByMasterAdmin_f();assert(!changed);
 target=50;Auth_ChangePasswordByMasterAdmin_f();assert(changed==1);
 invoker=100;target=100;Auth_ChangePasswordByMasterAdmin_f();assert(changed==2);
 invoker=20;target=100;Auth_ChangePasswordByMasterAdmin_f();assert(changed==2);
 return 0;
}
'''
        execute(source)

    def test_web_console_denies_unregistered_cvars_and_keeps_registered_permissions(self):
        source=r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#define SV_OUTPUTBUF_LENGTH 4096
#define XA(text) (++denied)
typedef int qboolean;typedef struct{int x;}xml_t;
static xml_t *xmlobjFlush;static int power=20,executed,denied;
int Cmd_GetInvokerPower(void){return power;}
int Cmd_GetPower(const char *name){return !strcmp(name,"bot_status")?20:-1;}
void Q_strncpyz(char *out,const char *s,int n){snprintf(out,n,"%s",s);}
void Q_strchrrepl(char *s,char a,char b){for(;*s;s++)if(*s==a){*s=b;break;}}
void Webadmin_FlushRedirect(char *s,qboolean last){}
void Com_BeginRedirect(char*b,int n,void(*f)(char*,qboolean)){}
void Com_EndRedirect(void){}
void Cmd_ExecuteSingleCommand(int a,int b,const char *text){executed++;}
'''
        source+=function('src/webadmin.c','void Webadmin_ConsoleCommand(')
        source+=r'''
int main(void){
 xml_t xml;
 Webadmin_ConsoleCommand(&xml,"rcon_password",42);assert(!executed && denied==1);
 Webadmin_ConsoleCommand(&xml,"rcon_password attacker",42);assert(!executed && denied==2);
 Webadmin_ConsoleCommand(&xml,"bot_status",42);assert(executed==1);
 power=100;Webadmin_ConsoleCommand(&xml,"rcon_password",42);assert(executed==2);
 return 0;
}
'''
        execute(source)

    def test_web_session_binds_record_despite_numeric_or_duplicate_names(self):
        source=r'''
#include <assert.h>
#include <stdint.h>
#include <string.h>
#include <strings.h>
#define MAX_AUTH_ADMINS 4
typedef struct {char username[32],sessionid[65];uint64_t steamid;}authData_admin_t;
static struct {authData_admin_t admins[MAX_AUTH_ADMINS];}auth_admins;
int Q_stricmp(const char *a,const char *b){return strcasecmp(a,b);}
'''
        source+=function('src/sv_auth.c','authData_admin_t* Auth_FindSessionAdmin(')
        source+=function('src/sv_auth.c','authData_admin_t* Auth_GetAdminFromIndex(')
        source+=r'''
int main(void){
 authData_admin_t *low=&auth_admins.admins[0],*high=&auth_admins.admins[1];
 strcpy(low->username,"76561198000000999");low->steamid=42;memset(low->sessionid,'a',64);
 strcpy(high->username,low->username);high->steamid=999;memset(high->sessionid,'b',64);
 assert(Auth_FindSessionAdmin(low->sessionid)==low && Auth_FindSessionAdmin(high->sessionid)==high);
 strcpy(low->username,"renamed");assert(Auth_FindSessionAdmin(low->sessionid)==low);
 assert(!Auth_FindSessionAdmin(0) && !Auth_FindSessionAdmin("short"));
 low->sessionid[0]=0;assert(!Auth_FindSessionAdmin("aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"));
 assert(!Auth_GetAdminFromIndex(-1) && !Auth_GetAdminFromIndex(MAX_AUTH_ADMINS));
 assert(Auth_GetAdminFromIndex(0)==low);
 return 0;
}
'''
        execute(source)
