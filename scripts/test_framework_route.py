import unittest
from framework_route import route

class RouteTests(unittest.TestCase):
    def test_selected_industry_and_depth(self):
        quick=route('explain','280000','quick');deep=route('explain','280000','deep')
        self.assertEqual(quick['industry']['name'],'汽车')
        self.assertLess(len(quick['references']),len(deep['references']))
    def test_unknown_is_not_guessed(self):
        with self.assertRaises(ValueError):route('explain','汽车')
        with self.assertRaises(ValueError):route('invented')
