"""Execute real filename sanitizers and the optional Unix hook quoting boundary."""
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ScreenshotSecurity(unittest.TestCase):
    def test_player_names_remain_literal_shell_arguments(self):
        source = (ROOT / 'src/sv_screenshot.c').read_text()
        functions = source[source.index('char FilenameCharValidate('):source.index('void SV_ScreenshotBuildName(')]
        with tempfile.TemporaryDirectory() as directory:
            fixture = Path(directory) / 'filename.c'
            binary = Path(directory) / 'filename'
            fixture.write_text('#include <stdio.h>\n' + functions +
                               '\nint main(int argc,char **argv) { if(argc!=2)return 1; ValidateFilename(argv[1]); puts(argv[1]); return 0; }\n')
            subprocess.run(['cc', '-Wall', '-Wextra', '-Werror', str(fixture), '-o', str(binary)], check=True)
            for name in ('Player-One_123', '$(printf${IFS}EXPANDED)', '`printf${IFS}EXPANDED`',
                         '%COMSPEC%!PATH!', '";printf EXPANDED;', 'a\\b/c\nname', '<svg/onload=x>'):
                with self.subTest(name=name):
                    safe = subprocess.check_output([str(binary), name], text=True).strip()
                    # Same double-quoted filename argument as SV_ScreenshotArrived;
                    # only harmless printf runs, with no game/network/file effects.
                    result = subprocess.check_output(['/bin/sh', '-c', 'printf "%s" "' + safe + '"'], text=True)
                    self.assertEqual(result, safe)
                    self.assertRegex(safe, r'^[A-Za-z0-9_-]+$')
                    if name == 'Player-One_123': self.assertEqual(safe, name)


if __name__ == '__main__':
    unittest.main()
