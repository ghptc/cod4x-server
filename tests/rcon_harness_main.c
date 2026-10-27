int main(int argc,char **argv) {
    assert(argc==3 || argc==2);
    password_var.type=CVAR_STRING;
    password_var.string=nullstring;
    password_var.latchedString=nullstring;
    if(argc==3) {
        int bound=!strcmp(argv[1],"--source-bound");
        int zero=!strcmp(argv[1],"--source-zero");
        int console=!strcmp(argv[1],"--source-console");
        assert(bound || zero || console || !strcmp(argv[1],"--source"));
        if(bound || zero)auth_handle=0;
        if(zero)authorized_record.steamid=0;
        Cvar_Set2("rcon_password","SyntheticServerPassword",qfalse);
        byte packet[1024]={0}; msg_t m; MSG_Init(&m,packet,sizeof(packet));
        MSG_WriteLong(&m,10+strlen(argv[2])); MSG_WriteLong(&m,7); MSG_WriteLong(&m,3);
        strcpy((char *)packet+m.cursize,argv[2]); m.cursize+=strlen(argv[2])+2;
        netadr_t from={0}; rconUser_t user={0};
        if(console) {
            assert(HL2Rcon_SourceRconAuth(&from,&m,&user));
            assert(user.steamid==0 && !strcmp(user.rconUsername,"console"));
            puts("source_master_console_authenticated=1");return 0;
        }
        if(bound) {
            assert(HL2Rcon_SourceRconAuth(&from,&m,&user));
            assert(user.steamid==42 && identity_lookups==0);
            puts("source_bound_to_verified_record=1 steamid=42");return 0;
        }
        assert(!HL2Rcon_SourceRconAuth(&from,&m,&user));
        assert(strstr(logs,"Bad rcon from 127.0.0.1\n"));
        assert(!strstr(logs,argv[2]));
        assert(!strstr(logs,"Disposable"));
        assert(source_id==-1 && ban_seconds==20);
        puts("source_rejected=1 response_id=-1 ban_seconds=20 redacted=1");
        return 0;
    }
    FILE *cfg=fopen(argv[1],"r"); assert(cfg);
    char line[4096], expected[2048]; assert(fgets(line,sizeof(line),cfg)); fclose(cfg);
    char *start=strchr(line,'"'); assert(start); ++start;
    char *end=strchr(start,'"'); assert(end); assert(end-start<sizeof(expected));
    memcpy(expected,start,end-start); expected[end-start]=0;
    Cmd_TokenizeString(line); Cvar_Set_f();
    assert(!strcmp(password_var.string,expected));
    int sock=socket(AF_INET,SOCK_DGRAM,0); assert(sock>=0);
    struct sockaddr_in addr={.sin_family=AF_INET,.sin_addr.s_addr=htonl(INADDR_LOOPBACK)};
    assert(!bind(sock,(struct sockaddr *)&addr,sizeof(addr)));
    socklen_t size=sizeof(addr); assert(!getsockname(sock,(struct sockaddr *)&addr,&size));
    printf("%u\n",ntohs(addr.sin_port)); fflush(stdout);
    byte packet[4096]; struct sockaddr_in client; size=sizeof(client);
    int n=recvfrom(sock,packet,sizeof(packet),0,(struct sockaddr *)&client,&size); assert(n>4);
    msg_t msg={packet,n,0}; char text[MAX_STRING_CHARS];
    MSG_ReadLong(&msg); MSG_ReadStringLine(&msg,text,sizeof(text));
    Cmd_TokenizeString(text); assert(!strcmp(Cmd_Argv(0),"rcon"));
    netadr_t from={sock}; SVC_RemoteCommand(&from,&msg);
    assert(!strstr(logs,"MODE_SECRET_CANARY"));
    assert(sendto(sock,response,strlen(response),0,(struct sockaddr *)&client,size)>=0);
    printf("cfg_length=%zu cfg_equal=%d\n",strlen(password_var.string),!strcmp(password_var.string,expected));
    close(sock); FreeString(password_var.string); FreeString(password_var.latchedString);
    return 0;
}
