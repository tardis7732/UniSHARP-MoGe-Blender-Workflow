import sys
from pathlib import Path
import unittest
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
from moge_geometry import depth_mesh, inverse_depth_preview


class GeometryTests(unittest.TestCase):
    def test_plane_reprojects_to_pixel_centers(self):
        d = np.full((4, 6), 3., np.float32)
        k = np.array([[.8, 0, .43], [0, 1.2, .55], [0, 0, 1]])
        v, f, uv = depth_mesh(d, np.ones_like(d, bool), k)
        projected = np.column_stack([v[:, 0]/v[:, 2]*k[0, 0]+k[0, 2],
                                     v[:, 1]/v[:, 2]*k[1, 1]+k[1, 2]])
        np.testing.assert_allclose(projected, np.column_stack([uv[:, 0], 1-uv[:, 1]]), atol=1e-7)
        self.assertEqual(len(f), 30)
        normals = np.cross(v[f[:, 1]]-v[f[:, 0]], v[f[:, 2]]-v[f[:, 0]])
        self.assertTrue((normals[:, 2] < 0).all())

    def test_mask_and_depth_jump_do_not_create_bridges(self):
        d = np.ones((5, 6), np.float32); d[:, 3:] = 8
        mask = np.ones_like(d, bool); mask[2, 1] = False
        v, f, _ = depth_mesh(d, mask, np.eye(3), edge_threshold=.04)
        self.assertTrue((np.ptp(v[f, 2], axis=1) == 0).all())
        self.assertFalse(np.any(np.all(np.isclose(v, [(1.5)/6, (2.5)/5, 1]), axis=1)))

    def test_depth_white_near_black_far_and_invalid(self):
        d = np.array([[1, 2, 10], [0, np.nan, np.inf]], np.float32)
        view, valid = inverse_depth_preview(d, np.ones_like(d, bool))
        self.assertGreater(view[0, 0], view[0, 1])
        self.assertGreater(view[0, 1], view[0, 2])
        self.assertTrue((view[1] == 0).all())
        self.assertEqual(valid.sum(), 3)


if __name__ == '__main__':
    unittest.main()
