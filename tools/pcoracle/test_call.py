"""gdb (winedbg proxy): can gdb call functions in the inferior? at the first level tick, call game.exe's
GetTickCount thunk (0x4108e0) and kernel32!VirtualAlloc through the IAT"""
import gdb, os, re, struct, time
port = os.environ.get('WDBG_PORT', '33333'); want = os.environ.get('WDBG_LEVEL')
HOME = os.path.expanduser('~')
gdb.execute('set pagination off'); gdb.execute('set confirm off'); gdb.execute('set architecture i386')
for sig in ('SIGABRT', 'SIGUSR1', 'SIGUSR2', 'SIGPIPE', 'SIGALRM'):
    gdb.execute('handle %s nostop noprint pass' % sig)
gdb.execute('target remote 127.0.0.1:%s' % port)
inf = gdb.selected_inferior()
rd = lambda a, n: bytes(inf.read_memory(a, n)); u32 = lambda a: struct.unpack('<I', rd(a, 4))[0]
m = re.search(r'GameLogic.dll @([0-9A-Fa-f]+)', open(HOME + '/nfh-bench/wine/logs/winedbg.log').read())
DELTA = int(m.group(1), 16) - 0x10000000
gdb.Breakpoint('*0x408014'); gdb.execute('continue')
ebp = int(gdb.parse_and_eval('$ebp')); sobj = u32(u32(u32(ebp + 0xc)) + 4); b, e = u32(sobj + 4), u32(sobj + 8)
if want: inf.write_memory(b, want.encode('utf-16le'))
gdb.execute('delete')
gdb.Breakpoint('*%#x' % (0x10044234 + DELTA)); gdb.execute('continue'); gdb.execute('delete')
print('at the tick, pc', hex(gdb.selected_frame().pc()), flush=True)
try:
    v = gdb.parse_and_eval('((unsigned int (*)())0x4108e0)()')
    print('GetTickCount via call:', int(v), flush=True)
except Exception as ex:
    print('call failed:', repr(ex), flush=True)
try:
    # kernel32!VirtualAlloc from game.exe's import table
    txt = gdb.execute('info functions VirtualAlloc', to_string=True)
    print(txt[:300], flush=True)
    va = int(gdb.parse_and_eval('(unsigned int)&VirtualAlloc')) if 'VirtualAlloc' in txt else None
    if va:
        p = gdb.parse_and_eval('((unsigned int (*)(unsigned int, unsigned int, unsigned int, unsigned int))%#x)(0, 65536, 0x3000, 0x40)' % va)
        print('VirtualAlloc ->', hex(int(p)), flush=True)
        inf.write_memory(int(p), 'hello'.encode('utf-16le'))
        print('scratch readback', rd(int(p), 10), flush=True)
except Exception as ex:
    print('VirtualAlloc failed:', repr(ex), flush=True)
gdb.execute('kill')
