"""The PC profile's HUD arithmetic, without a window: the viewer rating's
count-up queue (HUD._pc_rating_step) and the thermometer's drawn drain —
docs/PC_FIDELITY.md §7. Runs under the project's nix-shell (hud imports
sdl2): python3 -m unittest tests.test_hud_pc"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'runtime'))
import hud  # noqa: E402


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


class Thermometer(unittest.TestCase):
    """the drawn meter's rule as _draw_angry_meter applies it: full while
    the tick meter is full, then the level's drain per second"""
    def test_drain(self):
        shown = 0.0
        drain = 12.9
        full = 100.0
        def step(meter, dt):
            nonlocal shown
            if meter >= full - 1e-6:
                shown = 100.0
            else:
                shown = max(0.0, shown - drain * dt)
            return shown
        self.assertEqual(step(100.0, 1 / 60.0), 100.0)      # the trick
        self.assertEqual(step(100.0, 1 / 60.0), 100.0)      # the hold
        for _ in range(60):
            step(99.0, 1 / 60.0)                            # a second of drain
        self.assertAlmostEqual(shown, 100.0 - drain, places=3)
        for _ in range(60 * 8):
            step(50.0, 1 / 60.0)
        self.assertEqual(shown, 0.0)                        # empty in 7.8 s
        self.assertEqual(step(100.0, 1 / 60.0), 100.0)      # the next trick


if __name__ == '__main__':
    unittest.main()
