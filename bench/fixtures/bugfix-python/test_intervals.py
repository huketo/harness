import unittest

from intervals import inclusive_span


class InclusiveSpanTests(unittest.TestCase):
    def test_regular_interval(self):
        self.assertEqual(inclusive_span(3, 7), 5)

    def test_single_position_interval(self):
        self.assertEqual(inclusive_span(4, 4), 1)

    def test_reversed_interval_is_empty(self):
        self.assertEqual(inclusive_span(8, 2), 0)

    def test_non_integer_boundary_is_rejected(self):
        with self.assertRaises(TypeError):
            inclusive_span(1.5, 3)


if __name__ == "__main__":
    unittest.main()
