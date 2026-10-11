"""gdb (winedbg proxy): after the level start, break in GameLogic's path finder fcn.1000a711 and print the
backtrace: how game.exe hands a floor click (GoToPosMsg) to GameLogic"""
import gdb, os, re, time, struct
port = os.environ.get('WDBG_PORT', '33333'); want = os.environ.get('WDBG_LEVEL')
HOME = os.path.expanduser('~')
gdb.execute('set pagination off'); gdb.execute('set confirm off'); gdb.execute('set architecture i386')
for sig in ('SIGABRT', 'SIGUSR1', 'SIGUSR2', 'SIGPIPE', 'SIGALRM'):
    gdb.execute('handle %s nostop noprint pass' % sig)
gdb.execute('target remote 127.0.0.1:%s' % port)
inf = gdb.selected_inferior()
rd = lambda a, n: bytes(inf.read_memory(a, n)); u32 = lambda a: struct.unpack('<I', rd(a, 4))[0]
m = re.search(r'GameLogic.dll @([0-9A-Fa-f]+)', open(HOME + '/nfh-bench/wine/logs/winedbg.log').read())
GL = int(m.group(1), 16); DELTA = GL - 0x10000000
gdb.Breakpoint('*0x408014'); gdb.execute('continue')
ebp = int(gdb.parse_and_eval('$ebp')); sobj = u32(u32(u32(ebp + 0xc)) + 4); b, e = u32(sobj + 4), u32(sobj + 8)
if want: inf.write_memory(b, want.encode('utf-16le'))
gdb.execute('delete')
# a few seconds of level before the click arms the hook (the actors' own walks use it too)
n = [0]
class Tick(gdb.Breakpoint):
    def stop(self):
        n[0] += 1
        return n[0] >= 36          # ~3 s in
tk = Tick('*%#x' % (0x10044234 + DELTA), internal=True)
gdb.execute('continue')
tk.delete()
print('armed at tick 36', flush=True)
gdb.Breakpoint('*%#x' % (0x1000a711 + DELTA))
for i in range(3):
    gdb.execute('continue')
    print('=== path finder hit %d, esp args:' % i, [hex(u32(int(gdb.parse_and_eval('$esp')) + 4 * k)) for k in range(1, 7)], flush=True)
    gdb.execute('bt 14')
gdb.execute('kill')
