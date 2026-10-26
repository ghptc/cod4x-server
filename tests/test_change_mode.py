"""Compile and execute the production preflight command without runtime assets."""
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ChangeMode(unittest.TestCase):
    def test_preflight(self):
        with tempfile.TemporaryDirectory(prefix='cod4-change-mode-') as directory:
            binary = Path(directory) / 'test'
            subprocess.run(['gcc', '-m32', '-std=gnu11', '-fno-pie', '-no-pie',
                            '-ffunction-sections', '-fdata-sections', '-Wl,--gc-sections',
                            str(ROOT / 'tests/test_change_mode.c'), '-o', str(binary)],
                           cwd=ROOT, check=True)
            subprocess.run([str(binary)], check=True)
