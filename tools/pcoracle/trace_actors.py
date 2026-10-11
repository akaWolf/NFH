"""gdb (winedbg proxy): find the actor struct's position fields — capture each actor's object from the path
finder's args, then dump its first 0x90 bytes every 6 ticks to ~/nfh-bench/wine/logs/actors.jsonl"""
import gdb, os, re, time, struct, json
port = os.environ.get('WDBG_PORT', '33333'); want = os.environ.get('WDBG_LEVEL'); secs = float(os.environ.get('WDBG_SECS', '30'))
HOME = os.path.expanduser('~')
gdb.execute('set pagination off'); gdb.execute('set confirm off'); gdb.execute('set architecture i386')
for sig in ('SIGABRT', 'SIGUSR1', 'SIGUSR2', 'SIGPIPE', 'SIGALRM'):
    gdb.execute('handle %s nostop noprint pass' % sig)
gdb.execute('target remote 127.0.0.1:%s' % port)
inf = gdb.selected_inferior()
def rd(a, n): return bytes(inf.read_memory(a, n))
def u32(a): return struct.unpack('<I', rd(a, 4))[0]
m = re.search(r'GameLogic.dll @([0-9A-Fa-f]+)', open(HOME + '/nfh-bench/wine/logs/winedbg.log').read())
GL = int(m.group(1), 16); DELTA = GL - 0x10000000
def as_string(p):
    try:
        if p < 0x10000 or p > 0x7fffffff: return None
        vt, b, e = struct.unpack('<III', rd(p, 12))
        if not (0x10000 < b <= e < 0x7fffffff and (e - b) % 2 == 0 and e - b <= 160): return None
        if not (0x400000 <= vt < 0x7f000000): return None
        s = rd(b, e - b).decode('utf-16le')
        return s if all(0x20 <= ord(c) < 0x7f for c in s) else None
    except Exception:
        return None
actors = {}
log = open(HOME + '/nfh-bench/wine/logs/actors.jsonl', 'w')
state = {'tick': 0, 't0': None}
class Path(gdb.Breakpoint):
    def __init__(self): super().__init__('*%#x' % (0x1000a711 + DELTA), internal=True)
    def stop(self):
        try:
            esp = int(gdb.parse_and_eval('$esp')); a = u32(esp + 8)
            name = as_string(u32(a + 4))
            if name and name not in actors:
                actors[name] = a; print('actor', name, hex(a), flush=True)
        except Exception as e:
            print('path err', e, flush=True)
        return False
class Tick(gdb.Breakpoint):
    def __init__(self): super().__init__('*%#x' % (0x10044234 + DELTA), internal=True)
    def stop(self):
        state['tick'] += 1
        now = time.time()
        if state['t0'] is None: state['t0'] = now
        if state['tick'] % 6 == 0:
            for name, a in actors.items():
                try:
                    log.write(json.dumps({'tick': state['tick'], 'actor': name, 'words': list(struct.unpack('<36I', rd(a, 144)))}) + '\n')
                except Exception as e:
                    pass
            log.flush()
        return now - state['t0'] > secs
gdb.Breakpoint('*0x408014'); gdb.execute('continue')
ebp = int(gdb.parse_and_eval('$ebp')); sobj = u32(u32(u32(ebp + 0xc)) + 4); b, e = u32(sobj + 4), u32(sobj + 8)
if want: inf.write_memory(b, want.encode('utf-16le'))
gdb.execute('delete')
Path(); Tick()
gdb.execute('continue')
print('done ticks', state['tick'], 'actors', list(actors), flush=True)
gdb.execute('kill')
