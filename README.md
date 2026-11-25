# 这单真能减？

审核电商满减宣传语，找出承诺与券规则不一致的购物车，并给出改稿。给写笔记、备直播或审核促销海报的人用。把宣传语、券细则和几件商品交给 Agent，即可得到一笔具体的购物车、一行算式，以及有出处的改稿。

**[下载 Skill 源码包（v0.1.0）](https://github.com/Bamboorat0908/promo-proof/releases/download/v0.1.0/promo-proof.zip)**

## 一分钟试跑

解压后在包含 SKILL.md 的目录执行。需要 Python 3.8 或更高版本，仅使用标准库。

```bash
python3 scripts/audit.py examples/demo.json
python3 scripts/audit.py examples/books-mutated.json
python3 -B -m unittest discover -s tests -v
```

第一条会发现“全店满199减50”的问题。159 元正价上衣加 40 元特价配件，文案承诺减 50 元；细则只计算正价，实际计入 159 元，还差 40 元。把配件换成同价的正价款，规则优惠变成 50 元。

第二条用真实活动商品测试一次人为改错的推广语。运行 examples/books-reading.json 可与原稿对照。运行 examples/youzan.json 或 examples/books-blueseeds.json 可切换案例。

## 在 Agent 里使用

将整个 promo-proof 目录放入宿主支持的 Skills 目录或使用宿主的本地 Skill 导入功能。对 Agent 说：

> 用“这单真能减？”审核这句直播口播：全店满199减50。券详情写着“只有正价商品计入，满199减50”。商品有159元正价上衣、40元特价配件、40元正价配件，各限1件。请找出会少减的最小订单，并只改口播里有问题的部分。

其他入口包括发布前批量试几种凑单、客服解释混单为何未达门槛、对照同价换品，以及核对已脱敏的结算预览。输入、判定边界和输出约定见 SKILL.md。

## 验证情况

- **自动化测试**：`python3 -B -m unittest discover -s tests -v` 共 12 项通过，覆盖门槛边界、价格口径、混单、缺项与输入错误等。
- **公开规则算例**：`references/validation.md` 记录有赞混单算例和两张公开在售券的展示价条件测算；演示订单中文案承诺优惠 50 元、规则优惠 0 元。这些是依据公开规则和页面展示价的推演，不是实际结算结果。
- **实际结算记录**：目前独立结算预览、支付回执与商家复核记录均为零，现场误判率尚无分母。下一轮采样计划见 `references/field-trial.csv`。

[公开案例及实测说明](references/validation.md) · [现场记录空表](references/field-trial.csv)
