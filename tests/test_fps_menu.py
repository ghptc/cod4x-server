import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('fps333', Path(__file__).parents[1] / 'tools/promod/fps333.py')
fps = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fps)


class FPSMenu(unittest.TestCase):
    def test_patch_is_limited_to_upper_bound_and_message(self):
        source = 'dvarint("com_maxfps") < 40 || ' + fps.RULE + '; otherCheck(); SET COM_MAXFPS WITHIN 40-250'
        result = fps.patch_menu(source, 1, 1)
        self.assertEqual(result.replace('> 333', '> 250').replace('40-333', '40-250'), source)
        tree = fps.expression_tree(result.split(';')[0])
        def evaluate(node, value):
            if isinstance(node, str): return int(node) if node.isdigit() else node
            if node[0] == 'call': return value
            left, right = evaluate(node[1], value), evaluate(node[2], value)
            return {'||': lambda: left or right, '<': lambda: left < right,
                    '>': lambda: left > right}[node[0]]()
        for value, allowed in [(39, False), (40, True), (125, True), (250, True), (333, True), (334, False)]:
            self.assertEqual(not evaluate(tree, value), allowed)

    def test_tree_comparison_preserves_precedence(self):
        self.assertEqual(fps.expression_tree('a || b && c'), fps.expression_tree('a || (b && c)'))
        self.assertNotEqual(fps.expression_tree('(a || b) && c'), fps.expression_tree('a || b && c'))
        self.assertEqual(fps.expression_tree('!dvarint("x") && dvarint("y") < 40'),
                         fps.expression_tree('(!dvarint("x")) && (dvarint("y") < 40)'))

    def test_unknown_source_is_rejected(self):
        with self.assertRaises(ValueError): fps.patch_menu('another version', 1, 0)
        with self.assertRaises(ValueError): fps.expression_tree('a + b')
