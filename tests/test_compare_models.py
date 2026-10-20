import csv
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import compare_models as cm  # noqa: E402


def rows_from(cols, data):
    return [dict(zip(cols, r)) for r in data]


class WilsonTests(unittest.TestCase):
    def test_known_values(self):
        lo, hi = cm.wilson(8, 10)
        self.assertAlmostEqual(lo, 0.4901, places=3)
        self.assertAlmostEqual(hi, 0.9433, places=3)

    def test_zero_successes(self):
        lo, hi = cm.wilson(0, 10)
        self.assertEqual(lo, 0.0)
        self.assertAlmostEqual(hi, 0.2775, places=3)

    def test_invalid(self):
        for k, n in ((1, 0), (-1, 5), (6, 5)):
            with self.subTest(k=k, n=n), self.assertRaises(ValueError):
                cm.wilson(k, n)


class McNemarTests(unittest.TestCase):
    def test_exact_values(self):
        self.assertAlmostEqual(cm.mcnemar_exact_p(5, 0), 0.0625)
        self.assertAlmostEqual(cm.mcnemar_exact_p(3, 3), 1.0)
        self.assertAlmostEqual(cm.mcnemar_exact_p(8, 2), 112 / 1024)
        self.assertEqual(cm.mcnemar_exact_p(0, 0), 1.0)

    def test_symmetric(self):
        self.assertEqual(cm.mcnemar_exact_p(2, 9), cm.mcnemar_exact_p(9, 2))


class PercentileTests(unittest.TestCase):
    def test_nearest_rank(self):
        v = sorted(range(1, 11))
        self.assertEqual(cm.percentile(v, 50), 5)
        self.assertEqual(cm.percentile(v, 95), 10)
        self.assertEqual(cm.percentile([7], 95), 7)

    def test_empty(self):
        with self.assertRaises(ValueError):
            cm.percentile([], 50)


class OutcomeTests(unittest.TestCase):
    COLS = ['分层', 'A', 'B', 'tA', 'tB']

    def test_values_and_na(self):
        rows = rows_from(['A'], [['正确'], ['错误'], ['部分'], [''], ['NA'], ['1'], ['0']])
        res = cm.outcomes(rows, 'A')
        self.assertEqual([s for _, s, _ in res], [1, 0, 0, None, None, 1, 0])
        self.assertTrue(res[2][2])  # 部分被标记
        res = cm.outcomes(rows, 'A', partial_as_pass=True)
        self.assertEqual(res[2][1], 1)

    def test_unknown_value_names_the_row(self):
        rows = rows_from(['A'], [['正确'], ['也许']])
        with self.assertRaisesRegex(ValueError, '第 3 行'):
            cm.outcomes(rows, 'A')

    def test_missing_column(self):
        with self.assertRaisesRegex(ValueError, '找不到列'):
            cm.outcomes(rows_from(['A'], [['1']]), 'B')


class RateTests(unittest.TestCase):
    def test_rate_and_partial_count(self):
        rows = rows_from(['A'], [['正确']] * 6 + [['部分']] * 2 + [['错误']] * 2 + [['']])
        r = cm.rate(rows, 'A')['overall']
        self.assertEqual((r['n'], r['passed'], r['partial'], r['skipped']), (10, 6, 2, 1))
        self.assertAlmostEqual(r['rate'], 0.6)
        self.assertLess(r['wilson_low'], 0.6)
        self.assertGreater(r['wilson_high'], 0.6)

    def test_by_group(self):
        rows = rows_from(['层', 'A'], [['x', '1'], ['x', '0'], ['y', '1']])
        r = cm.rate(rows, 'A', by='层')
        self.assertEqual(r['by']['x']['n'], 2)
        self.assertEqual(r['by']['y']['passed'], 1)


class CompareTests(unittest.TestCase):
    def make(self, both_pass, a_only, b_only, both_fail):
        data = ([['1', '1']] * both_pass + [['1', '0']] * a_only +
                [['0', '1']] * b_only + [['0', '0']] * both_fail)
        return rows_from(['A', 'B'], data)

    def test_counts_and_rates(self):
        r = cm.compare(self.make(20, 8, 2, 10), 'A', 'B')
        self.assertEqual((r['both_pass'], r['a_only'], r['b_only'], r['both_fail']), (20, 8, 2, 10))
        self.assertAlmostEqual(r['rate_a'], 28 / 40)
        self.assertAlmostEqual(r['rate_b'], 22 / 40)
        self.assertAlmostEqual(r['diff_a_minus_b'], 6 / 40)
        self.assertAlmostEqual(r['mcnemar_exact_p'], 112 / 1024)
        self.assertLessEqual(r['diff_bootstrap_low'], r['diff_a_minus_b'])
        self.assertGreaterEqual(r['diff_bootstrap_high'], r['diff_a_minus_b'])

    def test_deterministic_with_seed(self):
        rows = self.make(20, 8, 2, 10)
        self.assertEqual(cm.compare(rows, 'A', 'B', seed=1), cm.compare(rows, 'A', 'B', seed=1))

    def test_skips_unpaired_rows(self):
        rows = self.make(5, 1, 0, 2) + rows_from(['A', 'B'], [['1', ''], ['', '0']])
        r = cm.compare(rows, 'A', 'B')
        self.assertEqual(r['paired_n'], 8)
        self.assertEqual(r['skipped'], 2)

    def test_few_discordant_warns(self):
        r = cm.compare(self.make(30, 2, 1, 7), 'A', 'B')
        self.assertTrue(any('少于 10' in n for n in r['notes']))

    def test_no_pairs(self):
        with self.assertRaises(ValueError):
            cm.compare(rows_from(['A', 'B'], [['1', '']]), 'A', 'B')

    def test_identical_columns_zero_diff(self):
        r = cm.compare(rows_from(['A', 'B'], [['1', '1'], ['0', '0']] * 5), 'A', 'B')
        self.assertEqual(r['diff_a_minus_b'], 0)
        self.assertEqual(r['mcnemar_exact_p'], 1.0)


class LatencyTests(unittest.TestCase):
    def test_stats_and_small_sample_note(self):
        rows = rows_from(['t'], [[str(x)] for x in range(1, 11)] + [['']])
        r = cm.latency(rows, ['t'])['t']
        self.assertEqual((r['n'], r['p50'], r['p95'], r['max']), (10, 5, 10, 10))
        self.assertIn('note', r)

    def test_rejects_bad_numbers(self):
        for bad in ('abc', '-1', 'nan', 'inf'):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                cm.latency(rows_from(['t'], [[bad]]), ['t'])


class CliTests(unittest.TestCase):
    def run_cli(self, rows, *args):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'r.csv'
            with open(path, 'w', newline='', encoding='utf-8-sig') as f:
                w = csv.writer(f)
                w.writerow(['分层', '27B正确(正确/部分/错误)', '9B正确(正确/部分/错误)', '27B总秒', '9B总秒'])
                w.writerows(rows)
            return subprocess.run(
                [sys.executable, str(ROOT / 'scripts/compare_models.py'), args[0], str(path), *args[1:]],
                capture_output=True, text=True)

    ROWS = [['常见', '正确', '正确', '2.1', '1.2'], ['常见', '正确', '错误', '2.4', '1.1'],
            ['拒答', '错误', '部分', '3.0', '1.5'], ['拒答', '正确', '', '2.2', '']]

    def test_eval_sheet_style_columns(self):
        p = self.run_cli(self.ROWS, 'compare', '--a', '27B正确(正确/部分/错误)',
                         '--b', '9B正确(正确/部分/错误)')
        self.assertEqual(p.returncode, 0, p.stderr)
        out = json.loads(p.stdout)
        self.assertEqual(out['status'], 'descriptive_statistics_not_decision')
        self.assertEqual(out['result']['paired_n'], 3)

    def test_rate_by_group_and_latency(self):
        p = self.run_cli(self.ROWS, 'rate', '--col', '27B正确(正确/部分/错误)', '--by', '分层')
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn('拒答', json.loads(p.stdout)['result']['27B正确(正确/部分/错误)']['by'])
        p = self.run_cli(self.ROWS, 'latency', '--col', '27B总秒', '9B总秒')
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(json.loads(p.stdout)['result']['9B总秒']['n'], 3)

    def test_bad_column_exits_nonzero(self):
        p = self.run_cli(self.ROWS, 'rate', '--col', '不存在')
        self.assertNotEqual(p.returncode, 0)
        self.assertIn('找不到列', p.stderr)


if __name__ == '__main__':
    unittest.main()
