"""Audit one fixed-amount coupon. Prices are integer hundredths of the stated currency."""
import argparse
from collections import Counter
from itertools import combinations_with_replacement
import json
from pathlib import Path
import sys


def whole(value, low, high, field):
    if type(value) is not int or not low <= value <= high:
        raise ValueError(f"{field} 须为 {low} 到 {high} 的整数")
    return value


def label(value, field):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"缺少 {field}")
    return value


def validate(data):
    if data["currency"] not in ("CNY", "TWD"):
        raise ValueError("支持人民币或新台币，单个输入只能用一种币种")
    label(data["case"], "case")
    label(data["context"], "订单条件")
    for side in ("claim", "rule"):
        spec = data[side]
        for field in ("quote", "source", "scope", "basis"):
            label(spec[field], side + "." + field)
        if not isinstance(spec["pending"], list):
            raise ValueError("pending 须为待核问题列表")
        for issue in spec["pending"]:
            label(issue, "待核问题")
        whole(spec["threshold"], 1, 10**12, "threshold")
        whole(spec["discount"], 1, spec["threshold"], "discount")
    items = data["catalog"]
    if not isinstance(items, list) or not 1 <= len(items) <= 12:
        raise ValueError("商品列表须有 1 至 12 项")
    ids = set()
    for item in items:
        sku = label(item["id"], "商品编号")
        if sku in ids:
            raise ValueError("商品编号重复")
        ids.add(sku)
        whole(item["limit"], 1, 99, "limit")
        for side in ("claim", "rule"):
            if item[side] not in ("yes", "no", "unknown"):
                raise ValueError("商品资格须为 yes、no 或 unknown")
            price = item[side + "_price"]
            if price is not None:
                whole(price, 0, 10**12, side + "_price")
    basket = data["basket"]
    if not isinstance(basket, dict) or not basket or set(basket) - ids:
        raise ValueError("订单为空或含商品列表之外的编号")
    for item in items:
        if item["id"] in basket:
            whole(basket[item["id"]], 1, item["limit"], "订单数量")


def compute(spec, items, basket, side):
    lower, upper = 0, 0
    lines = []
    for sku, quantity in basket.items():
        item = items[sku]
        price, eligible = item[side + "_price"], item[side]
        value = None if price is None else price * quantity
        lines.append(dict(id=sku, qty=quantity, amount=value, eligible=eligible))
        if eligible == "no":
            continue
        if value is None:
            upper = None
        else:
            if eligible == "yes":
                lower += value
            if upper is not None:
                upper += value
    threshold = spec["threshold"]
    if upper is not None and upper < threshold:
        discount = 0
    elif lower >= threshold and not spec["pending"]:
        discount = spec["discount"]
    else:
        discount = None
    return dict(eligible_min=lower, eligible_max=upper, discount=discount,
                gap=max(0, threshold - lower) if lower == upper else None,
                pending=spec["pending"], lines=lines)


def compare(data, items, basket):
    a, b = [compute(data[side], items, basket, side) for side in ("claim", "rule")]
    x, y = a["discount"], b["discount"]
    if x is None or y is None:
        verdict = "待核"
    elif x > y:
        verdict = "文案多承诺"
    elif x < y:
        verdict = "文案少承诺"
    else:
        verdict = "本单一致"
    return dict(basket=basket, claim=a, rule=b, verdict=verdict)


def audit(data, depth=3):
    validate(data)
    whole(depth, 1, 3, "搜索上限")
    items = {item["id"]: item for item in data["catalog"]}
    tally = Counter()
    witnesses = {}
    for count in range(1, depth + 1):
        for combo in combinations_with_replacement(sorted(items), count):
            basket = dict(Counter(combo))
            if any(q > items[sku]["limit"] for sku, q in basket.items()):
                continue
            test = compare(data, items, basket)
            verdict = test["verdict"]
            tally[verdict] += 1
            if verdict in ("文案多承诺", "文案少承诺") and verdict not in witnesses:
                witnesses[verdict] = test
    return dict(case=data["case"], currency=data["currency"], context=data["context"],
                sources={key: data[key] for key in ("claim", "rule")},
                order=compare(data, items, data["basket"]), max_units=depth,
                baskets_tested=sum(tally.values()), counts=dict(tally), witnesses=witnesses)


def money(n, unit):
    if n is None:
        return "待核"
    return f"{n // 100}.{n % 100:02d} {unit}"


def render(result):
    unit = result["currency"]
    order = result["order"]

    def describe(test):
        basket = " + ".join(f"{k} × {v}" for k, v in test["basket"].items())
        return (f"{basket} ｜ {test['verdict']} ｜ 文案优惠 {money(test['claim']['discount'], unit)}"
                f" ｜ 规则优惠 {money(test['rule']['discount'], unit)}")

    out = [result["case"], "适用前提　" + result["context"], describe(order)]
    for side, name in (("claim", "文案"), ("rule", "规则")):
        branch = order[side]
        spec = result["sources"][side]
        high = "上限未知" if branch["eligible_max"] is None else money(branch["eligible_max"], unit)
        amount = money(branch["eligible_min"], unit)
        if branch["eligible_min"] != branch["eligible_max"]:
            amount += " 至 " + high
        out.append(f"{name}计入金额　{amount}（{spec['basis']}）")
        for row in branch["lines"]:
            state = {"yes": "计入", "no": "排除", "unknown": "资格待核"}[row["eligible"]]
            out.append(f"  {row['id']} × {row['qty']}　{money(row['amount'], unit)}　{state}")
        if branch["gap"] is not None and branch["gap"] > 0:
            out.append("  距门槛还差 " + money(branch["gap"], unit))
        if spec["pending"]:
            out.append("  需确认　" + "、".join(spec["pending"]))
        out.append(f"  依据　「{spec['quote']}」　{spec['source']}")
    out.append(f"商品组合复核　至多 {result['max_units']} 件，已检查 {result['baskets_tested']} 种　" +
               "，".join(f"{k} {v}" for k, v in result["counts"].items()))
    for verdict, test in result["witnesses"].items():
        out.append("最少件数反例　" + describe(test))
    if result["witnesses"] and not result["sources"]["rule"]["pending"]:
        spec = result["sources"]["rule"]
        out.append(f"文案修改草稿（沿用活动前提）　{spec['scope']}满 {money(spec['threshold'], unit)}"
                   f" 可减 {money(spec['discount'], unit)}。")
        out.append("发布前须保留的订单条件　" + result["context"])
    return "\n".join(out)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", help="JSON 路径，或 - 从标准输入读取")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--max-units", type=int, default=3)
    args = parser.parse_args()
    try:
        raw = sys.stdin.read() if args.input == "-" else Path(args.input).read_text(encoding="utf-8-sig")
        result = audit(json.loads(raw), args.max_units)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.exit(2, f"输入无法审核　{exc}\n")
    print(json.dumps(result, ensure_ascii=False, indent=2) if args.json else render(result))


if __name__ == "__main__":
    main()
