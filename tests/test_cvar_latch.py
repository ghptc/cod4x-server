"""A later canonical string setting must cancel an earlier private latch."""
from pathlib import Path
import subprocess
import tempfile
import unittest
from test_rcon import function

ROOT = Path(__file__).resolve().parents[1]


class StringLatch(unittest.TestCase):
    def test_restore_current_value_replaces_pending_value(self):
        with tempfile.TemporaryDirectory(prefix='cod4-cvar-latch-') as directory:
            path = Path(directory)
            source = (ROOT / 'tests/rcon_harness.c').read_text()
            source += function('src/cmd.c', 'static void Cmd_TokenizeStringInternal(')
            source += function('src/cvar.c', 'static int Cvar_SetVariant( cvar_t *var, CvarValue value ,qboolean force ) {')
            source += r'''
int main(void) {
    cvar_t var = {0};
    var.type = CVAR_STRING; var.flags = CVAR_LATCH;
    var.string = CopyString("war"); var.latchedString = CopyString("war");
    CvarValue value = {.string = "sd"};
    assert(Cvar_SetVariant(&var, value, qfalse) == 1);
    assert(!strcmp(var.string, "war") && !strcmp(var.latchedString, "sd"));
    value.string = "war";
    assert(Cvar_SetVariant(&var, value, qfalse) == 1);
    assert(!strcmp(var.string, "war") && !strcmp(var.latchedString, "war"));
    assert(Cvar_SetVariant(&var, value, qfalse) == 0);
    FreeString(var.string); FreeString(var.latchedString);
    return 0;
}
'''
            (path / 'test.c').write_text(source)
            subprocess.run(['cc', '-std=gnu11', '-Wno-attributes', '-ffunction-sections', '-fdata-sections',
                            '-Wl,--gc-sections', '-I', str(ROOT / 'src'), str(path / 'test.c'),
                            '-o', str(path / 'test')], check=True)
            subprocess.run([str(path / 'test')], check=True)
