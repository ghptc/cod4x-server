#!/usr/bin/env python3
"""Run production callvote/vote and the exact native CheckVote assembly in isolation."""
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]

def run(*args):
    subprocess.run(args, cwd=ROOT, check=True)

with tempfile.TemporaryDirectory(prefix='cod4-mapvote-') as directory:
    temp = Path(directory)
    source = (ROOT / 'src/asmsource/_g_main_mp.asm').read_text()
    check = source[source.index('CheckVote:\n'):source.index(';Initialized global', source.index('CheckVote:\n'))]
    (temp / 'check.asm').write_text('BITS 32\nSECTION .text\nglobal CheckVote\n' +
        'extern level, G_UpdateVotingClients, g_voteAbstainWeight, ceilf, va\n' +
        'extern SV_GameSendServerCommand, SV_SetConfigstring, Cbuf_AddText\n' + check +
        '\nSECTION .rodata\n_cstring_c_game_votefaile: db "%c GAME_VOTEFAILED",0\n' +
        '_cstring_c_game_votepasse: db "%c GAME_VOTEPASSED",0\n' +
        '_cstring_null: db 0\n_cstring_s: db "%s",0\n' +
        'SECTION .note.GNU-stack noalloc noexec nowrite progbits\n')
    run('nasm', '-f', 'elf32', str(temp / 'check.asm'), '-o', str(temp / 'check.o'))
    for name, file in [('test', 'tests/test_map_voting.c'), ('vote', 'src/g_cmds.c')]:
        run('gcc', '-m32', '-std=gnu11', '-fno-pie', '-ffunction-sections', '-fdata-sections',
            '-c', file, '-o', str(temp / f'{name}.o'))
    run('gcc', '-m32', '-no-pie', '-Wl,--gc-sections', str(temp / 'test.o'),
        str(temp / 'vote.o'), str(temp / 'check.o'), '-lm', '-o', str(temp / 'test'))
    run(str(temp / 'test'))
