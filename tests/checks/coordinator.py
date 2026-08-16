"""The coordinator's own guards from the final audit: the music anchor
(pass 5 F1), the stand switch after a single with a callback (pass 5 F2),
and the dexterity 'done' tail routing (pass 1 pawn/items hand-off)."""
import json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, 'runtime'))


def run(record, check, outdir):
    ok = True
    os.environ.setdefault('SDL_VIDEODRIVER', 'offscreen')
    from scene import Level
    from world import World

    # -- F1: the level track is anchored at the scene load, intro_total
    #    before the port's t=0 (Level.cs:295-297, MusicPlayer.cs:71-81,
    #    IntroAnimation.cs:86-112): 15 - 7.79 = 7.21 s on Level101 -------
    lv = Level(os.path.join(ROOT, 'levels/s1/Level101.json'))
    ok &= check('coordinator: intro cards total 7.79 s',
                abs((lv.music or {}).get('intro_total', 0) - 7.79) < 0.02,
                (lv.music or {}).get('intro_total'))
    ok &= check('coordinator: EntranceSound clip resolved',
                (lv.music or {}).get('entrance') == 'levelstart',
                (lv.music or {}).get('entrance'))

    class _Bank:
        """a recording stand-in for the SoundBank"""
        def __init__(self):
            self.calls = []

        def play_music(self, name, loop=True, offset=0.0):
            self.calls.append(('music', name, loop, round(offset, 2)))

        def play_entrance(self, name):
            self.calls.append(('entrance', name))

        def stop_music(self):
            self.calls.append(('stop',))

    bank = _Bank()
    w = World(lv, music=bank)
    ok &= check('coordinator: clap resumes 7.79 s in, entrance at t=0',
                ('music', 'jingle_levelstart', False, 7.79) in bank.calls
                and ('entrance', 'levelstart') in bank.calls, bank.calls)
    ok &= check('coordinator: track armed at 15 - 7.79 s',
                w._music_timer is not None and abs(w._music_timer - 7.21) < 0.02,
                w._music_timer)

    # -- F2: a blocking single with a callback stands the pawn in the same
    #    Refresh when the delegates start nothing (StopSingleAnimation,
    #    AnimationControllerBase.cs:234-240; Woody.cs:343-353): the Hello's
    #    end shows Stand_Down on the very tick, no past-the-end cell ------
    st = record('levels/s1/Level101.json', os.path.join(outdir, 'hello'),
                'wait 5\n', 5, fps=0)
    anims = [s['woody']['anim'] for s in st]
    i = max(i for i, a in enumerate(anims) if a == 'Hello')
    ok &= check('coordinator: Hello -> Stand_Down on the next tick',
                i + 1 < len(anims) and anims[i + 1] == 'Stand_Down',
                anims[i:i + 3])
    ok &= run_colliders(record, check, outdir)
    ok &= run_refusals(record, check, outdir)
    return ok


def run_colliders(record, check, outdir):
    """a BoxCollider with a negative serialized size is the same solid for
    Physics.Raycast (half-extents are magnitudes) — L106's Pudding (height
    < 0) and L210's ElephantCricketBat (width < 0) must have a hit box"""
    from scene import Level
    ok = True
    for lv, name in (('levels/s1/Level106.json', 'Pudding'),
                     ('levels/s2/Level210.json', 'ElephantCricketBat')):
        L = Level(os.path.join(ROOT, lv))
        it = next(i for i in L.items.values() if i.name == name)
        c = it.collider
        ok &= check('coordinator: %s hit box positive' % name,
                    c is not None and c[2] > 0.1 and c[3] > 0.1, c)
    return ok


def run_refusals(record, check, outdir):
    """StartMoveToLocation's else (Woody.cs:736-741): a click MoveToLocation
    refuses — no zone under it here — drops the latched tooltip and the
    used inventory and keeps the old route"""
    st = record('levels/s1/Level101.json', os.path.join(outdir, 'refuse'),
                'wait 4\nclickitem Drawer\nwait 5\ninv 1\n'
                'mouseitem Microwave\nwait 2\nclick 20 20\nwait 1\n',
                13, fps=0)
    tail = st[-1]
    hud = tail.get('hud') or {}
    return check('coordinator: a no-zone click clears the latch',
                 not hud.get('colored'), hud)
