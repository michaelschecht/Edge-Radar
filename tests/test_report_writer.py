"""Tests for report_writer — empty-day proof-of-life behavior.

The scheduled execute→email pairs rely on a report file always existing for
the run date, even on days where no opportunity clears the edge threshold.
Without one, the paired email task finds no report and silently skips sending
(feedback_sameday_empty_emails). save_execution_report([]) must therefore write
a valid "0 orders" report rather than bailing out.
"""

from report_writer import save_execution_report, save_scan_report


class TestEmptyExecutionReport:
    def test_empty_orders_still_writes_file(self, tmp_path):
        """A no-opportunity day must still produce a proof-of-life report."""
        rpt = save_execution_report([], report_type="sports",
                                    output_dir=str(tmp_path))
        assert rpt is not None
        written = list(tmp_path.glob("*_sports_execution.md"))
        assert len(written) == 1

    def test_empty_report_content(self, tmp_path):
        """The empty report shows 0 orders and $0.00 total cost."""
        save_execution_report([], report_type="sports", output_dir=str(tmp_path))
        content = next(tmp_path.glob("*_sports_execution.md")).read_text(encoding="utf-8")
        assert "0 orders" in content
        assert "total cost: $0.00" in content
        assert "## Orders" in content


class TestEmptyScanReport:
    def test_empty_scan_report_returns_none(self, tmp_path):
        """save_scan_report intentionally skips empty result sets — the
        execute-report path is what supplies the empty-day proof-of-life file."""
        rpt = save_scan_report([], report_type="sports", output_dir=str(tmp_path))
        assert rpt is None
        assert list(tmp_path.glob("*.md")) == []
