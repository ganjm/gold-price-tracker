import os
import tempfile
import unittest
from datetime import datetime
from email import policy
from email.parser import BytesParser
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

import gold_alert


PERTH = ZoneInfo("Australia/Perth")


def snapshot(spot=100.0, ma50=100.0, ma200=90.0):
    return gold_alert.MarketSnapshot(
        captured_at=datetime(2026, 7, 14, 10, 17, tzinfo=PERTH),
        spot_aud=spot,
        spot_cny=500.0,
        daily_change_pct=-1.25,
        ma50_aud=ma50,
        ma200_aud=ma200,
        pm_1g=120.0,
        pm_5g=550.0,
    )


class TradingStatusTests(unittest.TestCase):
    def test_open_during_weekday_hours(self):
        status, is_open = gold_alert.get_trading_status(datetime(2026, 7, 14, 10, tzinfo=PERTH))
        self.assertTrue(is_open)
        self.assertIn("Open", status)

    def test_closed_outside_hours(self):
        status, is_open = gold_alert.get_trading_status(datetime(2026, 7, 14, 8, tzinfo=PERTH))
        self.assertFalse(is_open)
        self.assertIn("trading hours", status)

    def test_holiday_takes_priority(self):
        status, is_open = gold_alert.get_trading_status(datetime(2026, 12, 25, 10, tzinfo=PERTH))
        self.assertFalse(is_open)
        self.assertIn("Christmas", status)


class SignalTests(unittest.TestCase):
    def test_buy_zone_at_five_percent_below_ma50(self):
        self.assertEqual(gold_alert.get_signal(snapshot(spot=95))[0], "BUY ZONE")

    def test_watch_below_ma50(self):
        self.assertEqual(gold_alert.get_signal(snapshot(spot=98))[0], "WATCH")

    def test_wait_at_or_above_ma50(self):
        self.assertEqual(gold_alert.get_signal(snapshot(spot=101))[0], "WAIT")


class EmailTests(unittest.TestCase):
    def test_message_contains_plain_text_and_html(self):
        message = gold_alert.build_message(
            snapshot(), "Open — Mon–Fri 9am–5pm", "sender@example.com", "reader@example.com"
        )
        parsed = BytesParser(policy=policy.default).parsebytes(message.as_bytes())
        self.assertEqual(parsed["To"], "reader@example.com")
        self.assertIn("Gold WAIT", parsed["Subject"])
        self.assertEqual({part.get_content_type() for part in parsed.walk()}, {
            "multipart/alternative", "text/plain", "text/html"
        })

    def test_missing_secrets_raise_clear_error(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "GMAIL_ADDRESS, GMAIL_APP_PASSWORD"):
                gold_alert.get_email_settings()

    def test_taobao_share_price_parser(self):
        page = '<a href="item.htm?id=992105119294&amp;price=909&amp;sourceType=item">item</a>'
        self.assertEqual(gold_alert.parse_taobao_share_price(page), 909.0)

    def test_taobao_price_includes_currency_conversion_and_premium(self):
        text = gold_alert.taobao_price_text(500, 1, snapshot(spot=100))
        self.assertIn("¥500.00", text)
        self.assertIn("A$100.00", text)
        self.assertIn("+0.0%", text)


class PassbookTests(unittest.TestCase):
    def test_append_creates_one_header_and_multiple_rows(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "gold_passbook.csv"
            with patch.object(gold_alert, "PASSBOOK_PATH", path):
                gold_alert.append_passbook(snapshot())
                gold_alert.append_passbook(snapshot(spot=101))
            lines = path.read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(lines), 3)
            self.assertEqual(
                lines[0],
                "Date,Spot_AUD_g,Spot_CNY_g,MA50_AUD,MA200_AUD,Est_Shop_AUD,Taobao_1g_CNY,Taobao_5g_CNY",
            )

    def test_portfolio_uses_per_gram_purchase_price(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "holdings.csv"
            path.write_text("Date,Grams,Price_Paid_AUD\n2026-03-10,5,238.00\n", encoding="utf-8")
            grams, cost = gold_alert.load_portfolio(path)
            self.assertEqual(grams, 5)
            self.assertEqual(cost, 1190)


if __name__ == "__main__":
    unittest.main()
