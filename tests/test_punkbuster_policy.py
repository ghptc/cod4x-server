import importlib.util
from pathlib import Path
import struct
import unittest

spec = importlib.util.spec_from_file_location('prepare', Path(__file__).parents[1] / 'tools/bots/prepare.py')
prepare = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prepare)


class WarningPolicy(unittest.TestCase):
    def test_changes_only_explicit_pb_warning_condition(self):
        condition = 'if(!getDvarInt("sv_punkbuster")&&!game["LAN_MODE"]&&!game["PROMOD_PB_OFF"])'
        source = 'forceDvar("sv_pure","1");' + condition + 'warn();checkIwds();checkHealth();'
        result = prepare.punkbuster_policy(source)
        self.assertEqual(result.replace('&&!getDvarInt("promod_allow_no_punkbuster")', ''), source)

    def test_rejects_unknown_or_ambiguous_source(self):
        with self.assertRaises(ValueError):
            prepare.punkbuster_policy('different version')

    def test_rawfile_validates_lengths_and_ambiguity(self):
        marker = b'\xff' * 4 + b'promod/servercheck.gsc\0'
        data = b'\xff' * 4 + struct.pack('<I', 3) + marker + b'abc\0'
        self.assertEqual(prepare.rawfile(data, 'promod/servercheck.gsc'), 'abc')
        for invalid in [data[:-1], data + data, data.replace(b'abc\0', b'abc!')]:
            with self.assertRaises(ValueError):
                prepare.rawfile(invalid, 'promod/servercheck.gsc')
