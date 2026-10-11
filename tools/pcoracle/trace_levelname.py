"""gdb (winedbg proxy): at game.exe's level-session start (0x408014, call fcn.00407456) read the level-name
String ([[arg_ch]]+4: {vtable, begin, end}) and, with WDBG_LEVEL set, overwrite it (same length) so that
level loads instead; then let it run"""
import gdb, os, time, struct
port = os.environ.get('WDBG_PORT', '33333'); want = os.environ.get('WDBG_LEVEL')
gdb.execute('set pagination off'); gdb.execute('set confirm off'); gdb.execute('set architecture i386')
for sig in ('SIGABRT', 'SIGUSR1', 'SIGUSR2', 'SIGPIPE', 'SIGALRM'):
    gdb.execute('handle %s nostop noprint pass' % sig)
gdb.execute('target remote 127.0.0.1:%s' % port)
inf = gdb.selected_inferior()
rd = lambda a, n: bytes(inf.read_memory(a, n))
u32 = lambda a: struct.unpack('<I', rd(a, 4))[0]
gdb.Breakpoint('*0x408014')
t0 = time.time()
gdb.execute('continue')
print('STOP at %s after %.1fs' % (hex(gdb.selected_frame().pc()), time.time() - t0), flush=True)
ebp = int(gdb.parse_and_eval('$ebp'))
obj = u32(u32(ebp + 0xc)); sobj = u32(obj + 4)
begin, end = u32(sobj + 4), u32(sobj + 8)
name = rd(begin, end - begin).decode('utf-16le')
print('level name String @%#x: begin=%#x end=%#x -> %r' % (sobj, begin, end, name), flush=True)
if want and len(want) == len(name):
    inf.write_memory(begin, want.encode('utf-16le'))
    print('patched to', rd(begin, end - begin).decode('utf-16le'), flush=True)
gdb.execute('delete')
gdb.execute('continue')
