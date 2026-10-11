"""gdb (winedbg proxy): which xdotool click pattern reaches GameLogic, and when — dummies at fixed ticks,
the loop's 'click' events logged (oracle.py's hooks without a script)"""
import os, sys
os.environ.pop('WDBG_SCRIPT', None)
exec(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'oracle.py')).read().split("gdb.Breakpoint('*0x408014')")[0])
X = T + '/xdotool-result/bin/xdotool'; env = dict(os.environ, DISPLAY=':97')
patterns = {
    100: ['mousemove', '400', '300', 'sleep', '0.3', 'click', '1'],
    200: ['mousemove', '400', '300', 'sleep', '0.6', 'click', '1'],
    300: ['click', '1'],
    400: ['click', '1'],
    500: ['mousemove', '410', '310', 'sleep', '0.3', 'mousedown', '1', 'sleep', '0.1', 'mouseup', '1'],
    600: ['mousemove', '400', '300', 'sleep', '0.3', 'mousemove', '401', '301', 'sleep', '0.3', 'click', '1'],
    700: ['mousemove', '400', '300', 'sleep', '0.3', 'click', '1', 'sleep', '0.3', 'click', '1'],
}
class Tick2(gdb.Breakpoint):
    def __init__(self): super().__init__('*%#x' % gl(0x10044234), internal=True)
    def stop(self):
        state['tick'] += 1; now = time.time(); state['last'] = now
        if state['t0'] is None: state['t0'] = now; open(HOME + '/nfh-bench/wine/logs/level_started', 'w').write('%.3f' % now)
        if state['tick'] == 20: alloc_scratch(); state['loop'].enabled = True
        if state['tick'] in patterns:
            subprocess.Popen([X] + patterns[state['tick']], env=env); emit({'tick': state['tick'], 'ev': 'dummy', 'pattern': patterns[state['tick']]})
            print('DUMMY tick %d: %s' % (state['tick'], ' '.join(patterns[state['tick']])), flush=True)
        return now - state['t0'] > secs
class Loop2(Loop):
    def stop(self):
        try:
            ebp = int(gdb.parse_and_eval('$ebp')); msg = u32(ebp - 0x14); vt = u32(msg)
            if vt in (0x453b38, 0x453b2c, 0x453b20):
                print('CLICK tick %d vt=%#x %s' % (state['tick'], vt, as_string(u32(msg + 4))), flush=True)
        except Exception as e:
            print('loop err', e, flush=True)
        return False
gdb.Breakpoint('*0x408014'); gdb.execute('continue')
ebp = int(gdb.parse_and_eval('$ebp')); sobj = u32(u32(u32(ebp + 0xc)) + 4); b, e = u32(sobj + 4), u32(sobj + 8)
if want: wr(b, want.encode('utf-16le'))
gdb.execute('delete')
lp = Loop2(); lp.enabled = False; state['loop'] = lp
Tick2()
try: gdb.execute('continue')
except Exception as ex: print('continue ended', ex)
print('done', state['tick'], flush=True)
gdb.execute('kill')
