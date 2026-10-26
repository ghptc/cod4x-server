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
        source = ('if(level.players.size<1){continue;}'
                  'player.ready=false;player thread selfLoop();'
                  'player.oldready=player.update;humanRecordingChecks();'
                  'if(self useButtonPressed())self.ready=!self.ready;')
        result = prepare.bot_readyup(source)
        self.assertIn('if(!player.isbot)player thread selfLoop();', result)
        self.assertIn('player.pers["team"]=="allies"', result)
        self.assertIn('player.pers["team"]=="axis"', result)
        self.assertIn('isDefined(player.pers["class"])', result)
        self.assertIn('if(!player.ready){level.not_ready_count++;all_players_ready=false;}', result)
        for rule in ('if(level.players.size<1){continue;}', 'humanRecordingChecks();',
                     'if(self useButtonPressed())self.ready=!self.ready;'):
            self.assertIn(rule, result)
