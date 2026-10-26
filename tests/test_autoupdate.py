#!/usr/bin/env python3
"""Actual updater entry and lock functions with deterministic clock boundaries."""
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
PREFIX = r'''
#include <assert.h>
#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <sys/file.h>
#define qboolean int
#define qtrue 1
#define CVAR_INIT 16
#define CON_CHANNEL_SYSTEM 0
#define SEC_UPDATE_INITIALBUFFSIZE 1024
#define SEC_VERSION 1
#define OS_STRING "linux"
typedef struct { int boolean; } cvar_t;
typedef struct sec_file_s { struct sec_file_s *next; } sec_file_t;
typedef struct {} ftRequest_t;
static const char *directory;
static int sleeps, initialized_calls, configured = 1, default_enabled, init_only;
static int last_errno;
static time_t clock_seconds;
static cvar_t option;
static time_t fake_time(time_t *out) { *out=clock_seconds; return clock_seconds; }
#define time fake_time
static const char *Sys_BinaryPath(void) { return directory; }
static void FS_BuildOSPathForThread(const char *p,const char *n,const char *x,char *out,int t) {
    (void)x;(void)t; snprintf(out,1024,"%s/%s",p,n);
}
static void FS_StripTrailingSeperator(char *p) { (void)p; }
static void Com_Printf(int c,const char *fmt,...) { (void)c;(void)fmt; }
static void Sys_SleepSec(int n) { ++sleeps; clock_seconds+=n; }
static void Sys_Restart(const char *reason) { (void)reason; abort(); }
static cvar_t *Cvar_RegisterBool(const char *name,int def,int flags,const char *desc) {
    assert(!strcmp(name,"sv_autoupdate") && *desc);
    default_enabled=def; init_only=(flags==CVAR_INIT); option.boolean=configured; return &option;
}
static int Cvar_GetBool(const char *name) { assert(!strcmp(name,"sv_autoupdate")); return option.boolean; }
static void InitUpdateCvar(void);
static int Sec_Initialized(void) { ++initialized_calls; return 1; }
'''
TAIL = r'''
int main(int argc,char **argv) {
    assert(argc==3); directory=argv[2];
    if(!strcmp(argv[1],"off") || !strcmp(argv[1],"on")) {
        configured=!strcmp(argv[1],"on"); InitUpdateCvar(); Sec_Update(0);
        assert(default_enabled==1 && init_only);
        assert(initialized_calls==configured && sleeps==0);
        printf("enabled=%d initialized_calls=%d sleeps=%d\n",configured,initialized_calls,sleeps);
        return 0;
    }
    char filename[1024]; snprintf(filename,sizeof(filename),"%s/autoupdate.lock",directory);
    FILE *held=NULL;
    if(!strcmp(argv[1],"held")) { held=fopen(filename,"wb"); assert(held && !flock(fileno(held),LOCK_EX|LOCK_NB)); }
    errno=0;
    FILE *handle=Sec_AutoaupdateLock(); last_errno=errno;
    if(handle) fclose(handle);
    if(held) fclose(held);
    printf("handle=%d errno=%d sleeps=%d elapsed=%ld\n",handle!=NULL,last_errno,sleeps,(long)clock_seconds);
    return 0;
}
'''


def build(directory):
    text = (ROOT / 'src/sec_update.c').read_text()
    start = text.index('FILE* Sec_AutoaupdateLock()')
    lock = text[start:text.index('void Sec_AutoupdateUnlock', start)]
    start = text.index('void Sec_Update( qboolean getbasefiles )')
    # Stop at the first original banner; test the real early startup guard only.
    entry = text[start:text.index('    Com_Printf(CON_CHANNEL_SYSTEM,"\\n---', start)] + '}\n'
    source = directory / 'updater.c'
    common = (ROOT / 'src/common.c').read_text()
    first = common.index('    Cvar_RegisterBool("sv_autoupdate"')
    registration = common[first:common.index(');', first)+2]
    source.write_text(PREFIX + lock + entry + 'static void InitUpdateCvar(void) {\n' + registration + '\n}\n' + TAIL)
    binary = directory / 'updater'
    subprocess.run(['cc', '-static', '-std=gnu11', str(source), '-o', str(binary)], check=True)
    return binary


class Autoupdate(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workspace = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.workspace.cleanup)
        cls.path = Path(cls.workspace.name)
        cls.binary = build(cls.path)

    def run_case(self, mode, directory):
        return subprocess.check_output([str(self.binary), mode, str(directory)], text=True).strip()

    def test_explicit_off_returns_before_crypto_check(self):
        self.assertEqual(self.run_case('off', '/nonexistent'), 'enabled=0 initialized_calls=0 sleeps=0')

    def test_default_enabled_reaches_original_path(self):
        self.assertEqual(self.run_case('on', self.path), 'enabled=1 initialized_calls=1 sleeps=0')

    def test_writable_lock_and_advisory_lock_are_not_waited_on(self):
        self.assertEqual(self.run_case('lock', self.path), 'handle=1 errno=0 sleeps=0 elapsed=0')
        self.assertEqual(self.run_case('held', self.path), 'handle=1 errno=0 sleeps=0 elapsed=0')

    def test_missing_directory_retries_as_if_locked(self):
        self.assertEqual(self.run_case('lock', self.path / 'missing'),
                         'handle=0 errno=2 sleeps=17 elapsed=255')


if __name__ == '__main__':
    unittest.main()
