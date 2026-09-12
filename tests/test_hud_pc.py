"""The PC profile's HUD and anger arithmetic, without a window: the viewer
rating's count-up queue (HUD._pc_rating_step) and the Season 1 rage rule
read from game.exe (pcprofile.s1_rage_*) — docs/PC_FIDELITY.md §7,
docs/PC_ROUTINES.md. Runs under the project's nix-shell (hud imports
sdl2): python3 -m unittest tests.test_hud_pc"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'runtime'))
import hud  # noqa: E402
import pcprofile  # noqa: E402


class _World:
    time = 0.0


def _fresh():
    h = hud.Hud.__new__(hud.Hud)
    h.world = _World()
    h._pc_last = None
    h._pc_shown = 0.0
    h._pc_t = 0.0
    h._pc_popups = []
    h._pc_gap = 0.0
    return h


def _popup_left(h):
    if not h._pc_popups:
        return None
    amount, kind, age = h._pc_popups[0]
    delay = 1.0 if kind == 'trick' else 1.2
    return amount if age < delay else amount * (1.0 - min(1.0, (age - delay) / 0.9))


class CountUp(unittest.TestCase):
    def run_to(self, h, frames, score, ticks):
        for f in range(frames):
            h.world.time += 1.0 / 60.0
            h._pc_rating_step(score, ticks)

    def test_trick_then_tick(self):
        h = _fresh()
        h._pc_rating_step(0, 0)              # the first call primes the state
        self.run_to(h, 30, 0, 0)
        self.assertEqual(h._pc_shown, 0.0)
        # a 7-point trick: the popup sits a second, then climbs over 0.9 s
        self.run_to(h, 1, 7, 0)
        self.assertEqual(len(h._pc_popups), 1)
        self.run_to(h, 57, 7, 0)             # ~0.97 s later: still static
        self.assertAlmostEqual(h._pc_shown, 0.0, places=6)
        self.assertEqual(_popup_left(h), 7.0)
        self.run_to(h, 30, 7, 0)             # half a second into the climb
        self.assertTrue(3.0 < h._pc_shown < 4.5, h._pc_shown)
        self.assertTrue(2.5 < _popup_left(h) < 4.0)
        self.run_to(h, 30, 7, 0)             # the climb is over, snapped
        self.assertEqual(h._pc_shown, 7.0)
        self.assertEqual(h._pc_popups, [])
        # a tick: orange, 1.2 s still (after the 0.2 s gap), 0.9 s climb
        self.run_to(h, 1, 7, 1)
        self.assertEqual(h._pc_popups[0][1], 'tick')
        self.run_to(h, 78, 7, 1)             # 1.3 s: gap + most of the delay
        self.assertEqual(h._pc_shown, 7.0)
        self.run_to(h, 70, 7, 1)             # 1.17 s more: climbed and snapped
        self.assertEqual(h._pc_shown, 10.0)
        self.assertEqual(h._pc_popups, [])

    def test_queue_and_cap(self):
        h = _fresh()
        h._pc_rating_step(90, 0)
        self.run_to(h, 1, 97, 1)             # a 7 and a tick at once: two popups
        self.assertEqual([p[1] for p in h._pc_popups], ['trick', 'tick'])
        self.run_to(h, 60 * 5, 97, 1)
        self.assertEqual(h._pc_shown, 100.0)  # 97 + 3, capped at 100
        self.assertEqual(h._pc_popups, [])

    def test_target_less_pending(self):
        h = _fresh()
        h._pc_rating_step(0, 0)
        self.run_to(h, 1, 8, 1)
        # the first popup converges to 8, the pending tick is not counted yet
        self.assertEqual(h._pc_target(), 8)


class Rage(unittest.TestCase):
    """game.exe's level state on the bath (level angrytime 156): the foam
    pudding (240) pins the mercury 60 + 84 ticks (12 s at the 12 Hz tick),
    drains it over 156 (13 s), and pays a bonus to any trick fired within
    300 ticks (25 s)"""
    def test_bath_foam(self):
        cur, hold = pcprofile.s1_rage_fire(0, 240)
        self.assertEqual((cur, hold), (240, 60))
        self.assertEqual(pcprofile.s1_rage_percent(cur, 156), 100)
        pinned = 0
        ticks = 0
        while cur > 0:
            cur, hold = pcprofile.s1_rage_tick(cur, hold)
            ticks += 1
            if pcprofile.s1_rage_percent(cur, 156) == 100:
                pinned += 1
        self.assertEqual(ticks, 300)               # 60 + 240: 25 s above zero
        self.assertEqual(pcprofile.S1_TICK_HZ, 12)
        self.assertEqual(pinned, 60 + (240 - 156) - 1 + 1)   # 144 ticks full
        self.assertEqual(pcprofile.s1_rage_percent(0, 156), 0)

    def test_level_value_and_max(self):
        # a trick without its own value takes the level's; a second trick
        # never lowers the current, only restarts the hold
        cur, hold = pcprofile.s1_rage_fire(0, 156)
        for _ in range(100):
            cur, hold = pcprofile.s1_rage_tick(cur, hold)
        self.assertEqual((cur, hold), (116, 0))
        self.assertEqual(pcprofile.s1_rage_percent(cur, 156), 74)   # 116*100//156
        cur, hold = pcprofile.s1_rage_fire(cur, 100)
        self.assertEqual((cur, hold), (116, 60))
        self.assertTrue(cur > 0)                    # the bonus test


if __name__ == '__main__':
    unittest.main()
