#!/usr/bin/env python3
"""模型比选的描述性统计：通过率与 Wilson 区间、配对比较、延迟分位数。仅用标准库。

脚本只对用户给出的评分结果做算术，不判断评分是否正确，也不判断样本是否有代表性；
输出是描述，不是采用哪个模型的决定。

  rate     每个评分列的通过率及 Wilson 95% 区间，可按分层列分组
  compare  同一批样本上两个评分列的配对比较：不一致计数、精确 McNemar 检验、
           通过率差的配对自助法区间
  latency  延迟列的均值、P50、P95（最近秩法）

CSV 为 UTF-8，首行为列名（可直接用 eval-sheet 的列）。空值、NA、- 视为缺失并跳过。
"""
import argparse
import csv
import json
import math
import random
import sys
from collections import OrderedDict

Z95 = 1.959963984540054
PASS_VALUES = ('1', '正确', '是', 'y', 'yes', 'true', 'pass')
FAIL_VALUES = ('0', '错误', '否', 'n', 'no', 'false', 'fail')
PARTIAL_VALUES = ('部分',)
NA_VALUES = ('', 'na', 'n/a', '-', 'none', 'null')


def wilson(k, n, z=Z95):
    if n <= 0:
        raise ValueError('样本数必须大于 0')
    if not 0 <= k <= n:
        raise ValueError('通过数必须在 0 到样本数之间')
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return max(0.0, centre - half), min(1.0, centre + half)


def mcnemar_exact_p(a_only, b_only):
    """双侧精确 McNemar（二项符号检验）。a_only、b_only 为两种不一致的计数。"""
    n = a_only + b_only
    if n == 0:
        return 1.0
    k = min(a_only, b_only)
    tail = sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n
    return min(1.0, 2 * tail)


def percentile(sorted_values, p):
    """最近秩法：第 ceil(p/100 * n) 个值。"""
    n = len(sorted_values)
    if n == 0:
        raise ValueError('没有可用数值')
    rank = max(1, math.ceil(p / 100 * n))
    return sorted_values[rank - 1]


def read_rows(path):
    with open(path, newline='', encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))


def _col(rows, name):
    if not rows:
        raise ValueError('CSV 没有数据行')
    if name not in rows[0]:
        raise ValueError(f'找不到列“{name}”，现有列：{list(rows[0].keys())}')


def outcomes(rows, col, pass_values=PASS_VALUES, fail_values=FAIL_VALUES,
             partial_values=PARTIAL_VALUES, partial_as_pass=False):
    """返回 [(行序号, 得分 1/0/None, 是否部分)]；None 表示缺失。"""
    _col(rows, col)
    out = []
    for i, row in enumerate(rows, start=2):  # 行号含表头，便于对照文件
        raw = (row.get(col) or '').strip()
        v = raw.lower()
        if v in NA_VALUES:
            out.append((i, None, False))
        elif v in [x.lower() for x in pass_values]:
            out.append((i, 1, False))
        elif v in [x.lower() for x in fail_values]:
            out.append((i, 0, False))
        elif v in [x.lower() for x in partial_values]:
            out.append((i, 1 if partial_as_pass else 0, True))
        else:
            raise ValueError(f'第 {i} 行列“{col}”的值“{raw}”无法识别为通过、未通过、部分或缺失')
    return out


def rate(rows, col, by=None, **kw):
    def one(subset_rows):
        res = outcomes(subset_rows, col, **kw) if subset_rows else []
        scored = [s for _, s, _ in res if s is not None]
        n = len(scored)
        k = sum(scored)
        partial = sum(1 for _, s, p in res if s is not None and p)
        r = OrderedDict(n=n, skipped=len(res) - n, passed=k, partial=partial)
        if n:
            lo, hi = wilson(k, n)
            r.update(rate=k / n, wilson_low=lo, wilson_high=hi)
        else:
            r['rate'] = None
        return r

    result = OrderedDict(column=col, overall=one(rows))
    if by:
        _col(rows, by)
        groups = OrderedDict()
        for row in rows:
            groups.setdefault((row.get(by) or '').strip() or '(空)', []).append(row)
        result['by'] = OrderedDict((g, one(rs)) for g, rs in groups.items())
        result['note'] = '分层后每组样本很少，区间会很宽；只用来看哪一层暴露失败，不要外推到总体'
    return result


def compare(rows, col_a, col_b, seed=0, resamples=2000, **kw):
    oa = outcomes(rows, col_a, **kw)
    ob = outcomes(rows, col_b, **kw)
    pairs = [(a, b) for (_, a, _), (_, b, _) in zip(oa, ob) if a is not None and b is not None]
    n = len(pairs)
    if n == 0:
        raise ValueError('两列没有同时有结果的样本')
    both_pass = sum(1 for a, b in pairs if a and b)
    a_only = sum(1 for a, b in pairs if a and not b)
    b_only = sum(1 for a, b in pairs if b and not a)
    both_fail = n - both_pass - a_only - b_only
    ra = (both_pass + a_only) / n
    rb = (both_pass + b_only) / n
    deltas = [a - b for a, b in pairs]
    rng = random.Random(seed)
    means = sorted(sum(rng.choices(deltas, k=n)) / n for _ in range(resamples))
    lo = means[int((resamples - 1) * 0.025)]
    hi = means[math.ceil((resamples - 1) * 0.975)]
    r = OrderedDict(
        a=col_a, b=col_b, paired_n=n,
        skipped=len(oa) - n,
        both_pass=both_pass, a_only=a_only, b_only=b_only, both_fail=both_fail,
        rate_a=ra, rate_b=rb, diff_a_minus_b=ra - rb,
        diff_bootstrap_low=lo, diff_bootstrap_high=hi,
        mcnemar_exact_p=mcnemar_exact_p(a_only, b_only),
        bootstrap=OrderedDict(seed=seed, resamples=resamples),
    )
    notes = ['p 值只对事先指定的这一次比较有意义；比较多项指标时需自行校正',
             '区间与检验只描述这批样本；样本不是随机抽取时不能外推']
    if a_only + b_only < 10:
        notes.append('不一致的样本少于 10 条，检验几乎没有区分力：差异不显著不等于没有差异')
    r['notes'] = notes
    return r


def latency(rows, cols):
    result = OrderedDict()
    for col in cols:
        _col(rows, col)
        vals = []
        for i, row in enumerate(rows, start=2):
            raw = (row.get(col) or '').strip()
            if raw.lower() in NA_VALUES:
                continue
            try:
                x = float(raw)
            except ValueError:
                raise ValueError(f'第 {i} 行列“{col}”的值“{raw}”不是数字')
            if not math.isfinite(x) or x < 0:
                raise ValueError(f'第 {i} 行列“{col}”的值“{raw}”不是有限的非负数')
            vals.append(x)
        vals.sort()
        r = OrderedDict(n=len(vals))
        if vals:
            r.update(mean=sum(vals) / len(vals), p50=percentile(vals, 50),
                     p95=percentile(vals, 95), max=vals[-1])
            if len(vals) < 20:
                r['note'] = '样本少于 20 条，P95 不稳定，只作参考'
        result[col] = r
    return result


def _round(x):
    if isinstance(x, float):
        return round(x, 4)
    if isinstance(x, dict):
        return OrderedDict((k, _round(v)) for k, v in x.items())
    if isinstance(x, list):
        return [_round(v) for v in x]
    return x


def _values(s):
    return tuple(v.strip() for v in s.split(',') if v.strip())


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest='cmd', required=True)

    def common(sp):
        sp.add_argument('csv')
        sp.add_argument('--pass-values', type=_values, default=PASS_VALUES)
        sp.add_argument('--fail-values', type=_values, default=FAIL_VALUES)
        sp.add_argument('--partial-as-pass', action='store_true',
                        help='把“部分”算作通过（默认算未通过，并单独计数）')

    r = sub.add_parser('rate', help='通过率与 Wilson 区间')
    common(r)
    r.add_argument('--col', nargs='+', required=True)
    r.add_argument('--by', help='分层列')

    c = sub.add_parser('compare', help='两列配对比较')
    common(c)
    c.add_argument('--a', required=True)
    c.add_argument('--b', required=True)
    c.add_argument('--seed', type=int, default=0)
    c.add_argument('--resamples', type=int, default=2000)

    l = sub.add_parser('latency', help='延迟分位数')
    l.add_argument('csv')
    l.add_argument('--col', nargs='+', required=True)

    a = p.parse_args(argv)
    try:
        rows = read_rows(a.csv)
        if a.cmd == 'latency':
            out = latency(rows, a.col)
        else:
            kw = dict(pass_values=a.pass_values, fail_values=a.fail_values,
                      partial_as_pass=a.partial_as_pass)
            if a.cmd == 'rate':
                out = OrderedDict((col, rate(rows, col, by=a.by, **kw)) for col in a.col)
            else:
                if a.resamples < 100:
                    raise ValueError('resamples 至少 100')
                out = compare(rows, a.a, a.b, seed=a.seed, resamples=a.resamples, **kw)
    except (ValueError, OSError) as e:
        p.error(str(e))
    out = OrderedDict(status='descriptive_statistics_not_decision', result=out)
    print(json.dumps(_round(out), ensure_ascii=False, indent=2, allow_nan=False))


if __name__ == '__main__':
    main()
