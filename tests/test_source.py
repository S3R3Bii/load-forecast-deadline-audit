import sys
from pathlib import Path
import unittest
from decimal import Decimal as D
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from source import target_rows, native_load
from analyze import peak_summary


def rows():
    return [dict(DeliveryDate="10/25/2026",HourEnding=str(h)+":00",DSTFlag="N") for h in range(1,25)]


class SourceCases(unittest.TestCase):
    def test_complete_day(self):
        self.assertEqual(len(target_rows(rows(),"DeliveryDate","2026-10-25")),24)
    def test_missing_hour(self):
        with self.assertRaises(AssertionError):target_rows(rows()[:-1],"DeliveryDate","2026-10-25")
    def test_duplicate_hour(self):
        r=rows();r[-1]["HourEnding"]="1:00"
        with self.assertRaises(AssertionError):target_rows(r,"DeliveryDate","2026-10-25")
    def test_wrong_date(self):
        with self.assertRaises(AssertionError):target_rows(rows(),"DeliveryDate","2026-10-26")
    def test_unhandled_dst_fails(self):
        r=rows();r[1]["DSTFlag"]="Y"
        with self.assertRaises(AssertionError):target_rows(r,"DeliveryDate","2026-10-25")
    def test_non_hourly_fails(self):
        r=rows();r[0]["HourEnding"]="1:15"
        with self.assertRaises(AssertionError):target_rows(r,"DeliveryDate","2026-10-25")
    def test_bad_numeric(self):
        for value in ["-1","NaN","Infinity"]:
            with self.assertRaises(AssertionError):native_load(value)
    def test_peak_ties(self):
        r=[dict(hour_ending=h,forecast_mw=D(f),actual_mw=D(a)) for h,f,a in [(1,10,8),(2,10,10),(3,8,10)]]
        p=peak_summary(r)
        self.assertEqual(p["forecast_peak_hours"],"1|2")
        self.assertEqual(p["actual_peak_hours"],"2|3")
        self.assertEqual(p["includes_actual_peak"],1)
        self.assertEqual(p["peak_error_mw"],0)


if __name__=="__main__":
    unittest.main()
