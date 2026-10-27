"""Execute native BTD mode selection against engine state fixtures."""
from pathlib import Path
import subprocess
import tempfile
import unittest
from test_bot_killall import body

ROOT = Path(__file__).resolve().parents[1]


class AlliedManager(unittest.TestCase):
    def test_mode_readiness_and_limits(self):
        fixture = r'''
#include <assert.h>
#include <string.h>
typedef int qboolean;
#define SS_GAME 2
typedef struct {int boolean,integer;const char *string;} cvar_t;
cvar_t enabled={1},ready={1},running={1,1},pure={1},btd={1},
       fill={0,12},allied_fill={0,5},game={0,0,"war"},dir={0,0,"mods/btd_alpha_001"};
cvar_t *bot_enable=&enabled,*bot_ai_ready=&ready,*com_sv_running=&running,
       *sv_pure=&pure,*btd_allies_enable=&btd,*bot_fill_limit=&fill,
       *btd_allies_limit=&allied_fill,*sv_g_gametype=&game,*fs_gameDirVar=&dir;
struct {int state,restarting;} sv={SS_GAME,0};
'''
        for signature in ('static qboolean BotAlliedMode(', 'static int BotLimitValue(',
                          'static qboolean BotCanAdd('):
            fixture += body('src/sv_bot_manager.c', signature) + '\n'
        fixture += r'''
int main(void) {
 assert(BotAlliedMode() && BotCanAdd() && BotLimitValue()==5);
 enabled.boolean=0; assert(BotCanAdd());
 btd.boolean=0; assert(BotAlliedMode() && !BotCanAdd() && BotLimitValue()==5);
 btd.boolean=1;ready.boolean=0;assert(!BotCanAdd());ready.boolean=1;
 pure.boolean=0;assert(!BotCanAdd());pure.boolean=1;
 sv.restarting=1;assert(!BotCanAdd());sv.restarting=0;
 game.string="sd";dir.string="mods/pml220";
 assert(!BotAlliedMode() && !BotCanAdd() && BotLimitValue()==12);
 enabled.boolean=1;assert(BotCanAdd());
 game.string="war";assert(!BotCanAdd());
 dir.string="mods/other";assert(!BotCanAdd());
 return 0;
}
'''
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'manager.c'
            binary = Path(directory) / 'manager'
            source.write_text(fixture)
            subprocess.run(['cc', str(source), '-o', str(binary)], check=True)
            subprocess.run([str(binary)], check=True)

    def test_contract_permissions(self):
        source = (ROOT / 'src/sv_bot_manager.c').read_text()
        for command, handler, power in [('bot_add','BotAdd',80),('bot_kick','BotKick',80),
             ('bot_kickall','BotKickAll',80),('bot_killall','BotKillAll',80),('bot_status','BotStatus',20)]:
            self.assertIn(f'Cmd_AddPCommand("{command}", {handler}, {power});', source)
