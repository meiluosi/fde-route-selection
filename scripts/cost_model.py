"""单位经济估算：条件算术，不验证输入证据，也不含任何真实价格。"""
import argparse
import json
import math


def _num(name, x, strict=False, hi=None):
    if isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x):
        raise ValueError(f'{name} 需要有限数值')
    if (x <= 0) if strict else (x < 0):
        raise ValueError(f'{name} 不能为{"零或" if strict else ""}负')
    if hi is not None and x > hi:
        raise ValueError(f'{name} 必须在[0,{hi}]')
    return float(x)


def analyze(in_tokens, out_tokens, in_price, out_price, orders_per_day, days,
            calls=1.0, retry_rate=0.0, other_per_order=0.0,
            review_share=0.0, review_cost=0.0, fixed_annual=0.0,
            peak_hour_share=None, human_cost=None, saving_share=None,
            realizable_share=None, volume_multipliers=()):
    in_tokens = _num('in_tokens', in_tokens)
    out_tokens = _num('out_tokens', out_tokens)
    in_price = _num('in_price', in_price)
    out_price = _num('out_price', out_price)
    orders_per_day = _num('orders_per_day', orders_per_day, strict=True)
    days = _num('days', days, strict=True)
    calls = _num('calls', calls, strict=True)
    retry_rate = _num('retry_rate', retry_rate)
    other_per_order = _num('other_per_order', other_per_order)
    review_share = _num('review_share', review_share, hi=1)
    review_cost = _num('review_cost', review_cost)
    fixed_annual = _num('fixed_annual', fixed_annual)

    effective_calls = calls * (1 + retry_rate)
    model = effective_calls * (in_tokens * in_price + out_tokens * out_price) / 1e6
    review = review_share * review_cost
    variable = model + other_per_order + review
    annual_orders = orders_per_day * days
    annual = variable * annual_orders + fixed_annual

    r = dict(
        status='conditional_inference_not_observation',
        model_cost_per_order=model,
        other_cost_per_order=other_per_order,
        review_cost_per_order=review,
        variable_cost_per_order=variable,
        annual_orders=annual_orders,
        fixed_annual=fixed_annual,
        annual_total_cost=annual,
        effective_cost_per_order=annual / annual_orders,
        assumptions=['单价与币种单位由调用方提供且未经本脚本核实',
                     '每单 token 与调用次数为常数，未建模长尾',
                     '运行天数为调用方给出的客户实际天数'],
    )

    if peak_hour_share is not None:
        p = _num('peak_hour_share', peak_hour_share, hi=1)
        r['peak_calls_per_minute'] = orders_per_day * p * effective_calls / 60
        r['assumptions'].append('峰值按高峰小时占日量比例均匀分布，未含突发')

    value_args = (human_cost, saving_share, realizable_share)
    given = [v is not None for v in value_args]
    if any(given) and not all(given):
        raise ValueError('human_cost、saving_share、realizable_share 须同时提供')
    gross = None
    if all(given):
        human_cost = _num('human_cost', human_cost)
        saving_share = _num('saving_share', saving_share, hi=1)
        realizable_share = _num('realizable_share', realizable_share, hi=1)
        gross = human_cost * saving_share * realizable_share
        r['gross_value_per_order'] = gross
        r['net_value_per_order'] = gross - r['effective_cost_per_order']
        r['annual_net_value'] = r['net_value_per_order'] * annual_orders
        r['cost_within_value_ceiling'] = r['effective_cost_per_order'] <= gross
        margin = gross - variable
        r['break_even_orders_per_day'] = (
            fixed_annual / days / margin if margin > 0 and fixed_annual > 0 else None)
        r['assumptions'] += ['saving_share 若已扣除复核工时，则 review 参数不要再填，避免重复计算',
                             '价值为可兑现的人力节约，不含风险损失减少']

    rows = []
    for m in volume_multipliers:
        m = _num('volume_multiplier', m, strict=True)
        total = variable * annual_orders * m + fixed_annual
        row = dict(multiplier=m, annual_total_cost=total,
                   effective_cost_per_order=total / (annual_orders * m))
        if gross is not None:
            row['net_value_per_order'] = gross - row['effective_cost_per_order']
        rows.append(row)
    if rows:
        r['volume_sensitivity'] = rows
    return r


def _round(x):
    """仅用于展示，消除浮点噪声；analyze 本身返回原值。"""
    if isinstance(x, float):
        return round(x, 6)
    if isinstance(x, dict):
        return {k: _round(v) for k, v in x.items()}
    if isinstance(x, list):
        return [_round(v) for v in x]
    return x


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for arg in ('in-tokens', 'out-tokens', 'in-price', 'out-price', 'orders-per-day', 'days'):
        p.add_argument('--' + arg, type=float, required=True)
    p.add_argument('--calls', type=float, default=1.0)
    p.add_argument('--retry-rate', type=float, default=0.0)
    p.add_argument('--other-per-order', type=float, default=0.0)
    p.add_argument('--review-share', type=float, default=0.0)
    p.add_argument('--review-cost', type=float, default=0.0)
    p.add_argument('--fixed-annual', type=float, default=0.0)
    p.add_argument('--peak-hour-share', type=float)
    p.add_argument('--human-cost', type=float)
    p.add_argument('--saving-share', type=float)
    p.add_argument('--realizable-share', type=float)
    p.add_argument('--volume-multipliers', default='')
    a = p.parse_args()
    try:
        mult = [float(x) for x in a.volume_multipliers.split(',') if x.strip()]
        r = analyze(a.in_tokens, a.out_tokens, a.in_price, a.out_price,
                    a.orders_per_day, a.days, a.calls, a.retry_rate,
                    a.other_per_order, a.review_share, a.review_cost,
                    a.fixed_annual, a.peak_hour_share, a.human_cost,
                    a.saving_share, a.realizable_share, mult)
    except ValueError as e:
        p.error(str(e))
    print(json.dumps(_round(r), ensure_ascii=False, indent=2, allow_nan=False))


if __name__ == '__main__':
    main()
