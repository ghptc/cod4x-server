#!/usr/bin/env python3
from pathlib import Path
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='cod4-rotation-') as directory:
    temp = Path(directory)
    for name, source in [('test', 'tests/test_map_rotation.c'), ('shared', 'src/qshared.c')]:
        command = ['gcc', '-m32', '-std=gnu11', '-fno-pie', '-ffunction-sections', '-fdata-sections']
        if name == 'shared':
            command.append('-DNDEBUG')
        subprocess.run(command + ['-c', source, '-o', str(temp / f'{name}.o')], cwd=root, check=True)
    subprocess.run(['gcc', '-m32', '-no-pie', '-Wl,--gc-sections', str(temp / 'test.o'),
                    str(temp / 'shared.o'), '-lm', '-o', str(temp / 'test')], check=True)
    subprocess.run([str(temp / 'test')], check=True)
