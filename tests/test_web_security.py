"""Execute the production HTTP, HTML and session boundaries without networking."""
from pathlib import Path
import os
import subprocess
import tempfile
import unittest
from test_rcon import function

ROOT = Path(__file__).resolve().parents[1]


def execute(source, sanitize=False):
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / 'boundary.c'
        binary = Path(directory) / 'boundary'
        path.write_text(source)
        flags = ['-fsanitize=address,undefined', '-fno-omit-frame-pointer', '-g'] if sanitize else []
        subprocess.run(['gcc', '-std=gnu11', *flags, str(path), '-o', str(binary)], check=True)
        env = {**os.environ, 'ASAN_OPTIONS': 'detect_leaks=0'}
        subprocess.run([str(binary)], check=True, env=env)


class WebSecurity(unittest.TestCase):
    def test_http_segmented_framing_bounds_and_cookie_parsing(self):
        source = r'''
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
#include <stdint.h>
#define MAX_STRING_CHARS 1024
#define HTTP_SERVER_MAX_HEADER 16384
#define HTTP_SERVER_MAX_BODY 65536
#define HTTP_SERVER_MAX_REQUEST (HTTP_SERVER_MAX_HEADER+HTTP_SERVER_MAX_BODY)
#define CON_CHANNEL_FILEDL 0
#define qfalse 0
#define qtrue 1
#define HTTP_HEAD 2
#define HTTP_POST 1
#define HTTP_GET 0
typedef unsigned char byte;typedef int qboolean;
typedef struct {int type;}netadr_t;
typedef struct {byte *data;int maxsize,cursize,readcount;}msg_t;
typedef struct {netadr_t remote;msg_t recvmsg;int finallen,mode,version,contentLength,headerLength,transferactive;char url[1024],contentType[64],cookie[1024];}ftRequest_t;
#define Com_Memcpy memcpy
#define L_Malloc malloc
#define L_Free free
void MSG_BeginReading(msg_t*m){m->readcount=0;}
int MSG_ReadByte(msg_t*m){return m->readcount<m->cursize?m->data[m->readcount++]:-1;}
void Com_Printf(int c,const char*f,...){ }
#define Com_PrintError Com_Printf
#define Com_DPrintf Com_Printf
char *NET_AdrToString(netadr_t*a){return "local";}
#define Q_strncmp strncmp
#define Q_stricmpn strncasecmp
void Q_strncpyz(char*d,const char*s,int n){assert(n>0);snprintf(d,n,"%s",s);}
'''
        source += function('src/msg.c', 'char *MSG_ReadStringLine(')
        source += function('src/httpftp.c', 'int HTTPServer_ReadMessage(')
        source += function('src/httpftp.c', 'void HTTPServer_ReadSessionId(')
        source += r'''
static ftRequest_t request(void){ftRequest_t r={0};r.finallen=-1;r.recvmsg.data=malloc(2);r.recvmsg.maxsize=2;return r;}
static int feed(ftRequest_t*r,const char*s,int n){netadr_t from={1};msg_t m={(byte*)s,n,n,0};return HTTPServer_ReadMessage(&from,&m,r);}
static void packet(const char*s,int expected){ftRequest_t r=request();assert(feed(&r,s,strlen(s))==expected);free(r.recvmsg.data);}
int main(void){
 const char *post="POST /webadmin?action=sendcmd HTTP/1.1\r\nContent-Length: 3\r\n\r\na=b";
 for(int split=1;split<strlen(post);++split){
  ftRequest_t r=request();assert(feed(&r,post,split)==0);assert(feed(&r,post+split,strlen(post)-split)==1);
  assert(!strcmp(r.url,"/webadmin?action=sendcmd"));
  assert(!strcmp((char*)r.recvmsg.data+r.headerLength,"a=b"));free(r.recvmsg.data);
 }
 packet("GET / HTTP/1.1\r\n\r\n",1);
 packet("HEAD / HTTP/1.0\r\n\r\n",1);
 packet("GET\n\r\n\r\n",-1);
 packet("HEAD\n\r\n\r\n",-1);
 packet("POST\n\r\n\r\n",-1);
 packet("GETX / HTTP/1.1\r\n\r\n",-1);
 packet("HEADX / HTTP/1.1\r\n\r\n",-1);
 packet("POSTX / HTTP/1.1\r\n\r\n",-1);
 packet("POST / HTTP/1.1\r\nContent-Length: 3\r\n\r\na=bextra",-1);
 packet("POST / HTTP/1.1\r\nContent-Length: -1\r\n\r\n",-1);
 packet("POST / HTTP/1.1\r\nContent-Length: 2147483647\r\n\r\n",-1);
 packet("POST / HTTP/1.1\r\nContent-Length: 999999999999999999999\r\n\r\n",-1);
 packet("POST / HTTP/1.1\r\nContent-Length: 1\r\nContent-Length: 1\r\n\r\na",-1);
 packet("POST / HTTP/1.1\r\nTransfer-Encoding: chunked\r\n\r\n",-1);
 packet("POST / HTTP/1.1\r\nContent-Length: 1junk\r\n\r\na",-1);
 ftRequest_t r=request();char chunk[128]={0};r.finallen=64;r.recvmsg.cursize=1;
 assert(feed(&r,chunk,sizeof(chunk))==-1);free(r.recvmsg.data);
 r=request();char *large=malloc(HTTP_SERVER_MAX_HEADER);memset(large,'x',HTTP_SERVER_MAX_HEADER);
 assert(feed(&r,large,HTTP_SERVER_MAX_HEADER)==-1);free(large);free(r.recvmsg.data);
 r=request();char header[]="POST / HTTP/1.1\r\nContent-Length: 65536\r\n\r\n";
 assert(feed(&r,header,strlen(header))==0);large=malloc(65536);memset(large,'a',65536);
 assert(feed(&r,large,65536)==1);assert(r.recvmsg.data[r.recvmsg.cursize]==0);free(large);free(r.recvmsg.data);
 r=request();char line[1100];memset(line,'x',sizeof(line));memcpy(line,"GET /",5);memcpy(line+1080," HTTP/1.1\r\n\r\n",14);
 assert(feed(&r,line,1094)==-1);free(r.recvmsg.data);
 ftRequest_t cookies={0};char token[65],out[128];memset(token,'a',64);token[64]=0;
 const char *invalid[]={"SessionId=","SessionId=; Other=value","OtherSessionId=abc","SessionId=short","SessionId=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaz"};
 for(int i=0;i<sizeof(invalid)/sizeof(*invalid);++i){strcpy(cookies.cookie,invalid[i]);HTTPServer_ReadSessionId(&cookies,out,sizeof(out));assert(!*out);}
 snprintf(cookies.cookie,sizeof(cookies.cookie),"Other=value; SessionId=%s; Extra=value",token);
 HTTPServer_ReadSessionId(&cookies,out,sizeof(out));assert(!strcmp(out,token));
 HTTPServer_ReadSessionId(&cookies,out,1);assert(!*out);
 return 0;
}
'''
        execute(source, sanitize=True)

    def test_untrusted_html_and_color_output_are_escaped_and_bounded(self):
        source = r'''
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <stdarg.h>
#include <string.h>
#define qfalse 0
#define qtrue 1
#define CON_CHANNEL_SYSTEM 0
typedef unsigned char byte;typedef int qboolean;
typedef struct {char *buffer;int bufposition,buffersize;}xml_t;
#define XA(text) XML_AppendToBuffer(xmlobj,text)
#define Com_Memcpy memcpy
void Com_Printf(int c,const char*f,...){ }
int Com_sprintf(char*d,int n,const char*f,...){va_list ap;va_start(ap,f);int r=vsnprintf(d,n,f,ap);va_end(ap);return r;}
char* htmlq3colors[]={"#000000","#FF0000","#00FF00","#FFFF00","#0000FF","#00FFFF","#FF00FF","#A0A0A0","#7B8FB0","#A69169"};
'''
        for file, signature in [('src/qshared.c', 'void XML_AppendToBuffer('),
                                ('src/qshared.c', 'void XML_Escape('),
                                ('src/webadmin.c', 'static void Webadmin_AppendText('),
                                ('src/webadmin.c', 'char* Webadmin_ConvertToHTMLColor(')]:
            source += function(file, signature)
        source += r'''
int main(void){
 char output[2048];
 Webadmin_ConvertToHTMLColor("^1<svg/onload=alert(1)>&\"'",output,sizeof(output));
 assert(!strstr(output,"<svg") && strstr(output,"&lt;svg") && strstr(output,"&amp;") && strstr(output,"&quot;") && strstr(output,"&#39;"));
 assert(strstr(output,"<span style=\"color: #FF0000\">") && strstr(output,"</span>"));
 for(int size=1;size<140;++size){char *out=malloc(size);Webadmin_ConvertToHTMLColor("^1^2^3<>&\"'long^4data",out,size);assert(strlen(out)<size);free(out);}
 char raw[160];memset(raw,'x',sizeof(raw));memcpy(raw+60,"<svg/onload=alert(1)>",21);raw[159]=0;
 char rendered[4096]={0};xml_t xml={rendered,0,sizeof(rendered)};
 Webadmin_AppendText(&xml,raw);assert(!strstr(rendered,"<svg") && strstr(rendered,"&lt;svg"));
 Webadmin_AppendText(&xml,"\n\t<next>\r\n");assert(strstr(rendered,"\n\t&lt;next&gt;\r\n"));
 return 0;
}
'''
        execute(source, sanitize=True)

    def test_password_recovery_revokes_existing_web_session(self):
        source = r'''
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
#include <stdint.h>
#define MAX_AUTH_ADMINS 4
#define qfalse 0
#define SEC_HASH_SHA256 0
#define CON_CHANNEL_DONT_FILTER 0
typedef int qboolean;typedef unsigned char byte;
typedef struct {char username[32],sessionid[65],sha256[129],salt[65];uint64_t steamid;}authData_admin_t;
struct {authData_admin_t admins[MAX_AUTH_ADMINS];}auth_admins;
#define Q_stricmp strcasecmp
#define Com_sprintf snprintf
void Q_strncpyz(char*d,const char*s,int n){snprintf(d,n,"%s",s);}
void NV_ProcessBegin(void){}void NV_ProcessEnd(void){}
void Com_Printf(int c,const char*f,...){ }
#define Com_PrintError Com_Printf
void SV_SApiSteamIDToString(uint64_t id,char*d,int n){snprintf(d,n,"synthetic");}
void Com_RandomBytes(void*b,int n){memset(b,'a',n);}
int Sec_HashMemory(int kind,const void *data,int n,char *out,unsigned long *size,int mode){memset(out,'b',*size-1);out[*size-1]=0;return 1;}
'''
        source += function('src/sv_auth.c', 'authData_admin_t* Auth_FindSessionAdmin(')
        source += function('src/sv_auth.c', 'void Auth_ChangeAdminPassword(')
        source += r'''
int main(void){
 authData_admin_t *u=&auth_admins.admins[0];u->steamid=42;strcpy(u->username,"synthetic");memset(u->sessionid,'a',64);
 char cookie[65];memcpy(cookie,u->sessionid,65);assert(Auth_FindSessionAdmin(cookie)==u);
 Auth_ChangeAdminPassword(42,"SyntheticReplacementPassword");assert(!Auth_FindSessionAdmin(cookie));return 0;
}
'''
        execute(source)
