"""S3 (2026-08-26): venue/product eligibility — classify, remember, fail closed.

Between 2026-08-20 and 2026-08-25 Kalshi rejected **16 orders across 6 runs**
with a "Nevada residents are not currently allowed..." error. The account is in
California; that text is what any API key gets when it has not completed
Kalshi's periodic geolocation check. The fix was a click-through, and it took
six days, because three separate things failed:

1. the batch kept placing after the first rejection (3 orders in one second on
   08-20, 4 on 08-23),
2. nothing persisted the verdict, so every run rediscovered it, and
3. all three reporting surfaces truncated off the tail of the message, where
   the instruction lives.

These tests pin all three, using the **real** error body from the trade log.
"""

import json
from datetime import datetime, timedelta, timezone

import pytest

import venue_eligibility as vel

# The actual body stored on 2026-08-20, before the 200-char cap was removed.
REAL_ERROR = (
    '{"error":{"code":"Nevada_residents_are_not_currently_allowed_to_open_'
    'positions_in_Sports,_Elections_and_Entertainment._Check_your_email_for_'
    'more_details.","message":"Nevada residents are not currently allowed to '
    'open positions in Sports, Elections and Entertainment. Check your email '
    'for more details."}}'
)
TRUNCATED_ERROR = REAL_ERROR[:200]  # what the log actually held for five days


@pytest.fixture(autouse=True)
def _isolate_cache(tmp_path, monkeypatch):
    """Never read or write the operator's real eligibility cache.

    Same lesson as `_isolate_data_logs` in conftest: a test that blocks a venue
    must not disable the live account's trading.
    """
    monkeypatch.setattr(vel, "ELIGIBILITY_PATH",
                        tmp_path / "venue_eligibility.json")


class TestClassification:
    def test_the_real_error_is_structural(self):
        assert vel.is_structural_rejection(REAL_ERROR)

    def test_it_is_still_structural_after_the_logs_truncation(self):
        """The 200-char cap cut the `message` mid-sentence, but `code` carries
        the same text underscore-joined -- so detection survives it."""
        assert vel.is_structural_rejection(TRUNCATED_ERROR)

    @pytest.mark.parametrize("raw", [
        '{"error":{"code":"insufficient_balance"}}',
        '{"error":{"code":"deprecated_v1_order_endpoint","message":"Please switch to V2"}}',
        '{"error":{"code":"rate_limit_exceeded"}}',
        '{"error":{"code":"too_many_requests"}}',
        '{"error":{"code":"market_closed"}}',
        '{"error":{"code":"invalid_price"}}',
        "transport failure (placement UNKNOWN -- reconcile): read timeout",
        "", None,
    ])
    def test_transient_errors_never_disable_a_venue(self, raw):
        """A false positive here takes the account offline, so the transient
        list is checked FIRST and wins ties."""
        assert not vel.is_structural_rejection(raw)

    def test_the_six_v1_deprecation_rows_in_the_real_log_are_not_structural(self):
        """The other 6 of the log's 22 error rows are a v1->v2 endpoint change
        (2026-06-20). Those were genuinely transient -- four were successfully
        re-placed two days later -- and must not disable anything."""
        raw = ('{"error":{"code":"deprecated_v1_order_endpoint","message":'
               '"Please switch to the V2 endpoint"}}')
        assert not vel.is_structural_rejection(raw)

    @pytest.mark.parametrize("raw", [
        '{"error":{"code":"account_not_eligible"}}',
        '{"error":{"code":"restricted_jurisdiction"}}',
        '{"error":{"code":"kyc_required"}}',
        '{"error":{"code":"permission_denied"}}',
    ])
    def test_other_structural_shapes(self, raw):
        assert vel.is_structural_rejection(raw)


class TestTheMessageTail:
    """All three surfaces cut the end. The end is the only actionable part."""

    def test_full_message_survives_at_the_default_limit(self):
        assert "Check your email for more details" in vel.actionable_reason(REAL_ERROR)

    def test_the_old_110_char_cap_is_what_lost_it(self):
        """Regression pin: the digest's old `code[:110] + '...'` produced
        'Check you...'. Documented here so nobody reintroduces a tail cut."""
        code = json.loads(REAL_ERROR)["error"]["code"].replace("_", " ")
        assert len(code) == 135
        assert code[:110].endswith("Check you")
        assert "Check your email" in vel.actionable_reason(REAL_ERROR)

    def test_a_tight_budget_sacrifices_the_head_not_the_instruction(self):
        short = vel.actionable_reason(REAL_ERROR, limit=60)
        assert len(short) <= 62
        assert short.endswith("details.")
        assert "..." in short

    def test_empty_error_is_unknown_not_a_crash(self):
        assert vel.actionable_reason("") == "unknown"
        assert vel.actionable_reason(None) == "unknown"

    def test_unparseable_json_still_yields_the_code(self):
        assert "Nevada residents" in vel.actionable_reason(TRUNCATED_ERROR)


class TestFailClosed:
    def test_an_unrecorded_venue_is_unknown(self):
        assert vel.status("kalshi", "sports")[0] == "unknown"

    def test_a_corrupt_cache_is_unknown_not_ok(self, tmp_path, monkeypatch):
        bad = tmp_path / "bad.json"
        bad.write_text("{not json", encoding="utf-8")
        monkeypatch.setattr(vel, "ELIGIBILITY_PATH", bad)
        assert vel.status("kalshi", "sports")[0] == "unknown"

    def test_a_structural_rejection_blocks(self):
        assert vel.record_rejection("kalshi", "sports", REAL_ERROR) is True
        st, why = vel.status("kalshi", "sports")
        assert st == "blocked"
        assert "Check your email" in why

    def test_a_transient_rejection_does_not_block(self):
        assert vel.record_rejection("kalshi", "sports", "rate limit") is False
        assert vel.status("kalshi", "sports")[0] == "unknown"

    def test_the_full_body_is_kept_for_forensics(self):
        vel.record_rejection("kalshi", "sports", REAL_ERROR)
        entry = vel.load()["kalshi:sports"]
        assert entry["raw_error"] == REAL_ERROR
        assert len(entry["raw_error"]) > 200  # the old cap would have cut it

    def test_success_clears_a_block(self):
        vel.record_rejection("kalshi", "sports", REAL_ERROR)
        vel.record_success("kalshi", "sports", evidence="probe accepted")
        assert vel.status("kalshi", "sports")[0] == "ok"

    def test_time_alone_never_clears_a_block(self):
        """A restriction is not lifted by waiting. Only a real acceptance or an
        explicit probe clears it -- auto-retry is what produced six days."""
        vel.record_rejection("kalshi", "sports", REAL_ERROR,
                             now=datetime(2020, 1, 1, tzinfo=timezone.utc))
        assert vel.status("kalshi", "sports")[0] == "blocked"

    def test_an_ok_verdict_decays_to_unknown_after_the_ttl(self):
        """Kalshi says it will send further instructions 'as necessary to
        maintain access', so eligibility is a lease. A verdict that never
        expired is how the block went unnoticed for six days."""
        old = datetime.now(timezone.utc) - timedelta(days=vel.ELIGIBILITY_TTL_DAYS + 1)
        vel.record_success("kalshi", "sports", now=old)
        st, why = vel.status("kalshi", "sports")
        assert st == "unknown"
        assert "TTL" in why

    def test_a_fresh_ok_stands(self):
        vel.record_success("kalshi", "sports")
        assert vel.status("kalshi", "sports")[0] == "ok"

    def test_clear_returns_to_unknown(self):
        vel.record_success("kalshi", "sports")
        vel.clear("kalshi", "sports")
        assert vel.status("kalshi", "sports")[0] == "unknown"


class TestProductScoping:
    """The observed block named Sports, Elections and Entertainment -- not the
    whole venue. Disabling all of Kalshi would be over-broad."""

    def test_blocking_sports_leaves_prediction_alone(self):
        vel.record_rejection("kalshi", "sports", REAL_ERROR)
        assert vel.status("kalshi", "sports")[0] == "blocked"
        assert vel.status("kalshi", "prediction")[0] == "unknown"

    def test_venues_are_independent(self):
        vel.record_rejection("kalshi", "sports", REAL_ERROR)
        vel.record_success("polymarket", "sports")
        assert vel.status("kalshi", "sports")[0] == "blocked"
        assert vel.status("polymarket", "sports")[0] == "ok"

    @pytest.mark.parametrize("category,product", [
        ("game", "sports"), ("spread", "sports"), ("total", "sports"),
        ("futures", "sports"), ("championship", "sports"),
        ("crypto", "prediction"), ("weather", "prediction"),
        ("politics", "elections"),
        (None, "sports"), ("", "sports"), ("nonsense", "sports"),
    ])
    def test_category_maps_to_product(self, category, product):
        assert vel.product_for(category) == product


class TestExecutorWiring:
    def test_structural_handler_blocks_and_signals_abort(self, monkeypatch):
        import kalshi_executor as ke
        from opportunity import Opportunity
        monkeypatch.setattr(ke.vel, "ELIGIBILITY_PATH", vel.ELIGIBILITY_PATH)
        opp = Opportunity(
            ticker="KXMLSTOTAL-26AUG22ATXPHI-5", title="", category="total",
            side="yes", market_price=0.5, fair_value=0.6, edge=0.1,
            edge_source="t", confidence="high", liquidity_score=9.0,
            composite_score=9.0, details={},
        )
        assert ke._handle_structural(opp, REAL_ERROR, "kalshi", remaining=4) is True
        assert vel.status("kalshi", "sports")[0] == "blocked"

    def test_transient_error_does_not_abort_the_batch(self, monkeypatch):
        import kalshi_executor as ke
        from opportunity import Opportunity
        monkeypatch.setattr(ke.vel, "ELIGIBILITY_PATH", vel.ELIGIBILITY_PATH)
        opp = Opportunity(
            ticker="KXMLSTOTAL-26AUG22ATXPHI-5", title="", category="total",
            side="yes", market_price=0.5, fair_value=0.6, edge=0.1,
            edge_source="t", confidence="high", liquidity_score=9.0,
            composite_score=9.0, details={},
        )
        assert ke._handle_structural(opp, "insufficient_balance", "kalshi", 4) is False
        assert vel.status("kalshi", "sports")[0] == "unknown"


class TestDigestReporting:
    def test_daily_summary_prints_the_whole_instruction(self):
        from daily_summary import _error_reason
        assert "Check your email for more details" in _error_reason({"error": REAL_ERROR})

    def test_digest_handles_a_row_with_no_error_field(self):
        from daily_summary import _error_reason
        assert _error_reason({}) == "unknown"
