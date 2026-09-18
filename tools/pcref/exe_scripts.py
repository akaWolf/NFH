"""The PC neighbour's routines out of game.exe (Season 1), the way
docs/PC_ROUTINES.md was made — 2026-09-15.

game.exe is one compiled class per level; each class's `run` is a linear
script of engine calls. The level's object and action names are static
UTF-16 String globals, constructed at startup by `push <str>; push <global>;
call <ctor>` (0x4ae870 for "lir/book" -> 0x51a480), and the script code
refers to the globals: `mov edx, [global]` then a call. The helpers, by
their argument patterns:

    fcn.00437f70  SetIcon(ecx = icon name)          the bubble
    fcn.00479da0  GoTo(edx = object)                 the walk
    fcn.00477f60  DoAction(ecx = object, edx = action)
    fcn.0047a130  IsVariant(ecx = tricked object, edx = object)  a branch
    fcn.00451de0  SwitchObjects(push b, push a)      a -> b after a trick
    fcn.0044bb80 / 004766e0 / 0045f670 / 0047c640    the waits between

Steps:
  1. nix-shell -p radare2 --run "r2 -q -e scr.color=0 -e asm.lines=false
     -e asm.comments=false -c 'aaa; pD 894074 @ 0x401000' game.exe" > text.txt
  2. python3 tools/pcref/exe_scripts.py game.exe text.txt > scripts.json

The output lists, per level (matched by the objects.xml names of the copies
in ~/nfh-bench/pcref/pc/nfh1/x), the calls in CODE order. Mind that the
compiler lays the tricked-variant branches out of line: the code order is
not always the lap order — docs/PC_LAPS.md's orders (read off the video)
stay the reference for the lap, this file for the actions and their
repeats (the laundry's two wash and two dry cycles, the bath's towel
sequence). GameLogic.dll (Season 2, `--gl <GameLogic.dll> <dump>`) has the
same constant pattern and its own helpers, named 2026-09-16:

    fcn.100422a5  SetIcon(actor, icon)              the bubble
    fcn.1000e3e0  GoTo(level, actor, object) -> bool the walk (false: interrupted)
    fcn.1000aeb8 / 1000ae19                        the waits
    fcn.10002cd5  DoAction(actor, anim)
    fcn.1000f977  Shout(actor, n)                    a random shout<n>/freakout anim
    fcn.1000fb6e  IsVariant(a, b)   fcn.1000ec67  IsTricked(object)   branches
    fcn.1000fc33  RoomMove(actor, room)
"""
import glob
import json
import os
import re
import struct
import sys

CALLS = {'fcn.00479da0': 'GOTO', 'fcn.00477f60': 'ACTION', 'fcn.00437f70': 'ICON',
         'fcn.00451de0': 'SWITCH', 'fcn.0047a130': 'IFVARIANT', 'fcn.00451e80': 'OBJ1',
         'fcn.0047c290': 'OBJ2', 'fcn.00479ff0': 'OBJ3'}


def sections(b, base=0x400000):
    pe = struct.unpack_from('<I', b, 0x3c)[0]
    nsec = struct.unpack_from('<H', b, pe + 6)[0]
    opt = struct.unpack_from('<H', b, pe + 20)[0]
    out = []
    for i in range(nsec):
        off = pe + 24 + opt + i * 40
        vsize, va, rsize, raw = struct.unpack_from('<IIII', b, off + 8)
        out.append((base + va, vsize, raw, rsize))
    return out


def globals_map(exe):
    b = open(exe, 'rb').read()
    secs = sections(b)

    def va2off(va):
        for sva, vsize, raw, rsize in secs:
            if sva <= va < sva + max(vsize, rsize):
                return raw + (va - sva)

    def off2va(off):
        for sva, vsize, raw, rsize in secs:
            if raw <= off < raw + rsize:
                return sva + (off - raw)

    def wide_at(va):
        off = va2off(va)
        m = re.match(rb'(?:[\x20-\x7e]\x00)+', b[off:off + 200]) if off else None
        return m.group(0).decode('utf-16le') if m else None

    sites = []
    # re.S: an address byte 0x0a is a newline to `.` (the scan missed
    # 'marker', 0x519d60 <- 0x4ab430)
    for m in re.finditer(rb'\x68(....)\x68(....)\xe8', b, re.S):
        s_va, g_va = struct.unpack('<I', m.group(1))[0], struct.unpack('<I', m.group(2))[0]
        if 0x4d0000 <= s_va < 0x4f0000 and 0x510000 <= g_va < 0x530000:
            name = wide_at(s_va)
            if name:
                sites.append((off2va(m.start()), g_va, name))
    sites.sort()
    return sites


def level_of_block(blocks, xml_root):
    levels = {}
    for d in sorted(glob.glob(os.path.join(xml_root, 'level_*')) + glob.glob(os.path.join(xml_root, 'tutorial_*'))):
        raw = open(os.path.join(d, 'objects.xml'), 'rb').read()
        text = raw.decode('utf-16') if raw[:2] in (b'\xff\xfe', b'\xfe\xff') else raw.decode('utf-8', 'replace')
        levels[os.path.basename(d)] = set(re.findall(r'<(?:object|door) name="([^"]+)"', text))
    g2level = {}
    for blk in blocks:
        objs = set(n for _, _, n in blk if '/' in n and not n.startswith(('music', 'sfx', 'gui', 'gfx')))
        best = max(levels, key=lambda L: len(objs & levels[L])) if objs else None
        ok = best if best and len(objs & levels[best]) >= 3 else None
        for a, g, n in blk:
            g2level[g] = (ok, n)
    return g2level


GL_CALLS = {'fcn.1000e3e0': 'GOTO', 'fcn.10002cd5': 'ACTION', 'fcn.100422a5': 'ICON',
            'fcn.1000f977': 'SHOUT', 'fcn.1000fb6e': 'IFVARIANT', 'fcn.1000ec67': 'IFTRICKED',
            'fcn.1000fc33': 'ROOM', 'fcn.1000f5c9': 'SET'}


def main_gl(dll, dump, xml_root=os.path.expanduser('~/nfh-bench/pcref/pc/nfh2/x'),
            gmap=os.path.join(os.path.dirname(os.path.abspath(__file__)), 'exe', 'nfh2_gamelogic_globals.json')):
    """the Season 2 scripts out of GameLogic.dll (base 0x10000000): the
    String globals come from exe/nfh2_gamelogic_globals.json (the same
    push-push-call init as Season 1's: the map's first cut missed every
    constant whose address holds a 0x0a byte, the short UTF-16 names among
    them — `use`, `sit`, `run` — added 2026-09-23), the level blocks are the copies of the
    engine's string table in address order, split at each copy's 'trick',
    and a block's level is the objects.xml whose room/object names
    ('pond/bridge' -> 'pond_bridge') it shares most; the calls above"""
    G = {int(k, 16): v for k, v in json.load(open(gmap)).items()}
    sites = sorted((g, n) for g, n in G.items())
    blocks, cur = [], []
    for g, n in sites:
        # the engine's table (194 names, 'sfx_illegal.wav' first) is copied
        # once per level class; the level's own object table sits between
        # two copies as a block of its own
        if n == sites[0][1] and cur:
            blocks.append(cur); cur = []
        cur.append((g, n))
    blocks.append(cur)
    levels = {}
    for d in sorted(glob.glob(os.path.join(xml_root, '*'))):
        f = os.path.join(d, 'objects.xml')
        if not os.path.exists(f):
            continue
        raw = open(f, 'rb').read()
        text = raw.decode('utf-16') if raw[:2] in (b'\xff\xfe', b'\xfe\xff') else raw.decode('utf-8', 'replace')
        levels[os.path.basename(d)] = set(x.replace('/', '_') for x in re.findall(r'<(?:object|door) name="([^"]+)"', text))
    g2level = {}
    for blk in blocks:
        objs = set(n.replace('/', '_') for _, n in blk)
        best = max(levels, key=lambda L: len(objs & levels[L])) if objs else None
        ok = best if best and len(objs & levels[best]) >= 3 else None
        for g, n in blk:
            g2level[g] = (ok, n)
    events, pending = [], []
    for ln in open(dump):
        m = re.search(r'(0x100[0-9a-f]{5})\s+[0-9a-f]{2,}\s+(.*)$', ln)
        if not m:
            continue
        addr, ins = int(m.group(1), 16), m.group(2).strip()
        gs = [int(x, 16) for x in re.findall(r'0x100[de][0-9a-f]{4}', ins)]
        if gs and ins.startswith(('mov ecx', 'mov edx', 'mov eax', 'push 0x')):
            pending.append((addr, gs[0])); pending = pending[-4:]
        pm = re.match(r'push ([0-9]|0x[0-9a-f]+)$', ins)
        if pm:
            pending.append((addr, ('imm', int(pm.group(1), 0)))); pending = pending[-4:]
        cm = re.match(r'call (fcn\.[0-9a-f]+)', ins)
        if cm and cm.group(1) in GL_CALLS:
            args = []
            for a, g in pending:
                if addr - a >= 0x100:
                    continue
                args.append(str(g[1]) if isinstance(g, tuple) else g2level.get(g, (None, hex(g)))[1])
            lvl = next((g2level[g][0] for a, g in pending if not isinstance(g, tuple) and g in g2level and g2level[g][0]), None)
            events.append((addr, GL_CALLS[cm.group(1)], args, lvl)); pending = []
    # an event that names only engine globals (`DoAction(neighbor, leave)`)
    # belongs to the level class whose code it sits in: the last level seen
    # in address order
    by, last = {}, None
    for addr, kind, args, lvl in events:
        if lvl is None:
            lvl = last
        last = lvl
        by.setdefault(str(lvl), []).append((hex(addr), kind, args))
    json.dump(by, sys.stdout, indent=0)


def main(exe, dump, xml_root=os.path.expanduser('~/nfh-bench/pcref/pc/nfh1/x')):
    sites = globals_map(exe)
    blocks, cur = [], []
    for a, g, n in sites:            # each level's constants start with 'normal'
        if n == 'normal' and cur:
            blocks.append(cur); cur = []
        cur.append((a, g, n))
    blocks.append(cur)
    g2level = level_of_block(blocks, xml_root)
    events, pending = [], []
    for ln in open(dump):
        m = re.search(r'(0x004[0-9a-f]{5})\s+[0-9a-f]{2,}\s+(.*)$', ln)
        if not m:
            continue
        addr, ins = int(m.group(1), 16), m.group(2).strip()
        gs = [int(x, 16) for x in re.findall(r'0x51[0-9a-f]{4}', ins)]
        if gs and ins.startswith(('mov ecx', 'mov edx', 'push 0x')):
            pending.append((addr, gs[0])); pending = pending[-4:]
        cm = re.match(r'call (fcn\.[0-9a-f]+)', ins)
        if cm and cm.group(1) in CALLS:
            args = [g2level.get(g, (None, hex(g)))[1] for a, g in pending if addr - a < 0x40]
            lvl = next((g2level[g][0] for a, g in pending if g in g2level and g2level[g][0]), None)
            events.append((addr, CALLS[cm.group(1)], args, lvl)); pending = []
    by = {}
    for addr, kind, args, lvl in events:
        by.setdefault(str(lvl), []).append((hex(addr), kind, args))
    json.dump(by, sys.stdout, indent=0)


if __name__ == '__main__':
    if sys.argv[1:2] == ['--gl']:
        main_gl(*sys.argv[2:])
    else:
        main(*sys.argv[1:])
