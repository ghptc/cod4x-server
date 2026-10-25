import importlib.util
from pathlib import Path
import re
import unittest

spec = importlib.util.spec_from_file_location('prepare', Path(__file__).parents[1] / 'tools/bots/prepare.py')
prepare = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prepare)


class AdminRules(unittest.TestCase):
    def test_original_defaults_and_unrelated_rules_are_preserved(self):
        names = ['scr_sd_timelimit', 'scr_sd_roundlimit', 'scr_sd_scorelimit',
                 'scr_sd_roundswitch', 'scr_team_fftype', 'sv_voice']
        source = 'main(){\n' + '\n'.join('setDvar( "' + name + '", 1 );' for name in names) + '\ncheckIntegrity();\n}'
        changed = prepare.admin_rules(source)
        for name in names:
            self.assertIn('setDvar( "' + name + '", 1 );', changed)
            self.assertIn('getDvar("cod4x_rule_' + name + '") != ""', changed)
            self.assertIn('getDvarFloat("cod4x_rule_' + name + '") >= 0', changed)
        self.assertEqual(changed.count('getDvarInt("sv_promod_admin")'), 6)
        self.assertIn('checkIntegrity();', changed)

    def test_unknown_or_ambiguous_rulesets_fail_closed(self):
        with self.assertRaises(ValueError): prepare.admin_rules('another mod')
