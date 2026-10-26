import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('prepare', Path(__file__).parents[1] / 'tools/bots/prepare.py')
prepare = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prepare)


class GameplayPolicy(unittest.TestCase):
    def test_unknown_and_ambiguous_policies_fail_closed(self):
        for transform in [prepare.human_class_limits, prepare.match_end_rotation]:
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
