import tempfile
import unittest
from pathlib import Path

import record_purchase


class RecordPurchaseTests(unittest.TestCase):
    def test_records_purchase_using_total_paid(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "holdings.csv"
            added = record_purchase.append_purchase(
                path, "2026-08-20", "Lingfeng 2g gold bar", "2", "500",
                "Taobao", "Stored in China",
            )
            self.assertTrue(added)
            self.assertEqual(
                path.read_text(encoding="utf-8").splitlines()[1],
                "2026-08-20,Lingfeng 2g gold bar,2,500.00,Taobao,Stored in China",
            )

    def test_exact_duplicate_is_not_added(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "holdings.csv"
            values = (path, "2026-08-20", "Gold bar", "2", "500", "Other", "")
            self.assertTrue(record_purchase.append_purchase(*values))
            self.assertFalse(record_purchase.append_purchase(*values))
            self.assertEqual(len(path.read_text(encoding="utf-8").splitlines()), 2)

    def test_migrates_legacy_per_gram_rows(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "holdings.csv"
            path.write_text(
                "Date,Grams,Price_Paid_AUD\n2026-03-10,5,238.00\n",
                encoding="utf-8",
            )
            record_purchase.append_purchase(
                path, "2026-08-20", "Gold bar", "2", "500", "Other", "",
            )
            rows = path.read_text(encoding="utf-8").splitlines()
            self.assertIn("2026-03-10,Gold purchase,5,1190.00", rows[1])

    def test_rejects_invalid_values(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "holdings.csv"
            with self.assertRaisesRegex(ValueError, "YYYY-MM-DD"):
                record_purchase.append_purchase(path, "20 Aug", "Gold", "2", "500", "Other")
            with self.assertRaisesRegex(ValueError, "greater than zero"):
                record_purchase.append_purchase(path, "2026-08-20", "Gold", "0", "500", "Other")


if __name__ == "__main__":
    unittest.main()
