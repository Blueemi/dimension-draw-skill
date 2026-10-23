"""Unit tests for the dimdraw library (stdlib unittest, no dependencies).

usage: python3 -m unittest discover -s tests -v
"""

import math
import os
import random
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..",
                                "skills", "dimensional-drawing", "scripts"))

from dimdraw import Model, Sheet, spline  # noqa: E402


def save_quietly(sh):
    out = tempfile.mkdtemp(prefix="dimdraw-test-")
    stdout = sys.stdout
    sys.stdout = open(os.devnull, "w")
    try:
        return sh.save(os.path.join(out, "t.svg"), png=False)
    finally:
        sys.stdout.close()
        sys.stdout = stdout


def messages(problems, level):
    return [p["msg"] for p in problems if p["level"] == level]


class SplineTest(unittest.TestCase):
    def test_passes_through_points_without_overshoot(self):
        rnd = random.Random(3)
        for _ in range(200):
            pts = sorted((i * rnd.uniform(5, 40), rnd.uniform(-50, 50)) for i in range(1, 7))
            curve = spline(pts, per_segment=20)
            for p in pts:
                self.assertLess(min(math.dist(p, q) for q in curve), 1e-9)
            for a, b in zip(pts, pts[1:]):
                span = [q for q in curve if a[0] - 1e-9 <= q[0] <= b[0] + 1e-9]
                lo, hi = min(a[1], b[1]), max(a[1], b[1])
                for q in span:
                    self.assertGreaterEqual(q[1], lo - 1e-9)
                    self.assertLessEqual(q[1], hi + 1e-9)

    def test_closed_extremes_are_control_points(self):
        c = spline([(0, 0), (10, 5), (0, 10), (-10, 5)], closed=True, per_segment=16)
        self.assertAlmostEqual(max(p[0] for p in c), 10.0)
        self.assertAlmostEqual(min(p[0] for p in c), -10.0)
        self.assertAlmostEqual(max(p[1] for p in c), 10.0)


class ModelTest(unittest.TestCase):
    def test_line_on_follows_the_surface(self):
        m = Model("t")
        ball = m.sphere((0, 0, 0), 50, segments=48, rings=24, name="ball")
        runs = ball.line_on([(x, 20, 0) for x in range(-45, 46, 15)], (0, 0, -1), offset=0.5)
        self.assertEqual(len(runs), 1)
        pts = runs[0]
        self.assertGreater(len(pts), 7)                       # refined between the inputs
        for p in pts:
            self.assertGreater(p[2], 0)                       # landed on the near side
            self.assertTrue(49.5 < math.dist(p, (0, 0, 0)) < 51.0)
        sh = Sheet("D")
        fv = sh.model_view(m, "front", 300, 300, 2.0)
        fv.render()
        self.assertTrue(any(st == "thin" for st, _ in fv.result.visible))

    def test_envelope_and_extreme(self):
        m = Model("v")
        m.box((0, 600, 0), (2000, 600, 800), name="body")
        m.ellipsoid((1000, 700, 0), (30, 20, 20), name="lamp")
        env = m.envelope()
        self.assertEqual(env["x"][1], (1030.0, "lamp"))
        self.assertEqual(env["x"][0], (-1000.0, "body"))
        self.assertAlmostEqual(m.extreme("+x")[0], 1030.0)

    def test_ramp_angle_matches_tangent_geometry(self):
        m = Model("v")
        m.box((0, 600, 0), (2000, 600, 800), name="body")        # x -1000..1000, y 300..900
        for xa in (-500, 500):
            m.cylinder((xa, 300, -500), 300, 1000, axis="z", name="tire")
        sh = Sheet("D")
        side = sh.model_view(m, "front", 400, 300, 0.1, name="side")
        a, lim = side.ramp_angle((-500, 300, 0), 300, toward="left", label="APPROACH")
        self.assertAlmostEqual(a, math.degrees(math.asin(300 / 500)), places=6)
        self.assertEqual(lim, (-1000.0, 300.0))
        b, _ = side.ramp_angle((500, 300, 0), 300, toward="right", label="DEPARTURE")
        self.assertAlmostEqual(a, b, places=6)


class CheckerTest(unittest.TestCase):
    def test_clean_sheet(self):
        sh = Sheet("D")
        v = sh.view(300, 300, 2.0, name="front")
        body = v.rect(0, 0, 60, 40, r=4)
        v.dim_h(body.tl, body.tr, offset=10, ref=body)
        v.dim_v(body.tr, body.br, offset=10, ref=body)
        self.assertEqual(save_quietly(sh), [])

    def test_typed_value_must_match_geometry(self):
        sh = Sheet("D")
        v = sh.view(300, 300, 2.0, name="front")
        body = v.rect(0, 0, 60, 40)
        v.dim_h(body.tl, body.tr, offset=10, text="65.00")
        self.assertTrue(any("65.00" in m for m in messages(save_quietly(sh), "WARN")))

    def test_count_must_match_features(self):
        sh = Sheet("D")
        v = sh.view(300, 300, 2.0, name="front")
        v.rect(0, 0, 60, 40)
        hole = v.circle(10, 0, d=5)
        v.diameter(hole, prefix="4X")
        self.assertTrue(any("4X" in m for m in messages(save_quietly(sh), "WARN")))

    def test_dimension_off_the_part(self):
        sh = Sheet("D")
        v = sh.view(300, 300, 2.0, name="front")
        v.rect(0, 0, 60, 40)
        v.dim_h((-30, 20), (37, 20), offset=10)              # 37 is past the right edge
        self.assertTrue(messages(save_quietly(sh), "WARN"))

    def test_overlapping_text_is_an_error(self):
        sh = Sheet("D")
        v = sh.view(300, 300, 2.0, name="front")
        v.text("FIRST LABEL", 0, 0)
        v.text("SECOND LABEL", 1, 0)
        self.assertTrue(messages(save_quietly(sh), "ERROR"))


if __name__ == "__main__":
    unittest.main()
