import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from cost_model import analyze  # noqa: E402

BASE = dict(in_tokens=1000, out_tokens=200, in_price=2, out_price=8,
            orders_per_day=1000, days=250)


class CostModelTests(unittest.TestCase):
    def test_basic_unit_cost(self):
        r = analyze(**BASE)
        self.assertAlmostEqual(r['model_cost_per_order'], 0.0036)
        self.assertAlmostEqual(r['annual_total_cost'], 900.0)
        self.assertEqual(r['status'], 'conditional_inference_not_observation')

    def test_calls_and_retry_scale_model_cost(self):
        r = analyze(**BASE, calls=2, retry_rate=0.5)
        self.assertAlmostEqual(r['model_cost_per_order'], 0.0036 * 3)

    def test_review_and_other_cost(self):
        r = analyze(**BASE, other_per_order=0.01, review_share=0.2, review_cost=1.0)
        self.assertAlmostEqual(r['variable_cost_per_order'], 0.0036 + 0.01 + 0.2)

    def test_fixed_cost_changes_effective_unit_cost(self):
        r = analyze(**BASE, fixed_annual=250000)
        self.assertAlmostEqual(r['effective_cost_per_order'], 0.0036 + 1.0)

    def test_value_ceiling_and_break_even(self):
        r = analyze(**BASE, fixed_annual=250000, human_cost=5, saving_share=0.5,
                    realizable_share=0.8)
        self.assertAlmostEqual(r['gross_value_per_order'], 2.0)
        self.assertTrue(r['cost_within_value_ceiling'])
        # 固定成本250000 / 250天 / (2.0 - 0.0036) 每天的盈亏平衡单量
        self.assertAlmostEqual(r['break_even_orders_per_day'], 1000 / (2.0 - 0.0036))

    def test_cost_above_ceiling_flagged(self):
        r = analyze(**BASE, other_per_order=3.0, human_cost=5, saving_share=0.5,
                    realizable_share=0.8)
        self.assertFalse(r['cost_within_value_ceiling'])

    def test_volume_sensitivity_with_fixed_cost(self):
        r = analyze(**BASE, fixed_annual=1000, volume_multipliers=[1, 10])
        rows = r['volume_sensitivity']
        self.assertAlmostEqual(rows[1]['annual_total_cost'], 9000 + 1000)
        self.assertLess(rows[1]['effective_cost_per_order'], rows[0]['effective_cost_per_order'])

    def test_peak_calls(self):
        r = analyze(**BASE, peak_hour_share=0.3, calls=2)
        self.assertAlmostEqual(r['peak_calls_per_minute'], 1000 * 0.3 * 2 / 60)

    def test_invalid_inputs(self):
        bad = [dict(in_tokens=-1), dict(days=0), dict(orders_per_day=float('nan')),
               dict(review_share=1.5), dict(in_price=True), dict(retry_rate=-0.1)]
        for override in bad:
            with self.subTest(override=override):
                with self.assertRaises(ValueError):
                    analyze(**{**BASE, **override})

    def test_partial_value_args_rejected(self):
        with self.assertRaises(ValueError):
            analyze(**BASE, human_cost=5)

    def test_no_default_days(self):
        with self.assertRaises(TypeError):
            analyze(in_tokens=1, out_tokens=1, in_price=1, out_price=1, orders_per_day=1)


if __name__ == '__main__':
    unittest.main()
