#!/usr/bin/env python3
"""Run known installed PE login routines with synthetic inputs (Unicorn 2.1.4).

Does not launch the game, read process memory/configs, or contact any server.
Only accepts the exact binaries investigated; neither binary is redistributed.
"""
import argparse
import hashlib
from pathlib import Path
import struct
from unicorn import Uc, UC_ARCH_X86, UC_MODE_32, UC_HOOK_CODE
from unicorn.x86_const import UC_X86_REG_EAX, UC_X86_REG_ESP, UC_X86_REG_EBP, UC_X86_REG_EIP

KNOWN = {
    'f50f8a520581754e73cb7cae67b02adcbad5f2e71aaa412a013bb3ef57a391a5': 'stock',
    'bf5965ea484e0b899119ebb99428b8f7aaf175f2052e610c1ce466119e6b0d2b': 'cod4x',
}


def probe(path):
    data = path.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    if digest not in KNOWN:
        raise ValueError('Unknown binary revision; refusing unverified addresses')
    kind = KNOWN[digest]
    pe = struct.unpack_from('<I', data, 60)[0]
    count = struct.unpack_from('<H', data, pe + 6)[0]
    opt = pe + 24
    base = struct.unpack_from('<I', data, opt + 28)[0]
    size = struct.unpack_from('<I', data, opt + 56)[0]
    section = opt + struct.unpack_from('<H', data, pe + 20)[0]
    uc = Uc(UC_ARCH_X86, UC_MODE_32)
    uc.mem_map(base, (size + 4095) & ~4095)
    for i in range(count):
        _, rva, length, offset = struct.unpack_from('<IIII', data, section + 40*i + 8)
        uc.mem_write(base + rva, data[offset:offset+length])
    uc.mem_map(0x30000000, 0x10000)
    stack, value, pointers = 0x30008000, 0x30001000, 0x30002000

    def u32(address):
        return struct.unpack('<I', uc.mem_read(address, 4))[0]

    def write32(address, number):
        uc.mem_write(address, struct.pack('<I', number))

    def string(address):
        result = bytearray()
        while True:
            c = uc.mem_read(address + len(result), 1)
            if c == b'\0':
                return bytes(result)
            result += c

    stored = 0xe11558 if kind == 'stock' else 0x63555a80
    entry = 0x471a10 if kind == 'stock' else 0x63195608
    stop = {0x471a62, 0x471a75} if kind == 'stock' else {0x631956cf, 0x631956f0}

    def hook(machine, address, size, _):
        if address in stop:
            machine.emu_stop()
            return
        esp = machine.reg_read(UC_X86_REG_ESP)
        arg = lambda n: u32(esp + 4 + 4*n)
        result = 0
        if kind == 'stock':
            if address == 0x4fcbc0:  # Com_Printf: suppress all output
                pass
            elif address == 0x67cbc0:  # memcpy
                machine.mem_write(arg(0), bytes(machine.mem_read(arg(1), arg(2))))
            else:
                return
        else:
            if address == 0x631a13f3:  # Cmd_Argv
                assert arg(0) == 2
                result = value
            elif address == 0x63374e78:  # strlen
                result = len(string(arg(0)))
            elif address == 0x63374e98:  # strchr
                pos = string(arg(0)).find(bytes([arg(1)]))
                result = arg(0) + pos if pos >= 0 else 0
            elif address == 0x631e0550:  # Q_strncpyz
                machine.mem_write(arg(0), string(arg(1))[:arg(2)-1] + b'\0')
            elif address in (0x631a9790, 0x631a98f0):  # print/debug: suppress
                pass
            else:
                return
        machine.reg_write(UC_X86_REG_EAX, result)
        machine.reg_write(UC_X86_REG_EIP, u32(esp))
        machine.reg_write(UC_X86_REG_ESP, esp + 4)

    uc.hook_add(UC_HOOK_CODE, hook)
    print(f'{kind} sha256={digest}')
    for length in (16, 23, 24, 28, 29, 32, 48, 64):
        previous = b'DisposableOld16X9'
        uc.mem_write(stored, previous + b'\0')
        synthetic = (b'Ab9' * 30)[:length]
        uc.mem_write(value, synthetic + b'\0')
        uc.reg_write(UC_X86_REG_ESP, stack)
        uc.reg_write(UC_X86_REG_EBP, stack + 0x800)
        if kind == 'stock':
            write32(0x1410b40, 0)
            write32(0x1410b84, 3)
            write32(0x1410ba4, pointers)
            write32(pointers + 8, value)
        uc.emu_start(entry, 0, count=10000)
        actual = string(stored)
        accepted = actual == synthetic
        assert accepted == (length <= (23 if kind == 'stock' else 28))
        assert accepted or actual == previous
        print(f'length={length} accepted={int(accepted)} retained_previous={int(actual == previous)}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('binary', type=Path, nargs='+')
    for binary in parser.parse_args().binary:
        probe(binary)
