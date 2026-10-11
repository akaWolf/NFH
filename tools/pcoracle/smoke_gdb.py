"""gdb spike 5: through winedbg's gdb proxy — break at game.exe's GetCommandLineA call, then user32!MessageBoxA"""
import gdb, time, sys, os
port = os.environ.get('WDBG_PORT', '33333')
gdb.execute('set pagination off'); gdb.execute('set confirm off')
gdb.execute('set architecture i386')
for sig in ('SIGABRT', 'SIGSEGV', 'SIGUSR1', 'SIGUSR2', 'SIGPIPE', 'SIGALRM', 'SIGTRAP'):
    pass
for sig in ('SIGABRT', 'SIGUSR1', 'SIGUSR2', 'SIGPIPE', 'SIGALRM'):
    gdb.execute('handle %s nostop noprint pass' % sig)
t0 = time.time()
gdb.execute('target remote 127.0.0.1:%s' % port)
print('connected after %.1fs pc=%s' % (time.time() - t0, hex(gdb.selected_frame().pc())), flush=True)
inf = gdb.selected_inferior()
def rd(a, n): return bytes(inf.read_memory(a, n))
print('game.exe @0x400000:', rd(0x400000, 2), flush=True)
gdb.Breakpoint('*0x43229d')
gdb.execute('continue')
print('STOP1 after %.1fs pc=%s' % (time.time() - t0, hex(gdb.selected_frame().pc())), flush=True)
import re
m = re.search(r'GameLogic.dll @([0-9A-Fa-f]+)', open(os.path.expanduser('~/nfh-bench/wine/logs/winedbg.log')).read())
glb = int(m.group(1), 16) if m else None
print('GameLogic base %s: %r' % (hex(glb) if glb else None, rd(glb, 2) if glb else None), flush=True)
mb = int.from_bytes(rd(0x4521e8, 4), 'little')
print('IAT MessageBoxA -> %#x' % mb, flush=True)
gdb.execute('delete')
gdb.Breakpoint('*%#x' % mb)
gdb.execute('continue')
sp = int(gdb.parse_and_eval('$esp'))
text = int.from_bytes(rd(sp + 8, 4), 'little'); cap = int.from_bytes(rd(sp + 12, 4), 'little')
cstr = lambda a: rd(a, 120).split(b'\0')[0].decode('latin-1')
print('STOP2 MessageBoxA after %.1fs: caption=%r text=%r' % (time.time() - t0, cstr(cap), cstr(text)), flush=True)
gdb.execute('info threads')
gdb.execute('kill')
