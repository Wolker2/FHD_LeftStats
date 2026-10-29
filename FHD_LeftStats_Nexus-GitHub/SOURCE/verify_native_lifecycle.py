"""Probe real SRHD sibling ordering and entry layout, with stubbed UI methods.

This is not a renderer or a full game run. Requires pefile and unicorn.
"""
from pathlib import Path
import argparse
import hashlib
import re
import struct

import pefile
from unicorn import Uc, UC_ARCH_X86, UC_MODE_32, UC_HOOK_CODE
from unicorn.x86_const import UC_X86_REG_EAX, UC_X86_REG_ECX, UC_X86_REG_EDX, UC_X86_REG_ESP, UC_X86_REG_EIP, UC_X86_REG_EBP
from compile_srhd_dat import parse_blockpar, parse_bp_raw, unpack_dat_bytes
from verify import merge, named

EXPECTED = '83300344af802bc51e64389c58f047e5afdf195c133048098be3881fae29ed98'


def value(node, key, default=None):
    return next((e.value for e in node.elems if e.name == key and e.child is None), default)


class NativeUI:
    STOP = 0x1800800
    SETPOS = 0x1800100
    SETACTIVE = 0x1800200
    PAINT = 0x1800300
    FORM = 0x2100000
    VMT = 0x2000000
    STACK = 0x300f000

    def __init__(self, exe, tree):
        pe = pefile.PE(str(exe))
        self.u = Uc(UC_ARCH_X86, UC_MODE_32)
        payload = pe.get_memory_mapped_image()
        self.u.mem_map(0x400000, (len(payload) + 4095) & ~4095)
        self.u.mem_write(0x400000, payload)
        for start, size in [(0x1800000, 0x10000), (0x2000000, 0x800000), (0x3000000, 0x10000)]:
            self.u.mem_map(start, size)
        self.put(self.VMT + 0xc, self.SETPOS)
        self.put(self.VMT + 0x28, self.SETACTIVE)
        self.put(self.VMT + 0xa0, self.PAINT)
        self.objects = {}
        self.nodes = {}
        self.names = {}
        self.paint = []
        self.parents = {}
        self._visit(tree)
        self.put(self.FORM, self.VMT)
        self.put(self.FORM + 0x374, 398)
        self.put(self.FORM + 0x378, 410)
        self.put(0x87bbd8, 0x2600000)
        self.u.mem_write(0x2610070, b'\1')
        self.u.hook_add(UC_HOOK_CODE, self.hook)

    def put(self, addr, val):
        self.u.mem_write(addr, struct.pack('<I', val & 0xffffffff))

    def get(self, addr):
        return struct.unpack('<I', self.u.mem_read(addr, 4))[0]

    def _visit(self, node, parent=None):
        addr = 0x2200000 + len(self.nodes) * 0x200
        self.nodes[id(node)] = addr
        self.parents[addr] = parent
        name = value(node, 'Name')
        if name:
            assert name not in self.objects, 'Duplicate native binding: ' + name
            self.objects[name] = addr
        self.names[addr] = name or 'anonymous'
        self.put(addr, self.VMT)
        self.u.mem_write(addr + 0x41, bytes([value(node, 'Active', 'True') != 'False']))
        pos = [int(x) for x in value(node, 'Pos', '0,0').split(',')[:2]]
        self.put(addr + 0x20, pos[0]); self.put(addr + 0x24, pos[1])
        # Draw traversal probe uses intersecting rectangles, not actual rasterization.
        self.u.mem_write(addr + 0x60, struct.pack('<4i', 0, 0, 1920, 1080))
        self.put(addr + 0x18, 0x2500000)
        for e in node.elems:
            if e.child is not None:
                self._visit(e.child, addr)

    def active(self, name):
        return bool(self.u.mem_read(self.objects[name] + 0x41, 1)[0])

    def visible(self, name):
        addr = self.objects[name]
        while addr is not None:
            if not self.u.mem_read(addr + 0x41, 1)[0]:
                return False
            addr = self.parents[addr]
        return True

    def ret(self):
        sp = self.u.reg_read(UC_X86_REG_ESP)
        pc = self.get(sp)
        self.u.reg_write(UC_X86_REG_ESP, sp + 4)
        self.u.reg_write(UC_X86_REG_EIP, pc)

    def hook(self, uc, addr, size, _):
        if addr == self.STOP:
            uc.emu_stop()
        elif addr == 0x4cefc8:
            ptr = uc.reg_read(UC_X86_REG_EDX)
            raw = bytearray()
            while (c := bytes(uc.mem_read(ptr, 2))) != b'\0\0':
                raw.extend(c); ptr += 2
            uc.reg_write(UC_X86_REG_EAX, self.objects[raw.decode('utf-16le')])
            self.ret()
        elif addr == 0x414ea0:
            ptr = uc.reg_read(UC_X86_REG_ECX)
            self.put(ptr, uc.reg_read(UC_X86_REG_EAX))
            self.put(ptr + 4, uc.reg_read(UC_X86_REG_EDX))
            self.ret()
        elif addr == self.SETPOS:
            obj = uc.reg_read(UC_X86_REG_EAX); ptr = uc.reg_read(UC_X86_REG_EDX)
            self.put(obj + 0x20, self.get(ptr)); self.put(obj + 0x24, self.get(ptr + 4))
            self.ret()
        elif addr == self.SETACTIVE:
            obj = uc.reg_read(UC_X86_REG_EAX)
            uc.mem_write(obj + 0x41, bytes([bool(uc.reg_read(UC_X86_REG_EDX) & 255)]))
            self.ret()
        elif addr == self.PAINT:
            self.paint.append(uc.reg_read(UC_X86_REG_EAX))
            self.ret()
        elif addr == 0x7a568c:
            self.ret()  # unrelated item-help panel
        elif addr == 0x78c078:
            uc.reg_write(UC_X86_REG_EAX, 0x2600000); self.ret()
        elif addr == 0x70e5e0:
            uc.reg_write(UC_X86_REG_EAX, 0x2610000); self.ret()

    def run(self, start, end=None, eax=FORM, edx=0, ecx=0, args=b''):
        self.put(self.STACK, self.STOP)
        # Ship.Enter slices use the surrounding function's EBP-local self.
        self.u.reg_write(UC_X86_REG_EBP, self.STACK - 0x800)
        self.put(self.STACK - 0x804, self.FORM)
        if args:
            self.u.mem_write(self.STACK + 4, args)
        for reg, val in [(UC_X86_REG_ESP, self.STACK), (UC_X86_REG_EAX, eax), (UC_X86_REG_EDX, edx), (UC_X86_REG_ECX, ecx)]:
            self.u.reg_write(reg, val)
        self.u.emu_start(start, end or self.STOP, count=20000)


def order_probe(exe, tree):
    ui = NativeUI(exe, tree)
    root = named(tree, 'MainPanel')
    parent = ui.nodes[id(root)]
    for e in root.elems:
        if e.child is None:
            continue
        pos = value(e.child, 'Pos', '0,0').split(',')
        z = float(pos[2]) if len(pos) > 2 else 0.0
        # Execute native sibling insertion; Z is sorted per parent, not summed.
        ui.run(0x4c96c8, eax=parent, edx=ui.nodes[id(e.child)], args=struct.pack('<d', z))
    # Execute native forward draw traversal and rectangle intersections.
    ui.run(0x4cac4c, eax=parent, edx=parent + 0x60)
    bg = ui.objects['BGBuf']; stats = ui.objects['FHD_LeftStatsPanel']
    cargo = ui.nodes[id(next(e.child for e in root.elems if e.name == 'Panel' and named(e.child, 'PanelRH') is not None))]
    print('Native root draw order:', [ui.names[a] for a in ui.paint])
    assert ui.paint.index(bg) < ui.paint.index(stats) < ui.paint.index(cargo), 'Statistics are behind the background or cover equipment; parent Z cannot be added'
    print('PASS: native draw traversal paints background, left statistics, equipment/cargo in that order')


def entry_probe(exe, tree, language):
    ui = NativeUI(exe, tree)
    info = named(tree, 'FHD_LeftStatsPanel')
    assert value(info, 'Active') == 'True'
    # This evaluates only the simple mode guard in the real callback source.
    # The RScript interpreter and callback-info installation are not emulated.
    pattern = r"if\((!?)UICheckElement\('Ship','([^']+)','IsActive'\)\) ButtonClick\('Ship','ToRH'\);"
    guards = re.findall(pattern, language)
    assert len(guards) == 1, 'Unsupported entry guard; update the probe'
    negate, target = guards[0]
    ui.u.mem_write(ui.FORM + 0xd4, b'\1')  # player equipment view
    for number in range(1, 4):
        mode = bool(ui.u.mem_read(ui.FORM + 0x4a4, 1)[0])
        condition = not ui.active(target) if negate else ui.active(target)
        if condition:
            ui.run(0x6f50e8)  # original ToRH/FromRH handler
        # After t_OnEnteringForm, native Ship.Enter recalculates tab visibility.
        ui.run(0x6d771e, 0x6d78fc)
        actual_mode = bool(ui.u.mem_read(ui.FORM + 0x4a4, 1)[0])
        print(f'Open {number}: previous hold mode={mode}, guard={condition}, hold={ui.active("PanelRH")}, statistics={ui.visible("FHD_LeftStatsPanel")}')
        assert actual_mode and ui.active('PanelRH') and ui.visible('FHD_LeftStatsPanel'), 'First/repeated native entry leaves a required panel closed'
    # Reentry after an item move must preserve cargo mode, rather than toggle it.
    if (not ui.active(target) if negate else ui.active(target)):
        ui.run(0x6f50e8)
    ui.run(0x6d771e, 0x6d78fc)
    assert ui.active('PanelRH') and not ui.active('PanelRight')
    print('PASS: first open, two reopenings and item-update layout preserve cargo mode')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--exe', type=Path, required=True)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parent.parent)
    parser.add_argument('--probe', choices=['order', 'entry', 'all'], default='all')
    args = parser.parse_args()
    assert hashlib.sha256(args.exe.read_bytes()).hexdigest() == EXPECTED, 'Unsupported reference EXE'
    src = args.root / 'SOURCE'
    tree = merge(parse_blockpar(src / 'fixtures/vanilla_ship.txt'), parse_bp_raw(unpack_dat_bytes((args.root / 'CFG/Main.dat').read_bytes(), 0xB1E8C689)))
    if args.probe in ['order', 'all']:
        order_probe(args.exe, tree)
    if args.probe in ['entry', 'all']:
        for lang in ['Rus', 'Eng']:
            print('Language:', lang)
            entry_probe(args.exe, tree, (src / 'CFG' / lang / 'Lang.txt').read_text())


if __name__ == '__main__':
    main()
