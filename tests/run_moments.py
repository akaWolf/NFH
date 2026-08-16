"""The moment suite: replay each scripted moment through runtime/record.py
and assert the class of behaviour it was written to guard — the pass-4 rule
that every caught divergence turns into a repeatable check.

    python3 tests/run_moments.py [outdir]

Each case records into <outdir>/<name> (frames + state.jsonl) and the
asserts run over state.jsonl.
"""
import json, os, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REC = os.path.join(ROOT, 'runtime', 'record.py')


def record(level, out, script_text, seconds, fps=1):
    os.makedirs(out, exist_ok=True)
    sp = os.path.join(out, 'script.txt')
    open(sp, 'w').write(script_text)
    env = dict(os.environ, SDL_VIDEODRIVER='offscreen')
    subprocess.run([sys.executable, REC, os.path.join(ROOT, level), out,
                    '--script=' + sp, '--seconds=%s' % seconds,
                    '--fps=%s' % fps],
                   check=True, env=env, capture_output=True)
    return [json.loads(l) for l in open(os.path.join(out, 'state.jsonl'))]


def check(name, cond, detail=''):
    status = 'ok' if cond else 'FAIL'
    print('%-38s %s %s' % (name, status, detail if not cond else ''))
    return cond


def main(outdir):
    ok = True

    # -- entrance: the walk-in, the Hello greeting, the delayed routine ----
    st = record('levels/s1/Level101.json', os.path.join(outdir, 'entrance'),
                'wait 6\n', 6)
    anims = [s['woody']['anim'] for s in st]
    unlock_t = next((s['t'] for s in st if not s['woody']['locked']), None)
    hello_t = next((s['t'] for s in st if s['woody']['anim'] == 'Hello'), None)
    routine_start = next((s['t'] for s in st
                          if s['routines'][0]['state'] != 'idle'), None)
    ok &= check('entrance: Hello plays', hello_t is not None)
    ok &= check('entrance: unlock after Hello',
                unlock_t is not None and hello_t is not None
                and unlock_t > hello_t, '%s vs %s' % (unlock_t, hello_t))
    ok &= check('entrance: routine DelayStart 1.5s',
                routine_start is not None and 1.4 <= routine_start <= 1.7,
                routine_start)

    # -- tooltips: hover text, the held-inventory line, the miss reset -----
    st = record('levels/s1/Level101.json', os.path.join(outdir, 'tooltips'),
                'wait 4\nclickitem Drawer\nwait 5\ninv 1\n'
                'mouseitem Microwave\nwait 3\nclickworld 0.0 0.5\nwait 1\n',
                14)
    tips = [((s.get('hud') or {}).get('tooltip') or '') for s in st]
    ok &= check('tooltips: UseWith line',
                any(t.startswith('Use ') and ' with ' in t for t in tips))
    ok &= check('tooltips: hover text seen',
                any(t and not t.startswith('Use ') for t in tips))
    ok &= check('tooltips: miss clears the held item',
                st[-1]['hud'] is not None
                and not (st[-1].get('hud') or {}).get('colored'))

    # -- the description bubble on a refused click -------------------------
    st = record('levels/s1/Level101.json', os.path.join(outdir, 'bubble'),
                'wait 4\nclickitem Microwave\nwait 5\n', 10)
    ok &= check('bubble: refusal speaks',
                any((s.get('hud') or {}).get('bubble') for s in st))

    # -- the catch: fear, the hit set, the hidden sprite, the score --------
    st = record('levels/s1/Level101.json', os.path.join(outdir, 'catch'),
                'wait 4\nclickworld 4.0 1.2\nwait 40\n', 45)
    caught_t = next((s['t'] for s in st if s['game']['caught']), None)
    ok &= check('catch: caught', caught_t is not None)
    if caught_t is not None:
        after = [s for s in st if s['t'] >= caught_t]
        ok &= check('catch: Woody fears',
                    any(s['woody']['anim'].startswith('Fear') for s in after))
        ok &= check('catch: a hit sequence plays',
                    any(s['routines'][0]['anim'].endswith('Woody')
                        for s in after))
        ok &= check('catch: Woody hides for the beating',
                    any(s['woody']['sprite_hidden'] for s in after))

    # -- the sleep bar: fills for the span of its sequence window ----------
    # The bed's use sequence is BedIn + 30 BedSleep (2 frames at 2 fps);
    # inside a sequence every element costs exactly 1/FrameRate per frame
    # (ResetAnimationTime after the switch, AnimationControllerBase.cs:
    # 103-141, 380), 1.0 s each. The bar counts indices [2, 31) —
    # 29 elements, 29 s — against its 29.3 s Duration denominator
    # (ProgressBar.cs:147-160), so it reads ~99% and hides as the sleep
    # ends. (An earlier build ticked every pawn controller twice per
    # frame — the sleep took 14.7 s and the bar showed ~50%; that number
    # was the bug, not the design.)
    st = record('levels/s1/Level109.json', os.path.join(outdir, 'sleep'),
                'wait 40\n', 40, fps=0.5)
    bar_t = [s['t'] for s in st if s.get('bars')]
    seen = [s['bars'][0]['progress'] for s in st if s.get('bars')]
    span = (bar_t[-1] - bar_t[0]) if bar_t else None
    ok &= check('sleep bar: fills', bool(seen) and max(seen) > 0.95,
                max(seen) if seen else None)
    ok &= check('sleep bar: 29 x 1.0 s window (+/-0.5)',
                span is not None and 28.6 <= span <= 29.7, span)
    ok &= check('sleep bar: hides when the sleep ends',
                bool(bar_t) and not st[-1].get('bars'))

    # -- the win: forcewin -> the 2.5s wait -> WinAnimation -> score -------
    st = record('levels/s1/Level101.json', os.path.join(outdir, 'win'),
                'wait 4\nforcewin\nwait 10\n', 14)
    ok &= check('win: game ends', st[-1]['game']['ending'])
    ok &= check('win: WinAnimation plays',
                any(s['woody']['anim'] == 'WinGame' for s in st))

    # -- the pause: the power click freezes the clock ----------------------
    st = record('levels/s1/Level101.json', os.path.join(outdir, 'pause'),
                'wait 4\nclick 685 575\nwait 3\nclick 685 575\nwait 2\n', 9)
    t5 = next(s['game']['time'] for s in st if abs(s['t'] - 5.0) < 0.01)
    t7 = next(s['game']['time'] for s in st if abs(s['t'] - 6.9) < 0.01)
    ok &= check('pause: the clock freezes', abs(t5 - t7) < 0.2,
                '%s vs %s' % (t5, t7))

    # -- the per-area check modules (tests/checks/*.py): each exposes
    #    run(record, check, outdir) -> bool and guards the class of
    #    divergence its audit pass caught
    import glob, importlib.util
    for path in sorted(glob.glob(os.path.join(ROOT, 'tests', 'checks',
                                              '*.py'))):
        name = os.path.splitext(os.path.basename(path))[0]
        if name.startswith('_'):
            continue
        spec = importlib.util.spec_from_file_location('checks_' + name, path)
        mod = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(mod)
            ok &= bool(mod.run(record, check, os.path.join(outdir, name)))
        except Exception as e:           # a broken module is a failure
            print('%-38s FAIL %s' % ('checks/%s: crashed' % name, e))
            ok = False

    print('---')
    print('moments:', 'ALL OK' if ok else 'FAILURES')
    return 0 if ok else 1


if __name__ == '__main__':
    out = sys.argv[1] if len(sys.argv) > 1 else tempfile.mkdtemp(
        prefix='nfh-moments-')
    sys.exit(main(out))
