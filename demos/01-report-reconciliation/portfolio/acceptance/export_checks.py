"""Independent behavioral checks; supplied only after the model has finished."""
import csv
import io
import sys
from pathlib import Path
import unittest
sys.path.insert(0, str(Path.cwd()))
from app.exporter import export_csv


def row(**changes):
    item = dict(invoice_id="N-1",customer="NORTHSTAR",invoice_at="2026-08-01T00:00:00+00:00",settled_at="2026-09-15T12:00:00+00:00",status="PAID",gross_cents=10000,fee_cents=300,currency="USD")
    return {**item, **changes}


def records(rows, customer="NORTHSTAR", month="2026-09"):
    return list(csv.reader(io.StringIO(export_csv(rows,customer,month))))

class SettlementAcceptance(unittest.TestCase):
    def test_historical_period_keeps_invoice_export(self):
        self.assertEqual(export_csv([row()],"NORTHSTAR","2026-08"),"invoice_id,amount_cents\nN-1,10000\n")
    def test_columns_and_paid_net(self):
        self.assertEqual(records([row()]), [["invoice_id","settlement_date","net_cents"],["N-1","2026-09-15","9700"]])
    def test_local_month_includes_early_october_utc(self):
        self.assertEqual(records([row(settled_at="2026-10-01T03:30:00Z")])[1], ["N-1","2026-09-30","9700"])
    def test_local_month_excludes_early_september_utc(self):
        self.assertEqual(len(records([row(settled_at="2026-09-01T03:30:00Z")])), 1)
    def test_winter_timezone_offset(self):
        self.assertEqual(records([row(settled_at="2026-12-01T04:30:00Z")],month="2026-11")[1][1], "2026-11-30")
    def test_refund_does_not_return_fee(self):
        self.assertEqual(records([row(status="REFUNDED",gross_cents=5000,fee_cents=150)])[1][2], "-5000")
    def test_pending_and_void_ignore_absent_settlement(self):
        self.assertEqual(len(records([row(status="PENDING",settled_at=None), row(status="VOID",settled_at=None)])),1)
    def test_customer_isolation_and_csv_quoting(self):
        self.assertEqual(records([row(invoice_id='N,"quoted"'),row(customer="BLUEBIRD")])[1][0], 'N,"quoted"')
        self.assertEqual(len(records([row(customer="BLUEBIRD")])),1)
    def test_sort_order(self):
        result=records([row(invoice_id="Z"),row(invoice_id="B",settled_at="2026-09-01T12:00:00Z"),row(invoice_id="A")])
        self.assertEqual([item[0] for item in result[1:]], ["B","A","Z"])
    def test_unsupported_currency(self):
        with self.assertRaises(ValueError): records([row(currency="EUR")])
    def test_bad_money_and_missing_offset(self):
        for changes in ({"gross_cents":1.5},{"fee_cents":True},{"fee_cents":-1},{"settled_at":"2026-09-15T12:00:00"}):
            with self.subTest(changes=changes), self.assertRaises(ValueError): records([row(**changes)])
    def test_other_customers_keep_invoice_behavior(self):
        self.assertEqual(export_csv([row(customer="BLUEBIRD",invoice_at="2026-09-01T00:00:00Z",status="PENDING")],"BLUEBIRD","2026-09"),"invoice_id,amount_cents\nN-1,10000\n")

if __name__ == "__main__": unittest.main()
