import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('prepare', Path(__file__).parents[1] / 'tools/bots/prepare.py')
prepare = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prepare)


class GameplayPolicy(unittest.TestCase):
    def test_unknown_and_ambiguous_policies_fail_closed(self):
        for transform in [prepare.human_class_limits, prepare.match_end_rotation, prepare.bot_readyup]:
            with self.assertRaises(ValueError):
                transform('unknown version')
        with self.assertRaises(ValueError):
            prepare.replace_once('xx', 'x', 'y')

    def test_only_terminal_match_restart_changes(self):
        terminal = 'if(isDefined(game["PROMOD_MATCH_MODE"])&&game["PROMOD_MATCH_MODE"]=="match"){map_restart(false);return;}exitLevel(false);'
        source = 'map_restart(true);otherRoundRules();' + terminal
        result = prepare.match_end_rotation(source)
        self.assertEqual(result.replace('&&!getDvarInt("promod_auto_maprotate")', ''), source)
        self.assertIn('map_restart(true);otherRoundRules();', result)

    def test_readyup_preserves_human_and_minimum_player_rules(self):
        source = ('previous_not_ready_count=0;level.not_ready_count=0;'
                  'if(level.players.size<1){continue;}'
                  'if(!isDefined(player.looped)){player.ready=false;player thread selfLoop();}'
                  'player.oldready=player.update;humanRecordingChecks();'
                  'if(all_players_ready)level.ready_up_over=true;'
                  'lastPlayerReady(){if(level.players.size>1&&level.players.size>1){'
                  'player=level.players[i];originalReminder();}}'
                  'if(self useButtonPressed())self.ready=!self.ready;'
                  'originalCountdown();map_restart(true);')
        result = prepare.bot_readyup(source)
        self.assertIn('if(!player humanReadyEligible())', result)
        self.assertIn('!self.isbot', result)
        self.assertIn('self.pers["team"]=="allies"', result)
        self.assertIn('self.pers["team"]=="axis"', result)
        self.assertIn('all_players_ready&&level.readyup_humans>0', result)
        self.assertNotIn('level.players.size>1', result)
        self.assertIn('player.readyup_team=undefined', result)
        for rule in ('if(level.players.size<1){continue;}', 'humanRecordingChecks();',
                     'originalCountdown();map_restart(true);', 'originalReminder();'):
            self.assertIn(rule, result)
        with self.assertRaises(ValueError):
            prepare.bot_readyup(source + 'level.not_ready_count=0;')
