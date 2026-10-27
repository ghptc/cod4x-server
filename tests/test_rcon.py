#!/usr/bin/env python3
"""Compile real RCON/parser functions with isolated engine boundaries; no game assets."""
from pathlib import Path
import os
import hashlib
import socket
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


def function(file, signature):
    source = (ROOT / file).read_text()
    start = source.index(signature)
    brace = source.index("{", start)
    # Functions here have balanced braces in comments/string literals as well.
    depth = 1
    end = brace + 1
    while depth:
        depth += (source[end] == "{") - (source[end] == "}")
        end += 1
    return source[start:end] + "\n"


class Rcon(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workspace = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.workspace.cleanup)
        path = Path(cls.workspace.name)
        pieces = [(ROOT / 'tests/rcon_harness.c').read_text()]
        for file, signature in [
            ('src/sv_mode_bridge.c', 'qboolean SV_RconModeFraming('),
            ('src/sv_mode_bridge.c', 'qboolean SV_RconModeCommand('),
            ('src/msg.c', 'char *MSG_ReadStringLine('),
            ('src/cmd.c', 'static void Cmd_TokenizeStringInternal('),
            ('src/cvar.c', 'static int Cvar_SetVariant( cvar_t *var, CvarValue value ,qboolean force ) {'),
            ('src/cvar.c', 'void Cvar_Set_f( void ) {'),
            ('src/sv_main.c', '__optimize3 __regparm2 static void SVC_RemoteCommand('),
            ('src/hl2rcon.c', 'qboolean HL2Rcon_SourceRconAuth('),
        ]:
            pieces.append(function(file, signature))
        pieces.append((ROOT / 'tests/rcon_harness_main.c').read_text())
        harness = path / 'rcon.c'
        harness.write_text('\n'.join(pieces))
        cls.binary = path / 'rcon'
        subprocess.run(['cc', '-std=gnu11', '-Wno-attributes', '-I', str(ROOT / 'src'),
                        str(harness), '-o', str(cls.binary)], check=True)

    def udp(self, length, quoted=False, wrong=False, command='status', packet=None):
        password = ('Ab9' * 400)[:length]
        with tempfile.TemporaryDirectory() as directory:
            cfg = Path(directory) / 'server.cfg'
            cfg.write_text('set rcon_password "' + password + '"\n')
            process = subprocess.Popen([str(self.binary), str(cfg)], stdout=subprocess.PIPE,
                                       stderr=subprocess.PIPE, text=True)
            try:
                port = int(process.stdout.readline())
                with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as client:
                    client.settimeout(3)
                    supplied = 'Z' * length if wrong else password
                    if quoted:
                        supplied = '"' + supplied + '"'
                    client.sendto(packet if packet is not None else b'\xff' * 4 + f'rcon {supplied} {command}\0'.encode(),
                                  ('127.0.0.1', port))
                    response = client.recv(4096)
                output, error = process.communicate(timeout=3)
                self.assertEqual(process.returncode, 0, error)
                self.assertEqual(output.strip(), f'cfg_length={length} cfg_equal=1')
                return response
            finally:
                if process.poll() is None:
                    process.kill()
                process.communicate()

    def test_mode_ingress_requires_authentication_and_complete_wire_frame(self):
        self.assertEqual(self.udp(16, command='change_mode promod'), b'INGRESS_ALLOWED')
        self.assertEqual(self.udp(16, wrong=True, command='change_mode promod'), b'Bad rcon')
        self.assertIn(b'shorter than 8', self.udp(7, command='change_mode promod'))
        password = ('Ab9' * 400)[:16]
        for suffix in (b'\nquit', b'\0quit', b'\rquit'):
            packet = b'\xff' * 4 + f'rcon {password} change_mode promod'.encode() + suffix
            self.assertEqual(self.udp(16, packet=packet), b'INGRESS_INVALID')

    def test_source_identity_uses_verified_record_not_numeric_name(self):
        result=subprocess.run([str(self.binary),'--source-bound',
            '76561198000000999 SyntheticAccountPassword'],text=True,capture_output=True,check=True)
        self.assertIn('source_bound_to_verified_record=1 steamid=42',result.stdout)

    def test_mode_request_logs_omit_untrusted_arguments(self):
        self.assertEqual(self.udp(16,command='change_mode promod MODE_SECRET_CANARY'),b'INGRESS_ALLOWED')

    def test_source_zero_account_cannot_impersonate_master_console(self):
        rejected=subprocess.run([str(self.binary),'--source-zero','console SyntheticAccountPassword'],
                                text=True,capture_output=True,check=True)
        self.assertIn('source_rejected=1',rejected.stdout)
        master=subprocess.run([str(self.binary),'--source-console','SyntheticServerPassword'],
                              text=True,capture_output=True,check=True)
        self.assertIn('source_master_console_authenticated=1',master.stdout)

    def test_udp_lengths_and_quotes(self):
        for length in (16, 23, 24, 28, 29, 32, 48, 64):
            for quoted in (False, True):
                with self.subTest(length=length, quoted=quoted):
                    self.assertEqual(self.udp(length, quoted), b'EXECUTED:status')

    def test_wrong_password_and_minimum(self):
        self.assertEqual(self.udp(48, wrong=True), b'Bad rcon')
        self.assertIn(b'shorter than 8', self.udp(7))
        self.assertEqual(self.udp(8), b'EXECUTED:status')

    def test_complete_command_boundary(self):
        # The 1024-byte read buffer holds 1023 bytes, excluding the OOB marker.
        self.assertEqual(self.udp(1016, command='x'), b'EXECUTED:x')
        self.assertEqual(self.udp(1017, command='x'), b'EXECUTED:x')
        self.assertEqual(self.udp(1018, command='x'), b'EXECUTED:x')
        self.assertEqual(self.udp(1019, command='x'), b'Bad rcon')

    @unittest.skipUnless(os.environ.get('COD4X_CLIENT_SOURCE'), 'optional public client checkout')
    def test_public_client_serialization(self):
        source = Path(os.environ['COD4X_CLIENT_SOURCE']) / 'src/cl_main.c'
        revision = subprocess.check_output(['git', '-C', str(source.parents[1]),
                                            'rev-parse', 'HEAD'], text=True).strip()
        self.assertEqual(revision, '17182c7bf04b859dea5c0db4acdb0b83c28d6dd2')
        # Require the tracked source bytes, as well as the checkout revision.
        tracked = subprocess.check_output(['git', '-C', str(source.parents[1]),
                                           'show', 'HEAD:src/cl_main.c'])
        self.assertEqual(hashlib.sha256(source.read_bytes()).digest(), hashlib.sha256(tracked).digest())
        text = source.read_text()
        start = text.index('void CL_Rcon_f( void ) {')
        end = text.index('/*', start)
        harness = Path(self.workspace.name) / 'client.c'
        harness.write_text((ROOT / 'tests/rcon_client_harness.c').read_text() + text[start:end])
        binary = harness.with_suffix('')
        subprocess.run(['cc', str(harness), '-o', str(binary)], check=True)
        for length in (16, 23, 24, 28, 29, 32, 48, 64):
            with self.subTest(length=length):
                packet = subprocess.check_output([str(binary), str(length)])
                expected = b'EXECUTED:status' if length <= 28 else b'Bad rcon'
                self.assertEqual(self.udp(length, packet=packet), expected)

    def test_source_rejection_redacts_entire_login(self):
        for login in ('DisposableRejectedSecret48', 'DisposableUser DisposablePassword'):
            result = subprocess.run([str(self.binary), '--source', login],
                                    capture_output=True, text=True, check=True)
            self.assertEqual(result.stdout, 'source_rejected=1 response_id=-1 ban_seconds=20 redacted=1\n')


if __name__ == '__main__':
    unittest.main()
