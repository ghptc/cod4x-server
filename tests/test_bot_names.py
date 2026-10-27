"""Compile and exercise the exact bounded native name parser."""
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class BotNames(unittest.TestCase):
    def test_native_parser_boundaries_and_userinfo_characters(self):
        source = r'''
#include <assert.h>
#include <string.h>
#include "sv_bot_names.h"
int main(void) {
    const char data[] = "\n Capt. Price \r\nSoap MacTavish\nBad\\name\nBad;name\nBad\"name\n^1Red\nBad\tname\n01234567890123456789012345678901\nGaz";
    const char *cursor = data;
    char name[BOT_NAME_BYTES];
    assert(BotName_Next(&cursor, data + sizeof(data)-1, name));
    assert(!strcmp(name, "Capt. Price"));
    assert(BotName_Next(&cursor, data + sizeof(data)-1, name));
    assert(!strcmp(name, "Soap MacTavish"));
    assert(BotName_Next(&cursor, data + sizeof(data)-1, name));
    assert(!strcmp(name, "Gaz"));
    assert(!BotName_Next(&cursor, data + sizeof(data)-1, name));
    { const char bounded[] = {'G','a','z','X'}; cursor = bounded;
      assert(BotName_Next(&cursor, bounded+3, name)); assert(!strcmp(name,"Gaz")); }
    { const char embedded[] = {'x',0,'y','\n','G','a','z'}; cursor=embedded;
      assert(BotName_Next(&cursor, embedded+7, name)); assert(!strcmp(name,"Gaz")); }
    return 0;
}
'''
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            (path / 'names.c').write_text(source)
            subprocess.run(['cc', '-std=c99', '-Wall', '-Wextra', '-Werror', '-I', str(ROOT / 'src'),
                            str(path / 'names.c'), '-o', str(path / 'names')], check=True)
            subprocess.run([str(path / 'names')], check=True)
