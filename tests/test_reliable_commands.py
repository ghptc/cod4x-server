"""Native command-ring and download characterization, without proprietary assets.

Compiles unchanged production functions with real engine types/message writers.
Filesystem and reliable-transport boundaries are deterministic fixtures. These
tests do not claim a real-client reproduction, gameplay, or network throughput.
Acknowledgments are assigned directly; the network ACK parser and the client's
receive/CGame rings are not exercised. Advancing svs.time tests the serializers,
not real frame callbacks or a sleeping graphical client. The gamestate boundary
only verifies completion-handler ordering, not gamestate payload delivery.
"""
from pathlib import Path
import subprocess
import tempfile
import unittest
from test_rcon import function

ROOT = Path(__file__).resolve().parents[1]


class ReliableCommands(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory(prefix='cod4-reliable-')
        cls.addClassCleanup(cls.directory.cleanup)
        path = Path(cls.directory.name)
        source = (ROOT / 'tests/reliable_commands_harness.c').read_text()
        for file, signature in [
            ('src/msg.c', 'void MSG_Init('),
            ('src/msg.c', 'void MSG_Clear('),
            ('src/msg.c', 'void MSG_WriteByte('),
            ('src/msg.c', 'void MSG_WriteShort('),
            ('src/msg.c', 'void MSG_WriteLong('),
            ('src/msg.c', 'void MSG_WriteData('),
            ('src/msg.c', 'void MSG_WriteString('),
            ('src/msg.c', 'void MSG_WriteReliableCommandToBuffer('),
            ('src/qshared.c', 'qboolean I_IsEqualUnitWSpace('),
            ('src/qshared.c', 'unsigned char I_CleanChar('),
            ('src/sv_main.c', 'void sub_5310E0('),
            ('src/sv_main.c', 'int sub_530FC0('),
            ('src/sv_main.c', 'void __cdecl SV_AddServerCommand('),
            ('src/sv_snapshot.c', '__cdecl void SV_UpdateServerCommandsToClient('),
            ('src/sv_snapshot.c', 'void SV_UpdateServerCommandsToClientRecover('),
            ('src/sv_client.c', 'void SV_WWWRedirect('),
            ('src/sv_client.c', '__cdecl void SV_WriteDownloadToClient('),
            ('src/sv_client.c', 'static void SV_CloseDownload( client_t *cl ) {'),
            ('src/sv_client.c', 'void SV_DoneDownload_f('),
            ('src/sv_client.c', 'void SV_SendReliableServerCommand('),
        ]:
            source += function(file, signature)
        source += (ROOT / 'tests/reliable_commands_main.c').read_text()
        (path / 'test.c').write_text(source)
        cls.binary = path / 'test'
        subprocess.run(['gcc', '-m32', '-std=gnu11', '-fno-pie', '-no-pie',
                        '-Wall', '-Wextra', '-Wno-sign-compare',
                        '-I', str(ROOT / 'src'), str(path / 'test.c'),
                        '-o', str(cls.binary)], check=True)

    def run_case(self, name):
        subprocess.run([str(self.binary), name], check=True)

    def test_retransmit_until_acknowledged(self):
        self.run_case('retransmit')

    def test_compaction_preserves_sent_commands(self):
        self.run_case('compact')

    def test_server_producer_without_ack_requests_overflow_drop(self):
        self.run_case('overflow')

    def test_recovery_message_preserves_unsent_tail(self):
        self.run_case('recover')

    def test_download_does_not_consume_command_ring(self):
        self.run_case('download')

    def test_download_backpressure_and_shared_budget(self):
        self.run_case('backpressure')

    def test_done_download_refreshes_gamestate(self):
        self.run_case('done')


if __name__ == '__main__':
    unittest.main()
