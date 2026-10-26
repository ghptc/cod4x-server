"""Private BTD preparation fixtures contain no third-party assets."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('btd_prepare', ROOT / 'tools/btd/prepare.py')
btd = importlib.util.module_from_spec(spec)
spec.loader.exec_module(btd)


class BtdPreparation(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        original = btd.ROOT
        self.addCleanup(setattr, btd, 'ROOT', original)
        btd.ROOT = self.root
        self.source = self.root / 'source'
        mod = self.source / 'btd_alpha_001'
        mod.mkdir(parents=True)
        for name in ('mod.ff', 'btd_images.iwd', 'btd_music.iwd', 'btd_weapons.iwd', 'btd_settings.cfg'):
            (mod / name).write_bytes(b'original fixture')
        (mod / 'server.cfg').write_text('unsafe sample must not be packaged')
        (mod / 'btd_maprotation.cfg').write_text('set sv_mapRotation "gametype war map mp_crash"\n')
        (self.source / 'readme.txt').write_text('retain original notice')
        self.headers = self.root / 'headers'
        self.headers.mkdir()
        for name in ['jcod4x_00.dat'] + [f'localized_english_iw{i:02}.dat' for i in range(7)]:
            (self.headers / name).write_bytes(b'header fixture')
        self.binary = self.root / 'engine'
        self.binary.write_bytes(b'engine fixture')
        (self.root / 'tools/btd').mkdir(parents=True)
        (self.root / 'bots').mkdir()
        hashes = {str(p.relative_to(self.source)): btd.digest(p) for p in self.source.rglob('*') if p.is_file()}
        (self.root / 'tools/btd/dependencies.json').write_text(json.dumps(
            {'files': hashes, 'default_cfgs': ['btd_settings.cfg']}))
        (self.root / 'bots/dependencies.json').write_text(json.dumps(
            {'integrity_headers': {p.name: btd.digest(p) for p in self.headers.iterdir()}}))
        self.output = self.root / 'runtime'

    def prepare(self):
        return btd.prepare(self.source, self.headers, self.binary, self.output)

    def test_original_assets_not_modified_or_decompiled(self):
        record = self.prepare()
        self.assertEqual(record['maps'], ['mp_crash'])
        self.assertEqual(record['asset_type'], 'btd-alpha-001')
        self.assertEqual((self.output / 'mods/btd_alpha_001/mod.ff').read_bytes(), b'original fixture')
        self.assertFalse((self.output / 'mods/btd_alpha_001/server.cfg').exists())
        self.assertEqual((self.output / 'licenses/Before-the-Dawn-readme.txt').read_text(), 'retain original notice')
        self.assertNotIn('server.cfg', record['assets'])
        self.assertEqual(len(record['headers']), 8)
        with self.assertRaises(ValueError):
            self.prepare()

    def test_tampered_input_rejected_before_output(self):
        (self.source / 'btd_alpha_001/mod.ff').write_bytes(b'tampered')
        with self.assertRaisesRegex(ValueError, 'hash mismatch'):
            self.prepare()
        self.assertFalse(self.output.exists())

    def test_symlink_input_rejected(self):
        path = self.source / 'btd_alpha_001/mod.ff'
        data = path.read_bytes()
        path.unlink()
        (self.root / 'other').write_bytes(data)
        path.symlink_to(self.root / 'other')
        with self.assertRaises(ValueError):
            self.prepare()
        self.assertFalse(self.output.exists())
