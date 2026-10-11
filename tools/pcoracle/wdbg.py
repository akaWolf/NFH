"""drive: Xvfb + wineserver + winedbg --gdb proxy on game.exe + a gdb python script; hard cleanup"""
import os, signal, socket, subprocess, sys, time
HOME = os.path.expanduser('~')
W = '/nix/store/4p6dqsj06jv2fqraf80xkqcjr5hz7nhv-wine-wow-10.0/bin/'
GDB = os.environ.get('NFH_GDB') or os.path.join(os.path.dirname(os.path.abspath(__file__)), 'gdb-result/bin/gdb')
GAME = sys.argv[1]; SCRIPT = sys.argv[2]; TIMEOUT = float(sys.argv[3]) if len(sys.argv) > 3 else 120
DISP = ':97'; PORT = 33333
env = dict(os.environ, WINEPREFIX=HOME + '/nfh-bench/wine/nfh', WINEDLLOVERRIDES='mscoree,mshtml=', WINEDEBUG=os.environ.get('WDBG_WINEDEBUG', '-all'), DISPLAY=DISP)
logs = HOME + '/nfh-bench/wine/logs/'
try: os.remove(logs + 'level_started')
except OSError: pass
procs = []
def start(cmd, name, **kw):
    f = open(logs + name + '.log', 'w')
    p = subprocess.Popen(cmd, stdout=f, stderr=subprocess.STDOUT, env=env, start_new_session=True, **kw)
    procs.append(p); return p
def listening(port):
    s = socket.socket(); s.settimeout(0.5)
    try: s.connect(('127.0.0.1', port)); s.close(); return True
    except Exception: return False
try:
    start(['Xvfb', DISP, '-screen', '0', os.environ.get('WDBG_SCREEN', '800x600x24'), '+extension', 'GLX'], 'xvfb'); time.sleep(1.5)
    subprocess.run([W + 'wineserver', '-p'], env=env, timeout=30)
    cwd = HOME + '/nfh-bench/wine/%sgame/bin' % GAME
    # (split on blanks, not shlex: a Windows path's backslashes are no escapes)
    cmd = (os.environ.get('WDBG_CMD') or (W + 'winedbg --gdb --no-start --port %d game.exe' % PORT)).split()
    wd = start(cmd, 'winedbg', cwd=cwd)
    t0 = time.time()
    ready = False
    # (no TCP probe: the proxy accepts one connection, gdb's)
    while time.time() - t0 < 60 and not ready:
        if wd.poll() is not None: break
        ready = 'target remote' in open(logs + 'winedbg.log').read()
        time.sleep(0.3)
    print('winedbg: rc=%s ready=%s after %.1fs' % (wd.poll(), ready, time.time() - t0), flush=True)
    if ready:
        genv = dict(env, WDBG_PORT=str(PORT))
        g = subprocess.Popen([GDB, '-q', '-batch', '-x', SCRIPT], env=genv, start_new_session=True,
                             stdout=open(logs + 'gdbclient.log', 'w'), stderr=subprocess.STDOUT)
        procs.append(g)
        clicks = os.environ.get('WDBG_CLICKS')
        if clicks:
            # the menu walk alongside gdb (the game's window, the cursor mapping of menuwalk.sh)
            T = os.path.dirname(os.path.abspath(__file__))
            c = subprocess.Popen(['sh', T + '/clicks.sh', GAME, clicks], env=env, start_new_session=True,
                                 stdout=open(logs + 'clicks.log', 'w'), stderr=subprocess.STDOUT)
            procs.append(c)
        try: g.wait(timeout=TIMEOUT)
        except subprocess.TimeoutExpired: print('gdb client timed out', flush=True)
        print(open(logs + 'gdbclient.log').read()[-3000:], flush=True)
finally:
    for p in procs[::-1]:
        try: os.killpg(p.pid, signal.SIGKILL)
        except Exception: pass
    try: subprocess.run([W + 'wineserver', '-k9'], env=env, timeout=15)
    except Exception: subprocess.run(['pkill', '-9', 'wineserver'])
    # (Wine rewrites its processes' argv to the Windows paths — winedevice.exe, game.exe —, and with the
    # server gone -k9 reaches none of them: every process of this prefix is found by its environment)
    for pid in os.listdir('/proc'):
        if not pid.isdigit(): continue
        try:
            envb = open('/proc/%s/environ' % pid, 'rb').read()
        except Exception:
            continue
        if ('WINEPREFIX=' + env['WINEPREFIX']).encode() in envb and int(pid) != os.getpid():
            try: os.kill(int(pid), signal.SIGKILL)
            except Exception: pass
