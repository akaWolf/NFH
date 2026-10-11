"""gdb (winedbg proxy): message rewriting at GameLogic's message loop (GL+0x10044464, the Msg in [ebp-0x14]).
A dummy click's message (GoToPosMsg vt game.exe 0x453b38: +4 String* room, +0xc x, +0x10 y; UseObjectMsg:
captured here) is rewritten into the wanted one. Scratch memory from kernel32!VirtualAlloc through game.exe's
IAT slot 0x452108. Experiment: tick 30 click the cool box -> dump UseObjectMsg; tick ~100 click it again ->
name rewritten to shop/waste (a take); then the inventory slot + the cool box -> the use message"""
import gdb, os, re, time, struct, json
port = os.environ.get('WDBG_PORT', '33333'); want = os.environ.get('WDBG_LEVEL'); secs = float(os.environ.get('WDBG_SECS', '60'))
HOME = os.path.expanduser('~')
gdb.execute('set pagination off'); gdb.execute('set confirm off'); gdb.execute('set architecture i386')
for sig in ('SIGABRT', 'SIGUSR1', 'SIGUSR2', 'SIGPIPE', 'SIGALRM'):
    gdb.execute('handle %s nostop noprint pass' % sig)
gdb.execute('target remote 127.0.0.1:%s' % port)
inf = gdb.selected_inferior()
def rd(a, n): return bytes(inf.read_memory(a, n))
def wr(a, b): inf.write_memory(a, b)
def u32(a): return struct.unpack('<I', rd(a, 4))[0]
lg = open(HOME + '/nfh-bench/wine/logs/winedbg.log').read()
GL = int(re.search(r'GameLogic.dll @([0-9A-Fa-f]+)', lg).group(1), 16); DELTA = GL - 0x10000000
def as_string(p):
    try:
        if p < 0x10000 or p > 0x7fffffff: return None
        vt, b, e = struct.unpack('<III', rd(p, 12))
        if not (0x10000 < b <= e < 0x7fffffff and (e - b) % 2 == 0 and e - b <= 200): return None
        if not (0x400000 <= vt < 0x7f000000): return None
        return rd(b, e - b).decode('utf-16le', 'replace')
    except Exception:
        return None
scratch = {'base': None, 'pos': 0}
def alloc_scratch():
    va = u32(0x452108)
    p = int(gdb.parse_and_eval('((unsigned int (*)(unsigned int, unsigned int, unsigned int, unsigned int))%#x)(0, 65536, 0x3000, 0x40)' % va))
    scratch['base'] = p; print('scratch at %#x' % p, flush=True)
def salloc(n):
    p = scratch['base'] + scratch['pos']; scratch['pos'] += (n + 15) & ~15; return p
def make_string(text, proto):
    """a String object like `proto` (its 16 bytes copied) whose text is `text`"""
    data = text.encode('utf-16le') + b'\0\0'
    buf = salloc(len(data)); wr(buf, data)
    obj = salloc(16); wr(obj, rd(proto, 16))
    wr(obj + 4, struct.pack('<II', buf, buf + len(data) - 2))
    return obj
def retext(sobj, text):
    """point an existing String object at new text"""
    data = text.encode('utf-16le') + b'\0\0'
    buf = salloc(len(data)); wr(buf, data)
    wr(sobj + 4, struct.pack('<II', buf, buf + len(data) - 2))
state = {'tick': 0, 't0': None, 'plan': []}
out = open(HOME + '/nfh-bench/wine/logs/inject.jsonl', 'w')
def dump(msg, tag):
    words = struct.unpack('<16I', rd(msg, 64))
    fields = {}
    for i, w in enumerate(words):
        s = as_string(w)
        if s is not None: fields['+%#x' % (4 * i)] = s
    rec = {'tick': state['tick'], 'tag': tag, 'msg': '%#x' % msg, 'words': ['%#x' % w for w in words[:12]], 'strings': fields}
    out.write(json.dumps(rec) + '\n'); out.flush(); print(json.dumps(rec)[:300], flush=True)
    return words, fields
class Tick(gdb.Breakpoint):
    def __init__(self): super().__init__('*%#x' % (0x10044234 + DELTA), internal=True)
    def stop(self):
        state['tick'] += 1; now = time.time()
        if state['t0'] is None:
            state['t0'] = now
            open(HOME + '/nfh-bench/wine/logs/level_started', 'w').write('%.3f' % now)
        if state['tick'] % 12 == 0: out.write(json.dumps({'tick': state['tick'], 'wall': now}) + '\n')
        if state['tick'] == 20:
            alloc_scratch()
            state['loop'].enabled = True
        return now - state['t0'] > secs
class Loop(gdb.Breakpoint):
    def __init__(self): super().__init__('*%#x' % (0x10044464 + DELTA), internal=True)
    def stop(self):
        try:
            ebp = int(gdb.parse_and_eval('$ebp')); msg = u32(ebp - 0x14)
            vt = u32(msg)
            if vt == 0x453b38:            # GoToPosMsg
                words, fields = dump(msg, 'goto')
            else:
                words, fields = dump(msg, 'other')
                # a UseObjectMsg (its name String at the first String field): the second one is rewritten
                names = [k for k, v in fields.items() if '/' in v]
                target = os.environ.get('WDBG_REWRITE')
                if names and target and not state.get('rewrote'):
                    off = int(names[0][1:], 16)
                    retext(u32(msg + off), target)
                    state['rewrote'] = state['tick']
                    print('REWROTE %s -> %s at tick %d' % (names[0], target, state['tick']), flush=True)
        except Exception as e:
            print('loop err', repr(e), flush=True)
        return False
gdb.Breakpoint('*0x408014'); gdb.execute('continue')
ebp = int(gdb.parse_and_eval('$ebp')); sobj = u32(u32(u32(ebp + 0xc)) + 4); b, e = u32(sobj + 4), u32(sobj + 8)
if want: wr(b, want.encode('utf-16le'))
gdb.execute('delete')
class Act(gdb.Breakpoint):
    def __init__(self): super().__init__('*%#x' % (0x10002cd5 + DELTA), internal=True)
    def stop(self):
        try:
            esp = int(gdb.parse_and_eval('$esp'))
            a1, a2 = as_string(u32(esp + 8)), as_string(u32(esp + 12))
            if state['tick'] > 20 and (a1 == 'woody' or (a2 and a2 not in ('enter', 'leave', 'use', 'start'))):
                print('ACTION tick %d: %s %s' % (state['tick'], a1, a2), flush=True)
        except Exception: pass
        return False
lp = Loop(); lp.enabled = False; state['loop'] = lp
Act(); Tick()
gdb.execute('continue')
print('done ticks', state['tick'], flush=True)
gdb.execute('kill')
