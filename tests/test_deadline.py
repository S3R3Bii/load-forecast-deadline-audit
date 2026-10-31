"""Authored edge cases have expected results independent of real cohort scores."""

import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from deadline import select, aware
from analyze import metrics
from decimal import Decimal as D


def doc(ident, stamp):
    return dict(DocID=ident, PublishDate=stamp)


class DeadlineTests(unittest.TestCase):
    def test_latest_before_deadline(self):
        r = select(
            [
                doc("old", "2026-10-24T10:30:00-05:00"),
                doc("good", "2026-10-24T11:30:00-05:00"),
                doc("late", "2026-10-24T12:30:00-05:00"),
            ],
            "2026-10-24T12:00:00-05:00",
        )
        self.assertEqual(r["doc_id"], "good")
        self.assertEqual(r["age_seconds"], 1800)

    def test_equal_deadline_is_eligible(self):
        self.assertEqual(
            select(
                [doc("equal", "2026-10-24T12:00:00-05:00")], "2026-10-24T12:00:00-05:00"
            )["status"],
            "SELECTED",
        )

    def test_late_only_never_falls_forward(self):
        self.assertEqual(
            select(
                [doc("late", "2026-10-24T12:00:01-05:00")], "2026-10-24T12:00:00-05:00"
            )["status"],
            "UNAVAILABLE",
        )

    def test_empty_is_unavailable(self):
        self.assertEqual(
            select([], "2026-10-24T12:00:00-05:00")["status"], "UNAVAILABLE"
        )

    def test_stale_fails(self):
        self.assertEqual(
            select(
                [doc("stale", "2026-10-24T10:29:59-05:00")], "2026-10-24T12:00:00-05:00"
            )["status"],
            "UNAVAILABLE",
        )

    def test_age_boundary(self):
        self.assertEqual(
            select(
                [doc("boundary", "2026-10-24T10:30:00-05:00")],
                "2026-10-24T12:00:00-05:00",
            )["status"],
            "SELECTED",
        )

    def test_publication_tie_fails(self):
        self.assertEqual(
            select(
                [
                    doc("a", "2026-10-24T11:30:00-05:00"),
                    doc("b", "2026-10-24T11:30:00-05:00"),
                ],
                "2026-10-24T12:00:00-05:00",
            )["reason"],
            "ambiguous publication tie",
        )

    def test_duplicate_identity_fails(self):
        self.assertEqual(
            select(
                [
                    doc("a", "2026-10-24T10:30:00-05:00"),
                    doc("a", "2026-10-24T11:30:00-05:00"),
                ],
                "2026-10-24T12:00:00-05:00",
            )["reason"],
            "duplicate document identity",
        )

    def test_naive_deadline_fails(self):
        with self.assertRaises(ValueError):
            select([], "2026-10-24T12:00:00")

    def test_naive_publication_fails(self):
        with self.assertRaises(ValueError):
            select([doc("bad", "2026-10-24T11:00:00")], "2026-10-24T12:00:00-05:00")

    def test_offsets_compare_instants(self):
        self.assertEqual(
            select(
                [doc("utc", "2026-10-24T16:30:00+00:00")], "2026-10-24T12:00:00-05:00"
            )["age_seconds"],
            1800,
        )

    def test_negative_age_limit_fails(self):
        with self.assertRaises(ValueError):
            select([], "2026-10-24T12:00:00-05:00", -1)

    def test_closed_form_metrics(self):
        rows = [
            dict(
                error_mw=x,
                actual_mw="10",
                published_after_start=0,
                published_after_end=0,
                violates_day_ahead=0,
            )
            for x in ["-3", "4"]
        ]
        m = metrics(rows)
        self.assertEqual(m["sum_squared"], D(25))
        self.assertEqual(m["mae_mw"], D("3.5"))
        self.assertEqual(m["wape"], D(".35"))
        self.assertEqual(m["mean_error_mw"], D(".5"))
        self.assertEqual(m["max_under_mw"], D(3))

    def test_zero_wape_denominator_unavailable(self):
        m = metrics(
            [
                dict(
                    error_mw="3",
                    actual_mw="0",
                    published_after_start=0,
                    published_after_end=0,
                    violates_day_ahead=0,
                )
            ]
        )
        self.assertEqual(m["wape"], "UNAVAILABLE")
        self.assertEqual(m["max_under_mw"], D(0))


if __name__ == "__main__":
    unittest.main()
