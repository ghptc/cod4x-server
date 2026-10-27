"""Synthetic map graph fixtures; no vendor coordinates or waypoint data."""
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('btd_navigation', Path(__file__).parents[1] / 'tools/btd/navigation.py')
nav = importlib.util.module_from_spec(spec)
spec.loader.exec_module(nav)


class NavigationValidation(unittest.TestCase):
    def rows(self):
        return [['10', '0 0 0', '1 2', 'stand'],
                ['11', '10 0 0', '0 2', 'stand'],
                ['12', '10 10 0', '0 1', 'stand'], ['13', 'end', '0', '0']]

    def validate(self, rows, **kwargs):
        return nav.validate_rows(rows, offset=10, count=3, **kwargs)

    def test_valid_connected_reciprocal_graph(self):
        report = self.validate(self.rows())
        self.assertEqual(report['nodes'], 3)
        self.assertEqual(report['directed_edges'], 6)
        self.assertTrue(report['connected'])
        self.assertFalse(report['geometry_qualified'])
        self.assertFalse(report['gameplay_qualified'])
        self.assertFalse(report['angle_column'])

    def test_original_trailing_space_terminal_rejected(self):
        rows = self.rows(); rows[-1][1] = 'end '
        with self.assertRaisesRegex(ValueError, 'terminal'):
            self.validate(rows)

    def test_missing_invalid_or_nonfinite_coordinates(self):
        for value in ['', '1', '1 2', '1 2 3 4', '1 x 3', 'nan 1 2', '1 inf 2', '1e999 1 2', '1e39 1 2', '1_0 2 3', '١ 2 3', '1\t2 3', '1\n2 3', '1\u00a02 3']:
            with self.subTest(value=value):
                rows = self.rows(); rows[0][1] = value
                with self.assertRaises(ValueError): self.validate(rows)
        for value in [None, [1, 2], [1, None, 3]]:
            with self.subTest(value=value):
                with self.assertRaises(ValueError): nav.vector(value)

    def test_missing_duplicate_or_malformed_map_rows(self):
        for rows in [self.rows()[:-1], self.rows() + [self.rows()[0]],
                     [self.rows()[0][:-1]] + self.rows()[1:]]:
            with self.assertRaises(ValueError): self.validate(rows)

    def test_invalid_child_syntax_bounds_self_duplicates(self):
        for value in ['', '-1 2', '+1 2', '1.0 2', 'x 2', '1 3', '0 1', '1 1', '1\t2', '1\n2', '1\u00a02']:
            with self.subTest(value=value):
                rows = self.rows(); rows[0][2] = value
                with self.assertRaises(ValueError): self.validate(rows)

    def test_nonreciprocal_edge_rejected(self):
        rows = self.rows(); rows[1][2] = '2'
        with self.assertRaisesRegex(ValueError, 'Nonreciprocal'): self.validate(rows)

    def test_disconnected_graph_rejected(self):
        rows = [['10', '0 0 0', '1', 'stand'], ['11', '1 0 0', '0', 'stand'],
                ['12', '2 0 0', '3', 'stand'], ['13', '3 0 0', '2', 'stand'],
                ['14', 'end', '0', '0']]
        with self.assertRaisesRegex(ValueError, 'Disconnected'):
            nav.validate_rows(rows, offset=10, count=4)

    def test_duplicate_origins_and_unknown_type_rejected(self):
        rows = self.rows(); rows[1][1] = rows[0][1]
        with self.assertRaisesRegex(ValueError, 'Duplicate waypoint origin'): self.validate(rows)
        rows = self.rows(); rows[0][3] = 'unknown'
        with self.assertRaisesRegex(ValueError, 'type'): self.validate(rows)

    def test_unrelated_map_rows_do_not_change_selected_graph(self):
        rows = [['broken unrelated cell'], ['99', 'bad', 'bad', 'bad']] + self.rows()
        self.assertEqual(self.validate(rows), self.validate(self.rows()))

    def test_all_spawn_associations_and_explicit_proximity_gate(self):
        spawns = {index: (1, 1, 0) for index in range(25)}
        report = self.validate(self.rows(), spawns=spawns, max_spawn_distance=2)
        self.assertEqual(len(report['spawn_associations']), 25)
        self.assertTrue(all(item['node'] == 0 for item in report['spawn_associations']))
        with self.assertRaisesRegex(ValueError, 'distance'):
            self.validate(self.rows(), spawns=spawns, max_spawn_distance=1)
        del spawns[0]
        with self.assertRaisesRegex(ValueError, '25'): self.validate(self.rows(), spawns=spawns)

    def test_spawn_branch_parser_rejects_missing_ambiguous_duplicates(self):
        marker = 'else if(getDvar("mapname") == "mp_killhouse")'
        source = marker + '{' + ''.join(f'zomspawnpoint[{i}] = (1,2,3);' for i in range(25)) + '} // Overgrown'
        self.assertEqual(len(nav.spawn_points(source)), 25)
        for invalid in ['', marker + source, source.replace('[24]', '[23]'),
                        source.replace('(1,2,3)', '(1,2)', 1)]:
            with self.assertRaises(ValueError): nav.spawn_points(invalid)
