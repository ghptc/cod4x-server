"""Private BTD preparation fixtures contain no third-party assets."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import hashlib
import struct
import zlib

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
        self.raw = ('fixture() { if(' + btd.DEATH_CONDITION + ') return true; }').encode()
        marker = b'\xff' * 4 + btd.SCRIPT.encode() + b'\0'
        payload = b'fixture!' + struct.pack('<I', len(self.raw)) + marker + self.raw + b'\0'
        self.spawn_raw = ('init() { ' + btd.SPAWN_ORIGIN + ' }').encode()
        payload += struct.pack('<I', len(self.spawn_raw)) + b'\xff'*4 + btd.SPAWN_SCRIPT.encode() + b'\0' + self.spawn_raw + b'\0'
        self.navigation_raw = ('loader() {\r\n' + btd.NAVIGATION_END_CHECK + '\r\n return; }').encode()
        payload += struct.pack('<I', len(self.navigation_raw)) + b'\xff'*4 + btd.NAVIGATION_SCRIPT.encode() + b'\0' + self.navigation_raw + b'\0'
        self.ammo_raw = (btd.AMMO_PICKUP_GUARD + '\r\nammoingwait()\r\n{}\r\nhashadammo()\r\n{}').encode()
        payload += struct.pack('<I', len(self.ammo_raw)) + b'\xff'*4 + btd.ALLIED_AMMO_SCRIPT.encode() + b'\0' + self.ammo_raw + b'\0'
        self.fastfile = b'fixture-head' + zlib.compress(payload)
        (mod / 'mod.ff').write_bytes(self.fastfile)
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
            {'files': hashes, 'default_cfgs': ['btd_settings.cfg'],
             'death_callback_source_sha256': hashlib.sha256(self.raw).hexdigest(),
             'spawn_points_source_sha256': hashlib.sha256(self.spawn_raw).hexdigest(),
             'navigation_source_sha256': hashlib.sha256(self.navigation_raw).hexdigest(),
             'allied_ammo_source_sha256': hashlib.sha256(self.ammo_raw).hexdigest()}))
        (self.root / 'bots/dependencies.json').write_text(json.dumps(
            {'integrity_headers': {p.name: btd.digest(p) for p in self.headers.iterdir()}}))
        self.output = self.root / 'runtime'

    def prepare(self):
        return btd.prepare(self.source, self.headers, self.binary, self.output)

    def test_optional_allied_manifest_and_overlay_hashes(self):
        sources = {
            btd.SCRIPT: ('init()\r\n{}\r\nCallback_PlayerConnect()\r\n{}\r\nspawnPlayer()\r\n{}\r\n' +
                         btd.DEATH_CONDITION + '\r\n' + btd.PLAYER_DAMAGE_GUARD + '\r\nupdateTeamStatus()\r\n{players = level.players;}\r\nisValidClass(x){}').encode(),
            btd.SPAWN_SCRIPT: self.spawn_raw,
            btd.NAVIGATION_SCRIPT: self.navigation_raw,
            btd.ALLIED_SURVIVAL_SCRIPT: b'getentarray("player","classname");' * 4,
            btd.ALLIED_AMMO_SCRIPT: btd.AMMO_PICKUP_GUARD.encode() + b'\r\nammoingwait()\r\n{}\r\nhashadammo()\r\n{}',
            btd.ALLIED_ZOMBIE_SCRIPT: b'monitorplayers()\r\n{getentarray("player","classname");}\r\nmonitorme(){}',
        }
        payload = b'fixture!'
        for name, raw in sources.items():
            payload += struct.pack('<I', len(raw)) + b'\xff' * 4 + name.encode() + b'\0' + raw + b'\0'
        (self.source / 'btd_alpha_001/mod.ff').write_bytes(b'fixture-head' + zlib.compress(payload))
        lock_path = self.root / 'tools/btd/dependencies.json'
        lock = json.loads(lock_path.read_text())
        lock['files']['btd_alpha_001/mod.ff'] = btd.digest(self.source / 'btd_alpha_001/mod.ff')
        for script, key in [(btd.SCRIPT, 'death_callback_source_sha256'),
                            (btd.ALLIED_SURVIVAL_SCRIPT, 'allied_survival_source_sha256'),
                            (btd.ALLIED_ZOMBIE_SCRIPT, 'allied_zombie_source_sha256'),
                            (btd.ALLIED_AMMO_SCRIPT, 'allied_ammo_source_sha256')]:
            lock[key] = hashlib.sha256(sources[script]).hexdigest()
        lock_path.write_text(json.dumps(lock))
        (self.root / 'bots/btd_allies.gsc').write_text('// synthetic authored adapter')
        record = btd.prepare(self.source, self.headers, self.binary, self.output, allies=True)
        ammo_name = btd.ALLIED_AMMO_SCRIPT.replace('.gsc', '.gsx')
        baseline_output = self.root / 'baseline-runtime'
        baseline = btd.prepare(self.source, self.headers, self.binary, baseline_output)
        self.assertEqual((self.output / 'mods/btd_alpha_001' / ammo_name).read_bytes(),
                         (baseline_output / 'mods/btd_alpha_001' / ammo_name).read_bytes())
        self.assertEqual(record['overlays'][ammo_name], baseline['overlays'][ammo_name])
        self.assertNotIn('allied_bots', baseline)
        self.assertIs(record['allied_bots'], True)
        self.assertEqual(len(record['overlays']), 7)
        self.assertEqual(record['allied_zombie_source_sha256'], lock['allied_zombie_source_sha256'])
        for name, expected in record['overlays'].items():
            self.assertEqual(btd.digest(self.output / 'mods/btd_alpha_001' / name), expected)

    def test_original_assets_not_modified_or_decompiled(self):
        record = self.prepare()
        self.assertEqual(record['maps'], ['mp_crash', 'mp_killhouse'])
        self.assertEqual((self.output / 'mods/btd_alpha_001/btd_maprotation.cfg').read_bytes(),
                         (self.source / 'btd_alpha_001/btd_maprotation.cfg').read_bytes())
        self.assertEqual(record['asset_type'], 'btd-alpha-001')
        self.assertEqual((self.output / 'mods/btd_alpha_001/mod.ff').read_bytes(), self.fastfile)
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

    def test_only_missing_field_guard_changes(self):
        record = self.prepare()
        overlay = self.output / 'mods/btd_alpha_001/maps/mp/gametypes/_globallogic.gsx'
        self.assertEqual(overlay.read_bytes(), self.raw.replace(
            btd.DEATH_CONDITION.encode(), btd.SAFE_DEATH_CONDITION.encode()))
        self.assertEqual(record['overlays'][str(overlay.relative_to(self.output / 'mods/btd_alpha_001'))],
                         hashlib.sha256(overlay.read_bytes()).hexdigest())

    def test_unpinned_source_rejected(self):
        with self.assertRaisesRegex(ValueError, 'source hash mismatch'):
            btd.death_overlay(self.fastfile, '0' * 64)

    def test_unexpected_condition_rejected(self):
        raw = self.raw.replace(b'eInflictor.targetname', b'eInflictor.otherfield')
        marker = b'\xff' * 4 + btd.SCRIPT.encode() + b'\0'
        ff = b'fixture-head' + zlib.compress(b'fixture!' + struct.pack('<I', len(raw)) + marker + raw + b'\0')
        with self.assertRaisesRegex(ValueError, 'condition'):
            btd.death_overlay(ff, hashlib.sha256(raw).hexdigest())

    def test_spawn_points_receive_native_vector_angles(self):
        self.prepare()
        overlay = self.output / 'mods/btd_alpha_001' / btd.SPAWN_SCRIPT.replace('.gsc', '.gsx')
        self.assertEqual(overlay.read_bytes(), self.spawn_raw.replace(
            btd.SPAWN_ORIGIN.encode(), (btd.SPAWN_ORIGIN+' temp.angles = (0, 0, 0);').encode()))


    def test_only_pinned_killhouse_terminal_check_changes(self):
        record = self.prepare()
        path = self.output / 'mods/btd_alpha_001' / btd.NAVIGATION_SCRIPT.replace('.gsc', '.gsx')
        expected = self.navigation_raw.replace(btd.NAVIGATION_END_CHECK.encode(),
            (btd.KILLHOUSE_TERMINATOR_REPAIR + btd.NAVIGATION_END_CHECK).encode())
        self.assertEqual(path.read_bytes(), expected)
        self.assertEqual(record['overlays'][str(path.relative_to(self.output / 'mods/btd_alpha_001'))],
                         hashlib.sha256(expected).hexdigest())
        self.assertEqual(record['navigation_source_sha256'], hashlib.sha256(self.navigation_raw).hexdigest())
        self.assertEqual(len(record['overlays']), 4)

    def test_unpinned_navigation_blocks_map_declaration(self):
        lock_path = self.root / 'tools/btd/dependencies.json'
        lock = json.loads(lock_path.read_text())
        lock['navigation_source_sha256'] = '0' * 64
        lock_path.write_text(json.dumps(lock))
        with self.assertRaisesRegex(ValueError, 'source hash mismatch'):
            self.prepare()
        self.assertFalse(self.output.exists())

    def test_unpinned_navigation_rejected(self):
        with self.assertRaisesRegex(ValueError, 'source hash mismatch'):
            btd.navigation_overlay(self.fastfile, '0' * 64)

    def test_missing_or_ambiguous_navigation_guard_rejected(self):
        for raw in [b'loader() {}', self.navigation_raw * 2]:
            marker = b'\xff'*4 + btd.NAVIGATION_SCRIPT.encode() + b'\0'
            ff = b'fixture-head' + zlib.compress(b'fixture!' + struct.pack('<I', len(raw)) + marker + raw + b'\0')
            with self.assertRaisesRegex(ValueError, 'termination check'):
                btd.navigation_overlay(ff, hashlib.sha256(raw).hexdigest())

    def test_navigation_preserves_non_utf8_comments(self):
        raw = b'// vendor comment \x93quoted\x94\r\n' + self.navigation_raw
        marker = b'\xff'*4 + btd.NAVIGATION_SCRIPT.encode() + b'\0'
        ff = b'fixture-head' + zlib.compress(b'fixture!' + struct.pack('<I', len(raw)) + marker + raw + b'\0')
        overlay = btd.navigation_overlay(ff, hashlib.sha256(raw).hexdigest())
        self.assertEqual(overlay.replace(btd.KILLHOUSE_TERMINATOR_REPAIR.encode(), b''), raw)

    def test_baseline_includes_first_pickup_and_disconnect_safety(self):
        record = self.prepare()
        name = btd.ALLIED_AMMO_SCRIPT.replace('.gsc', '.gsx')
        data = (self.output / 'mods/btd_alpha_001' / name).read_bytes()
        self.assertIn(btd.AMMO_FIRST_USE.encode(), data)
        self.assertEqual(data.count(b'self endon("disconnect");'), 2)
        self.assertEqual(record['overlays'][name], hashlib.sha256(data).hexdigest())
        self.assertNotIn('allied_bots', record)

    def test_unpinned_baseline_ammo_rejected_before_output(self):
        path = self.root / 'tools/btd/dependencies.json'
        lock = json.loads(path.read_text())
        lock['allied_ammo_source_sha256'] = '0' * 64
        path.write_text(json.dumps(lock))
        with self.assertRaisesRegex(ValueError, 'source hash mismatch'):
            self.prepare()
        self.assertFalse(self.output.exists())
