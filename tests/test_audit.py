import copy
import json
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from audit import audit


def fixture(name):
    return json.loads((ROOT / "examples" / (name + ".json")).read_text(encoding="utf-8"))


class AuditTests(unittest.TestCase):
    def setUp(self):
        self.demo = fixture("demo")
        self.item = self.demo["catalog"][0]
        self.demo["basket"] = {self.item["id"]: 1}

    def test_threshold_edges(self):
        for price, expected in ((19899, 0), (19900, 5000), (19901, 5000)):
            with self.subTest(price=price):
                self.item["rule_price"] = price
                self.assertEqual(audit(self.demo)["order"]["rule"]["discount"], expected)

    def test_original_demo_and_repair(self):
        data = fixture("demo")
        result = audit(data)
        self.assertEqual(result["baskets_tested"], 7)
        self.assertEqual(result["counts"], {"本单一致": 6, "文案多承诺": 1})
        self.assertEqual(result["order"]["rule"]["gap"], 4000)
        data["basket"] = {"A-正价上衣": 1, "C-正价配件": 1}
        self.assertEqual(audit(data)["order"]["rule"]["discount"], 5000)

    def test_public_examples(self):
        for name, expected in [("youzan", 500), ("books-reading", 5000),
                               ("books-blueseeds", 0), ("books-mutated", 0)]:
            with self.subTest(name=name):
                self.assertEqual(audit(fixture(name))["order"]["rule"]["discount"], expected)
        result = audit(fixture("books-mutated"))
        self.assertEqual(result["witnesses"]["文案多承诺"]["basket"], {"女王特调身体乳": 1})

    def test_unconfirmed_item_straddles_threshold(self):
        self.item.update(rule="unknown", rule_price=19900)
        self.assertEqual(audit(self.demo)["order"]["verdict"], "待核")

    def test_unconfirmed_item_below_threshold(self):
        self.item.update(rule="unknown", rule_price=19899)
        self.assertEqual(audit(self.demo)["order"]["rule"]["discount"], 0)

    def test_unknown_price(self):
        self.item["rule_price"] = None
        self.assertIsNone(audit(self.demo)["order"]["rule"]["discount"])
        self.item["rule"] = "no"
        self.assertEqual(audit(self.demo)["order"]["rule"]["discount"], 0)

    def test_known_minimum_is_sufficient(self):
        self.item["rule_price"] = 19900
        extra = self.demo["catalog"][2]
        extra.update(rule="unknown", rule_price=None)
        self.demo["basket"][extra["id"]] = 1
        self.assertEqual(audit(self.demo)["order"]["rule"]["discount"], 5000)

    def test_pending_prerequisite(self):
        self.item["rule_price"] = 19900
        self.demo["rule"]["pending"] = ["需确认是否满足会员条件"]
        self.assertIsNone(audit(self.demo)["order"]["rule"]["discount"])

    def test_distinct_price_basis(self):
        self.item.update(claim_price=19900, rule_price=19899)
        self.assertEqual(audit(self.demo)["order"]["verdict"], "文案多承诺")

    def test_underpromise_and_multiple_units(self):
        self.item.update(rule_price=10000, claim_price=9000, limit=2)
        self.demo["basket"][self.item["id"]] = 2
        result = audit(self.demo)
        self.assertEqual(result["order"]["verdict"], "文案少承诺")
        self.assertEqual(sum(result["witnesses"]["文案少承诺"]["basket"].values()), 2)

    def test_input_errors(self):
        for key, value in [("rule_price", -1), ("limit", True), ("claim", "maybe")]:
            data = copy.deepcopy(self.demo)
            data["catalog"][0][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                audit(data)
        self.demo["basket"][self.item["id"]] = 2
        with self.assertRaises(ValueError):
            audit(self.demo)

    def test_cli_stdin_and_malformed_json(self):
        command = [sys.executable, str(ROOT / "scripts/audit.py"), "-", "--json"]
        good = subprocess.run(command, input=json.dumps(fixture("demo")), text=True, capture_output=True)
        self.assertEqual(good.returncode, 0)
        self.assertEqual(json.loads(good.stdout)["order"]["verdict"], "文案多承诺")
        bad = subprocess.run(command, input="{", text=True, capture_output=True)
        self.assertEqual(bad.returncode, 2)


if __name__ == "__main__":
    unittest.main()
