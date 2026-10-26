/* Execute the production native rotation with deterministic randomness and I/O. */
#include "../src/sv_cmds.c"
#undef assert
#include <assert.h>
#include <stdio.h>

cvar_t *com_sv_running, *sv_randomMapRotation, *sv_mapRotation, *sv_mapRotationCurrent;
cvar_t *sv_g_gametype, *sv_mapname, *sv_cheats;
static cvar_t running, random_rotation, rotation, remaining, gametype, current, cheats;
static char strings[4][CVAR_STRING_SIZE];
static int seed, loads, restarts;
static const char *command="map", *argument="mp_crash";
int Cmd_Argc(void) { return 2; }
char *Cmd_Argv(int n) { return (char *)(n==0 ? command : argument); }
void Com_Error(int level, const char *fmt, ...) { (void)level; (void)fmt; abort(); }
int Com_RandomInt(void) { return seed++; }
void Com_Printf(conChannel_t c, const char *fmt, ...) { (void)c; (void)fmt; }
void Com_PrintError(conChannel_t c, const char *fmt, ...) { (void)c; (void)fmt; }
void Com_PrintWarning(conChannel_t c, const char *fmt, ...) { (void)c; (void)fmt; }
void Cvar_SetString(cvar_t *var, const char *value)
{
    int n=var==&remaining ? 0 : var==&gametype ? 1 : 2;
    snprintf(strings[n],sizeof(strings[n]),"%s",value);
    ((cvar_t *)var)->string=strings[n];
}
void Cvar_SetBool(cvar_t *var, qboolean value) { ((cvar_t *)var)->boolean=value; }
qboolean SV_Map(const char *name) { ++loads; Cvar_SetString(&current,name); running.boolean=qtrue; return qtrue; }
void SV_MapRestart(qboolean fast) { (void)fast; ++restarts; }
static void setup(const char *list, int random)
{
    memset(&running,0,sizeof(running));
    random_rotation.boolean=random;
    rotation.string=(char *)list; remaining.string="";gametype.string="sd";current.string="";
    com_sv_running=&running;sv_randomMapRotation=&random_rotation;sv_mapRotation=&rotation;
    sv_mapRotationCurrent=&remaining;sv_g_gametype=&gametype;sv_mapname=&current;sv_cheats=&cheats;
    command="map";argument="mp_crash";loads=restarts=0;
}
int main(void)
{
    const char *list="gametype sd map mp_crash gametype sd map mp_strike gametype sd map mp_backlot";
    int seen=0;
    for(int n=0;n<12;++n) {
        setup(list,1);seed=n;SV_Map_f();
        assert(loads==1 && !restarts);
        if(!strcmp(current.string,"mp_crash"))seen|=1;
        else if(!strcmp(current.string,"mp_strike"))seen|=2;
        else if(!strcmp(current.string,"mp_backlot"))seen|=4;
        else assert(0);
        char previous[MAX_QPATH];
        for(int i=0;i<12;++i) {
            snprintf(previous,sizeof(previous),"%s",current.string);
            SV_MapRotate_f();assert(strcmp(previous,current.string));
        }
        /* Explicit administrator maps retain their target after startup. */
        argument="mp_strike";SV_Map_f();assert(!strcmp(current.string,"mp_strike"));
        Cvar_SetString(&remaining,"gametype sd map mp_strike");
        SV_MapRotate_f();assert(strcmp(current.string,"mp_strike"));
    }
    assert(seen==7);
    setup("map mp_crash",1);SV_Map_f();SV_MapRotate_f();assert(loads==2 && !restarts);
    setup(list,0);SV_Map_f();assert(!strcmp(current.string,"mp_crash"));
    const char *invalid[]={"", "gametype", "map", "gametype sd", "unknown value"};
    for(unsigned i=0;i<sizeof(invalid)/sizeof(*invalid);++i) {
        setup(invalid[i],1);SV_MapRotate_f();assert(!loads);
    }
    puts("native rotation: randomized startup, cursor, no repeats, admin maps, single-map and malformed lists passed");
}
