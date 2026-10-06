import unittest
from app.jobs import run_job
class DecoderBehavior(unittest.TestCase):
    def test_daily_v2(self):
        self.assertEqual(run_job("daily_sales", [{"schema_version":"2", "kind":"SALE", "amount_cents":10000}]),10000)
