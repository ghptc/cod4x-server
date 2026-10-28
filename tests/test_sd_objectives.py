"""Fail-closed native overlay changes; runtime evidence uses run_sd_native.py."""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('prepare_sd', ROOT / 'tools/bots/prepare.py')
prepare = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prepare)


class SDObjectives(unittest.TestCase):
    def test_only_publishes_existing_native_object(self):
        source = 'originalOwnership();defuseObject.label=label;originalCallbacksAndTimers();'
        result = prepare.publish_defuse_object(source)
        self.assertEqual(result.replace('level.defuseObject=defuseObject;', ''), source)
        for bad in ('unknown_revision', source + source):
            with self.assertRaises(ValueError): prepare.publish_defuse_object(bad)

    def test_unknown_objective_source_cannot_prepare(self):
        with self.assertRaises(ValueError): prepare.sd_objective_source('unknown_revision')

    def test_derivation_removes_hidden_information_and_retries_another_site(self):
        # Minimal original interfaces, no licensed gameplay source in this fixture.
        helpers = ['BotRandomStance', 'bot_inc_bots', 'bot_get_obj', 'bot_go_plant',
                   'bot_go_defuse', 'bot_array_nearest_curorigin', 'bot_sd_defenders',
                   'bot_sd_attackers']
        script = '\n'.join(name + '(){}' for name in helpers)
        script += '\nbot_escort_obj(){if(carrier == obj.carrier)return;}\n'
        script += ('bot_sd_defenders_loop(data){\n'
            '\t\ttimeleft = stockTimer();\n\t\t// check for a bomb carrier\n'
            '\t\thiddenDroppedBombPosition();\n\t\t// pick a site to protect\n'
            '\t\tif ( site isInUse() ) { hiddenEnemyPlant(); }\n'
            '\t\t// else hang around the site\npublicSites();}\n')
        script += ('bot_sd_attackers_loop(data){\n'
            '\t\tif ( site isInUse() ) { hiddenEnemyDefuse(); }\n'
            '\t\t// else hang around the site\npublicPlantedBomb();\n'
            '\t// check if to plant\nstockRandomDelay();\n'
            '\tif ( !isdefined( level.bombzones ) )return;\n'
            'sites[ sites.size ] = level.bombzones[ i ];\n'
            'if ( !sites.size )\n\t{\n\t\treturn;\n\t}\n'
            'event = self waittill_any_return( "goal", "bad_path", "new_goal" );\n'
            'self isBombCarrier();\nself bot_wait_stop_move();\n'
            'self thread BotPressUse( waitTime );\n\twait waitTime;\n}\n')
        result = prepare.sd_objective_source(script)
        for hidden in ('hiddenDroppedBombPosition', 'hiddenEnemyPlant', 'hiddenEnemyDefuse', 'stockRandomDelay'):
            self.assertNotIn(hidden, result)
        for required in ('publicSites()', 'publicPlantedBomb()', 'data.failed_site = plant',
                         'self carries_bomb()', 'self hold_objective_use( waitTime )'):
            self.assertIn(required, result)
