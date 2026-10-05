import unittest
from app.exporter import export_csv

class ExistingExport(unittest.TestCase):
    def test_other_customer_invoice_month_and_columns(self):
        row = dict(invoice_id="B-1", customer="BLUEBIRD", invoice_at="2026-09-30T23:00:00+00:00", gross_cents=2500)
        self.assertEqual(export_csv([row], "BLUEBIRD", "2026-09"), "invoice_id,amount_cents\nB-1,2500\n")
        self.assertEqual(export_csv([row], "BLUEBIRD", "2026-10"), "invoice_id,amount_cents\n")
    def test_customer_isolation(self):
        row = dict(invoice_id="N-1", customer="NORTHSTAR", invoice_at="2026-09-01T00:00:00+00:00", gross_cents=2500)
        self.assertEqual(export_csv([row], "BLUEBIRD", "2026-09"), "invoice_id,amount_cents\n")
