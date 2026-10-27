"""Public adapter policy and fail-closed private-overlay regression tests."""
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import unittest
import zlib

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('allied_prepare', ROOT / 'tools/btd/prepare.py')
btd = importlib.util.module_from_spec(spec)
spec.loader.exec_module(btd)


def fastfile(sources):
    payload = b''
    for name, source in sources.items():
        raw = source.encode()
        payload += b'\0' * 4 + struct.pack('<I', len(raw)) + b'\xff' * 4 + name.encode() + b'\0' + raw + b'\0'
    return b'\0' * 12 + zlib.compress(payload)


class AlliedOverlayTests(unittest.TestCase):
    def fixture(self):
        sources = {
            btd.SCRIPT: 'init()\r\n{\r\n}\r\n' + btd.DEATH_CONDITION + '\r\n' + btd.PLAYER_DAMAGE_GUARD + '\r\n'
                'Callback_PlayerConnect()\r\n{}\r\nspawnPlayer()\r\n{}\r\n'
                'updateTeamStatus()\r\n{\r\nplayers = level.players;\r\n}\r\nisValidClass(x){}',
            btd.ALLIED_SURVIVAL_SCRIPT: ('players = getentarray("player","classname");\r\n' * 4),
            btd.ALLIED_AMMO_SCRIPT: btd.AMMO_PICKUP_GUARD + '\r\nammoingwait()\r\n{wait 0.75; self.isammoing=false;}\r\n'
                'hashadammo()\r\n{wait level.grace_time; self.hasntfullammo=true;}',
            btd.ALLIED_ZOMBIE_SCRIPT: 'other(){getentarray("player","classname");}\r\n'
                'monitorplayers()\r\n{\r\nplayers=getentarray("player","classname");\r\n}\r\nmonitorme(){}',
        }
        names = {btd.SCRIPT: 'death_callback_source_sha256',
                 btd.ALLIED_SURVIVAL_SCRIPT: 'allied_survival_source_sha256',
                 btd.ALLIED_ZOMBIE_SCRIPT: 'allied_zombie_source_sha256',
                 btd.ALLIED_AMMO_SCRIPT: 'allied_ammo_source_sha256'}
        lock = {names[name]: hashlib.sha256(source.encode()).hexdigest() for name, source in sources.items()}
        return sources, lock

    def test_human_accounting_preserves_zombie_combat(self):
        sources, lock = self.fixture()
        outputs = btd.allied_overlays(fastfile(sources), lock)
        global_source = outputs[btd.SCRIPT.replace('.gsc', '.gsx')].decode()
        self.assertIn(btd.SAFE_DEATH_CONDITION, global_source)
        self.assertIn(btd.PLAYER_DAMAGE_GUARD, global_source)
        self.assertIn('spawnPlayer()\r\n{\r\n self endon("disconnect");', global_source)
        self.assertIn('if (self.isbot) self.pers["isBot"] = true;', global_source)
        self.assertEqual(global_source.count('thread btd_allies::init();'), 1)
        self.assertIn('players = btd_allies::human_players();', global_source)
        survival = outputs[btd.ALLIED_SURVIVAL_SCRIPT.replace('.gsc', '.gsx')].decode()
        self.assertEqual(survival.count('btd_allies::human_players()'), 4)
        zombie = outputs[btd.ALLIED_ZOMBIE_SCRIPT.replace('.gsc', '.gsx')].decode()
        self.assertIn('other(){getentarray("player","classname");}', zombie)
        self.assertIn('players=btd_allies::human_players();', zombie)
        self.assertEqual(outputs['btd_allies.gsx'], (ROOT / 'bots/btd_allies.gsc').read_bytes())

    def test_ammo_cooldowns_cancel_before_their_waits(self):
        sources, lock = self.fixture()
        outputs = btd.allied_overlays(fastfile(sources), lock)
        ammo = outputs[btd.ALLIED_AMMO_SCRIPT.replace('.gsc', '.gsx')].decode()
        self.assertEqual(ammo.count('self endon("disconnect");'), 2)
        self.assertEqual(ammo.replace('\r\n self endon("disconnect");', '').replace(btd.AMMO_FIRST_USE, ''), sources[btd.ALLIED_AMMO_SCRIPT])
        self.assertEqual(ammo.count(btd.AMMO_FIRST_USE), 1)
        self.assertIn(btd.AMMO_PICKUP_GUARD + btd.AMMO_FIRST_USE, ammo)
        self.assertIn('ammoingwait()\r\n{\r\n self endon("disconnect");wait 0.75;', ammo)
        self.assertIn('hashadammo()\r\n{\r\n self endon("disconnect");wait level.grace_time;', ammo)

    def test_unpinned_ammo_source_rejected(self):
        sources, lock = self.fixture()
        sources[btd.ALLIED_AMMO_SCRIPT] += '// changed'
        with self.assertRaisesRegex(ValueError, 'hash mismatch'):
            btd.allied_overlays(fastfile(sources), lock)

    def test_missing_vendor_human_damage_guard_rejected(self):
        sources, lock = self.fixture()
        sources[btd.SCRIPT] = sources[btd.SCRIPT].replace(btd.PLAYER_DAMAGE_GUARD, '')
        lock['death_callback_source_sha256'] = hashlib.sha256(sources[btd.SCRIPT].encode()).hexdigest()
        with self.assertRaisesRegex(ValueError, 'player damage protection'):
            btd.allied_overlays(fastfile(sources), lock)

    def test_unpinned_source_rejected(self):
        sources, lock = self.fixture()
        sources[btd.ALLIED_ZOMBIE_SCRIPT] += '\nchanged'
        with self.assertRaisesRegex(ValueError, 'hash mismatch'):
            btd.allied_overlays(fastfile(sources), lock)

    def test_changed_anchor_rejected_even_with_new_hash(self):
        sources, lock = self.fixture()
        sources[btd.ALLIED_SURVIVAL_SCRIPT] += 'getentarray("player","classname")'
        lock['allied_survival_source_sha256'] = hashlib.sha256(sources[btd.ALLIED_SURVIVAL_SCRIPT].encode()).hexdigest()
        with self.assertRaisesRegex(ValueError, 'integration anchor'):
            btd.allied_overlays(fastfile(sources), lock)

    def test_production_adapter_has_no_damage_or_ammunition_shortcut(self):
        source = (ROOT / 'bots/btd_allies.gsc').read_text()
        for forbidden in ('notify("damage"', 'suicide(', 'givemaxammo(', 'giveweapon(', 'setorigin('):
            self.assertNotIn(forbidden, source.lower())
        self.assertIn('if (!players[i].isbot)', source)
        self.assertIn('getentarray("zom", "targetname")', source)
        self.assertNotIn('level.waypoints =', source)
        self.assertNotIn('level.waypointcount =', source)


if __name__ == '__main__':
    unittest.main()
