import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('prepare', Path(__file__).parents[1] / 'tools/bots/prepare.py')
prepare = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prepare)


class MapVotePolicy(unittest.TestCase):
    def test_only_removes_competition_vote_prohibition(self):
        source = 'main(){setDvar("g_allowVote",0);setDvar("sv_pure",1);matchRules();}'
        result = prepare.map_vote_policy(source)
        self.assertEqual(result, 'main(){setDvar("sv_pure",1);matchRules();}')

    def test_unknown_or_ambiguous_version_rejected(self):
        for source in ['', 'setDvar("g_allowVote",1);', 'setDvar("g_allowVote",0);' * 2]:
            with self.assertRaises(ValueError):
                prepare.map_vote_policy(source)
