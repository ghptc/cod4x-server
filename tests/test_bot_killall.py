"""Execute the production command/death bodies with controlled engine fixtures."""
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


def body(path, signature):
    text = (ROOT / path).read_text(errors='replace')
    start = text.index(signature)
    end = text.index('\n}', start) + 2
    return text[start:end]


class BotKillAll(unittest.TestCase):
    def test_permission(self):
        source = (ROOT / 'src/sv_bot_manager.c').read_text()
        for name, handler in [('bot_kickall', 'BotKickAll'), ('bot_killall', 'BotKillAll')]:
            self.assertIn(f'Cmd_AddPCommand("{name}", {handler}, 80);', source)

    def test_command_and_death(self):
        fixture = r'''
#include <assert.h>
#include <stdarg.h>
#include <stdio.h>
#include <string.h>
typedef int qboolean;
#define qfalse 0
#define qtrue 1
#define NULL ((void *)0)
#define SESS_STATE_PLAYING 0
#define CS_ACTIVE 4
#define SS_GAME 2
#define NA_BOT 7
#define HITLOC_NONE 0
#define CON_CHANNEL_SERVER 0
typedef struct { struct {int sessionState;} sess; struct {int stats[1];} ps; } gameclient;
typedef struct { gameclient *client; int flags, health; } gentity_t;
typedef struct {int state; struct {struct {int type;} remoteAddress;} netchan; gentity_t *gentity;} client_t;
struct {int integer;} running={1}, maximum={4};
__typeof__(running) *com_sv_running=&running, *sv_maxclients=&maximum;
struct {int state, restarting;} sv={SS_GAME,0};
struct {client_t clients[4];} svs;
int argc=1, deaths, reported, fill_state=2, next_fill=123;
struct bgs_s {int unused;} level_bgs, *bgs;
int Cmd_Argc(void) {return argc;}
void Com_Printf(int channel, const char *fmt, ...) {
 va_list ap; va_start(ap,fmt);
 if (!strncmp(fmt,"Killed",6)) reported=va_arg(ap,int);
 va_end(ap);
}
void player_die(gentity_t *self,gentity_t *inflictor,gentity_t *attacker,
 int damage,int mod,int weapon,void *dir,int hit,int offset) {
 assert(self==attacker && self==inflictor && mod==12);
 assert(bgs==&level_bgs);
 assert(self->health==0 && self->client->ps.stats[0]==0);
 self->client->sess.sessionState=1; ++deaths;
}
'''
        fixture += body('src/g_cmds.c', 'qboolean G_AdminSuicide(')
        fixture += '\n' + body('src/sv_bot_manager.c', 'static void BotKillAll(')
        fixture += r'''
int main(void) {
 gameclient gc[4]={0}; gentity_t ent[4]={0};
 for(int i=0;i<4;++i) {
  gc[i].ps.stats[0]=100; ent[i]=(gentity_t){&gc[i],3,100};
  svs.clients[i]=(client_t){CS_ACTIVE,{{NA_BOT}},&ent[i]};
 }
 BotKillAll(); assert(reported==4 && deaths==4 && bgs==NULL);
 BotKillAll(); assert(reported==0 && deaths==4);
 /* A new round respawns existing connections, with one human and one dead bot. */
 for(int i=0;i<4;++i) {gc[i].sess.sessionState=0;gc[i].ps.stats[0]=ent[i].health=100;}
 svs.clients[0].netchan.remoteAddress.type=1;
 gc[1].sess.sessionState=1;
 BotKillAll(); assert(reported==2 && ent[0].health==100 && ent[1].health==100);
 assert(fill_state==2 && next_fill==123);
 for(int i=0;i<4;++i) assert(svs.clients[i].state==CS_ACTIVE);
 /* Transition guard, invalid usage, stopped server, and empty population. */
 sv.restarting=1; BotKillAll(); assert(reported==0);
 sv.restarting=0; argc=2; BotKillAll(); assert(deaths==6); argc=1;
 running.integer=0; BotKillAll(); assert(reported==0); running.integer=1;
 maximum.integer=0; BotKillAll(); assert(reported==0);
 assert(!G_AdminSuicide(NULL));
 return 0;
}
'''
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'test.c'
            source.write_text(fixture)
            binary = Path(directory) / 'test'
            subprocess.run(['cc', '-std=gnu11', str(source), '-o', str(binary)], check=True)
            subprocess.run([str(binary)], check=True)
