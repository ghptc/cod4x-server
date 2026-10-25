#!/usr/bin/env python3
"""Exercise the actual loader's file validation without proprietary assets."""
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
HARNESS = r'''
#include <assert.h>
#include <setjmp.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#define MAX_OSPATH 256
#define ERR_FATAL 1
#define CON_CHANNEL_FILES 0
typedef struct { const char *string; } cvar_t;
static cvar_t *fs_localizedHeadersPath;
static int *fs_additionalPureChecksums, fs_additionalPureChecksumCount;
static int fs_checksumFeed = 0x11223344, checksum_calls;
static jmp_buf error;
static void Com_Error(int code, const char *fmt, ...) { (void)code; (void)fmt; longjmp(error, 1); }
static void Com_Printf(int channel, const char *fmt, ...) { (void)channel; (void)fmt; }
static void *Z_Malloc(size_t n) { return malloc(n); }
static int LittleLong(int value) { return value; }
static int Com_BlockChecksumKey32(const unsigned char *data, int n, int key) {
    assert(n > 0 && key == fs_checksumFeed);
    ++checksum_calls;
    return key ^ data[0];
}
'''
TAIL = r'''
int main(int argc, char **argv) {
    assert(argc == 3);
    cvar_t path = {argv[1]};
    fs_localizedHeadersPath = &path;
    int failed = setjmp(error);
    if (!failed) FS_LoadAdministrativeLocalizedChecksums();
    if (atoi(argv[2])) {
        assert(!failed && fs_additionalPureChecksumCount == 8 && checksum_calls == 8);
        for (int i = 0; i < 8; ++i) assert(fs_additionalPureChecksums[i] == (fs_checksumFeed ^ i));
    } else {
        assert(failed && fs_additionalPureChecksums == NULL && fs_additionalPureChecksumCount == 0);
    }
    free(fs_additionalPureChecksums);
    return 0;
}
'''


class AdministrativeHeaders(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workspace = tempfile.TemporaryDirectory()
        cls.root = Path(cls.workspace.name)
        source = (ROOT / 'src/filesystem.c').read_text()
        start = source.index('static void FS_LoadAdministrativeLocalizedChecksums(void)')
        end = source.index('\nvoid FS_InitLocalizedIwdPureChecksums()', start)
        harness = cls.root / 'loader.c'
        harness.write_text(HARNESS + source[start:end] + TAIL)
        cls.binary = cls.root / 'loader-test'
        subprocess.run(['gcc', '-std=gnu11', '-Wall', '-Wextra', '-Werror', str(harness), '-o', str(cls.binary)], check=True)

    @classmethod
    def tearDownClass(cls):
        cls.workspace.cleanup()

    def setUp(self):
        self.input = self.root / self._testMethodName
        headers = self.input / 'addiwdheaders'
        headers.mkdir(parents=True)
        self.files = [headers / f'localized_english_iw{i:02d}.dat' for i in range(7)] + [headers / 'jcod4x_00.dat']
        for i, file in enumerate(self.files):
            file.write_bytes(struct.pack('<I', i))

    def run_loader(self, success, path=None):
        subprocess.run([str(self.binary), str(path if path is not None else self.input), str(int(success))], check=True)

    def test_valid_eight_headers(self):
        self.run_loader(True)

    def test_missing_eighth_does_not_publish_partial_list(self):
        self.files[-1].unlink()
        self.run_loader(False)

    def test_empty_file(self):
        self.files[3].write_bytes(b'')
        self.run_loader(False)

    def test_unaligned_file(self):
        self.files[3].write_bytes(b'abc')
        self.run_loader(False)

    def test_oversized_file(self):
        self.files[3].write_bytes(b'x' * 16384)
        self.run_loader(False)

    def test_empty_administrative_path(self):
        self.run_loader(False, '')


if __name__ == '__main__':
    unittest.main()
