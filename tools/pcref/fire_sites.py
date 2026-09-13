"""The Season 1 trick-fire steps of game.exe, decoded from the radare2 text
listing (~/nfh-bench/pcref/r2/nfh1_game_text.txt) and the string globals
(tools/pcref/exe/nfh1_globals.json): every call of the three-argument step
fcn.0047c290 (OBJ2 in exe_scripts.py: name, index, flags), the five-argument
fcn.0047c320 (name, index, flags, animation, actor — the animation plays inside
the step before the shout) and the four-argument fcn.0047c3b0 (name, index,
flags, a ready step), with the arguments read off the pushes and slot stores
before the call by a small stack emulation (a String argument is a reserved
slot filled through `mov eax, esp; mov [eax], value`). The index picks the
cold shout (0: shout0_light / shout0_medium / shout0 by the points, 1:
shout2); flag 2 skips the shout, flag 1 the sync step (fcn.0047bd00,
docs/PC_ROUTINES.md "The fire's tail"). A register-valued index or flags is
the level fiber's prologue constant: with --fibers the tool runs radare2 over
each such fiber (the level classes' `run`, a switch on the resume index) and
reports the last write to the register on the site's path — every site sits
in a case that never reloads it, so `mov ebx, 3` / `xor ebp, ebp` /
`xor edi, edi` stands (2026-09-22).

    python3 tools/pcref/fire_sites.py [--fibers]
"""
import re, json, os, subprocess, sys
LISTING = os.path.expanduser('~/nfh-bench/pcref/r2/nfh1_game_text.txt')
EXE = os.path.expanduser('~/nfh-bench/pcref/pc/nfh1/bin/game.exe')
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
L = open(LISTING).read().split('\n')
G = json.load(open(os.path.join(ROOT, 'tools/pcref/exe/nfh1_globals.json')))

import re, json, sys
INS = re.compile(r'^0x([0-9a-f]{8})\s+\S+\s+(.*)$')
def parse(ln):
    m = INS.match(ln)
    return (int(m.group(1), 16), m.group(2).strip()) if m else (None, None)
def sym(v):
    m = re.match(r'dword \[(0x5[0-9a-f]{5})\]', v)
    if m: return G.get(m.group(1), m.group(1))
    if re.match(r'^(0x[0-9a-f]+|\d+)$', v): return int(v, 0)
    return v
def decode(i):
    # emulate from ~60 lines back to the call at line i
    start = i - 1
    for j in range(i - 1, max(0, i - 70), -1):
        t = L[j]
        if re.search(r'call (fcn|dword)', t) and 'call dword [e' not in t:
            start = j + 1; break
    regs = {}; stack = []; ptr = {}   # ptr: reg -> stack index it points at
    for j in range(start, i):
        a, ins = parse(L[j])
        if ins is None: continue
        m = re.match(r'push (.+)$', ins)
        if m:
            v = m.group(1)
            stack.append(regs.get(v, sym(v)) if v in ('eax','ecx','edx','ebx','esi','edi','ebp') else sym(v))
            continue
        m = re.match(r'mov (eax|ecx|edx), esp$', ins)
        if m: ptr[m.group(1)] = len(stack) - 1; continue
        m = re.match(r'mov dword \[(eax|ecx|edx)\], (.+)$', ins)
        if m and m.group(1) in ptr and 0 <= ptr[m.group(1)] < len(stack):
            v = m.group(2); stack[ptr[m.group(1)]] = regs.get(v, sym(v)) if v in regs or v in ('eax','ecx','edx','ebx','esi','edi','ebp') else sym(v); continue
        m = re.match(r'mov (eax|ecx|edx|ebx|esi|edi|ebp), (.+)$', ins)
        if m:
            regs[m.group(1)] = sym(m.group(2)); continue
        m = re.match(r'lea (eax|ecx|edx), \[(.+)\]$', ins)
        if m: regs[m.group(1)] = 'addr'; continue
    return stack
def lastassign(i, reg):
    # scan back to the function prologue for the last write to reg
    pats = [re.compile(r'^(mov|xor|pop) ' + reg + r'\b'), re.compile(r'^mov ' + {'ebx':'bl','edi':'di','ebp':'bp','esi':'si'}.get(reg,'xx') + r', ')]
    for j in range(i - 1, max(0, i - 3000), -1):
        a, ins = parse(L[j])
        if ins is None: continue
        if ins.startswith('push 0xffffffffffffffff'): return 'prologue at 0x%x (no assignment)' % a
        for p in pats:
            if p.match(ins): return '0x%x %s' % (a, ins)
    return '?'
REGS = ('ebx', 'edi', 'ebp', 'esi')
KIND = {'fcn.0047c290': 'OBJ2', 'fcn.0047c320': 'FIRE5', 'fcn.0047c3b0': 'FIRE4'}
NARGS = {'OBJ2': 3, 'FIRE5': 5, 'FIRE4': 4}


def sites():
    """every fire site: (line, address, kind, args top-first, notes, reg_sites)"""
    rows = []
    for i, ln in enumerate(L):
        m = re.search(r'call (fcn\.0047c290|fcn\.0047c320|fcn\.0047c3b0)$', ln)
        if not m: continue
        a, _ = parse(ln)
        st = decode(i)
        st = st[:-1] if st and st[-1] == 'addr' else st     # the result pointer on top
        kind = KIND[m.group(1)]
        n = NARGS[kind]
        args = st[-n:] if len(st) >= n else st
        top_first = list(reversed(args))      # p1 = top (last pushed)
        notes = []; regs = []
        for k, v in enumerate(top_first):
            if v in REGS:
                notes.append('p%d=%s: %s' % (k + 1, v, lastassign(i, v)))
        for k, v in enumerate(top_first[:3]):
            if v in REGS: regs.append((a, v, top_first[0] if isinstance(top_first[0], str) else '?', k + 1))
        rows.append((i, a, kind, top_first, notes, regs))
    return rows


def main(argv):
    reg_sites = []
    for i, a, kind, top_first, notes, regs in sites():
        reg_sites.extend(regs)
        print('%08x %-5s %s %s' % (a, kind, top_first, '; '.join(notes)))
    if '--fibers' in argv:
        fibers(reg_sites)


def fibers(reg_sites):
    """the register-valued ints: the last write on the site's path inside its fiber"""
    addr2line = {}
    for i, ln in enumerate(L):
        a, _ = parse(ln)
        if a is not None: addr2line[a] = i
    def prologue(site):
        for j in range(addr2line[site], addr2line[site] - 6000, -1):
            a, ins = parse(L[j])
            if ins and ins.startswith('push 0xffffffffffffffff'): return a
    pro = {s: prologue(s) for s, r, n, k in reg_sites}
    cmds = '; '.join('af @ 0x%x; pdf @ 0x%x' % (p, p) for p in sorted(set(pro.values())))
    out = subprocess.run(['nix-shell', '-p', 'radare2', '--run', "r2 -q -e scr.color=0 -e asm.lines=false -e asm.comments=false -e asm.bytes=false -e asm.stackptr=true -e asm.var.sub=false -c '%s' %s" % (cmds, EXE)], capture_output=True, text=True).stdout.split('\n')
    pos = {}
    for i, ln in enumerate(out):
        m = re.match(r'^0x([0-9a-f]{8})\s', ln)
        if m: pos[int(m.group(1), 16)] = i
    for site, reg, name, k in reg_sites:
        p = pro[site]
        if site not in pos or p not in pos: print('%08x %s p%d=%s: not in the r2 output' % (site, name, k, reg)); continue
        short = {'ebx': 'bl', 'ebp': 'bp', 'edi': 'di', 'esi': 'si'}[reg]
        last_case = None; last_write = None; const = None
        for j in range(pos[p], pos[site] + 1):
            ln = out[j]
            if ln.startswith(';-- case'): last_case = ln[:16].strip(); last_write = None; continue
            m = re.match(r'^0x([0-9a-f]{8})\s+\S+\s+(.*)$', ln)
            if not m: continue
            ins = m.group(2).strip()
            if re.match(r'^(mov|xor|pop|lea) (%s|%s)\b' % (reg, short), ins):
                if last_case is None: const = ins
                else: last_write = ins
        print('%08x %-24s p%d=%s fiber 0x%x %s | prologue: %s | in-case: %s' % (site, name, k, reg, p, last_case, const, last_write))

if __name__ == '__main__':
    main(sys.argv[1:])
