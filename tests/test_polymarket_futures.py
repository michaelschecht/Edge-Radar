"""Tests for the Phase 1 Polymarket futures edge detector (read-only)."""

import polymarket_client as pm
import polymarket_futures_edge as pmf
from opportunity import Opportunity


# ── polymarket_client ────────────────────────────────────────────────────────

class TestParseJsonField:
    def test_json_string(self):
        assert pm._parse_json_field('["Yes", "No"]') == ["Yes", "No"]

    def test_already_list(self):
        assert pm._parse_json_field(["a", "b"]) == ["a", "b"]

    def test_none_returns_default(self):
        assert pm._parse_json_field(None, []) == []

    def test_malformed_returns_default(self):
        assert pm._parse_json_field("not json", "fallback") == "fallback"


class TestIterFutureCandidates:
    def _event(self, markets):
        return {"title": "World Cup Winner", "markets": markets}

    def test_normalizes_live_candidate(self):
        ev = self._event([{
            "groupItemTitle": "Spain",
            "question": "Will Spain win the 2026 FIFA World Cup?",
            "outcomes": '["Yes", "No"]',
            "outcomePrices": '["0.22", "0.78"]',
            "bestBid": 0.219, "bestAsk": 0.22,
            "conditionId": "0xabc", "clobTokenIds": '["111","222"]',
            "volume": 100.0, "liquidity": 50.0,
            "active": True, "closed": False,
        }])
        cands = pm.iter_future_candidates(ev)
        assert len(cands) == 1
        c = cands[0]
        assert c["candidate"] == "Spain"
        assert c["yes_price"] == 0.22          # bestAsk preferred
        assert c["yes_bid"] == 0.219
        assert c["clob_token_ids"] == ["111", "222"]

    def test_skips_closed_and_degenerate(self):
        ev = self._event([
            {"groupItemTitle": "Brazil", "outcomePrices": '["0","1"]',
             "bestAsk": 0.001, "active": True, "closed": True},          # eliminated
            {"groupItemTitle": "Nowhere", "outcomePrices": '["0","1"]',
             "bestAsk": 0.0, "active": True, "closed": False},           # degenerate price
        ])
        assert pm.iter_future_candidates(ev) == []

    def test_falls_back_to_outcomeprice_when_no_ask(self):
        ev = self._event([{
            "groupItemTitle": "France", "outcomePrices": '["0.39", "0.61"]',
            "bestAsk": 0, "bestBid": 0, "active": True, "closed": False,
        }])
        cands = pm.iter_future_candidates(ev)
        assert cands and cands[0]["yes_price"] == 0.39


# ── polymarket_futures_edge ──────────────────────────────────────────────────

def _fair(name_to_fv):
    """Build a fair_values dict in the shape consensus_outright_fair_values returns."""
    return {name: {"fair_value": fv, "n_books": 8, "min": fv - 0.01, "max": fv + 0.01}
            for name, fv in name_to_fv.items()}


class TestDetectEdgeFutures:
    def test_positive_edge_yields_opportunity(self):
        cand = {"candidate": "Spain", "yes_price": 0.22, "yes_bid": 0.219,
                "condition_id": "0xabc123def456", "clob_token_ids": ["1"], "volume": 5.0}
        fv = _fair({"Spain": 0.30})  # sportsbook says 30%, PM asks 22% → +8% edge
        opp = pmf.detect_edge_futures_polymarket(cand, fv, "World Cup Winner", "worldcup")
        assert isinstance(opp, Opportunity)
        assert opp.side == "yes"
        assert opp.category == "futures"
        assert opp.edge_source == "polymarket_vs_outrights"
        assert opp.details["venue"] == "polymarket"
        assert abs(opp.edge - 0.08) < 1e-6
        assert opp.market_price == 0.22
        assert opp.fair_value == 0.30
        assert opp.ticker.startswith("PM-worldcup-")

    def test_no_match_returns_none(self):
        cand = {"candidate": "Atlantis", "yes_price": 0.10, "yes_bid": 0.09}
        opp = pmf.detect_edge_futures_polymarket(cand, _fair({"Spain": 0.30}),
                                                 "World Cup Winner", "worldcup")
        assert opp is None

    def test_negative_edge_returns_none(self):
        # PM ask 0.40 > sportsbook fair 0.30 → no YES edge
        cand = {"candidate": "Spain", "yes_price": 0.40, "yes_bid": 0.39}
        opp = pmf.detect_edge_futures_polymarket(cand, _fair({"Spain": 0.30}),
                                                 "World Cup Winner", "worldcup")
        assert opp is None


class TestScanOrchestration:
    def test_scan_filters_by_min_edge_and_sorts(self, monkeypatch):
        # Two candidates: one +8% edge, one +1% edge. min_edge=0.05 drops the small one.
        monkeypatch.setattr(pmf.pm, "find_event", lambda slug, search: {"markets": [1]})
        monkeypatch.setattr(pmf.pm, "iter_future_candidates", lambda ev: [
            {"candidate": "Spain", "yes_price": 0.22, "yes_bid": 0.21},
            {"candidate": "England", "yes_price": 0.21, "yes_bid": 0.20},
        ])
        monkeypatch.setattr(pmf, "fetch_outrights", lambda k: [{"stub": True}])
        monkeypatch.setattr(pmf, "consensus_outright_fair_values",
                            lambda ev: _fair({"Spain": 0.30, "England": 0.22}))

        opps = pmf.scan_polymarket_futures(min_edge=0.05, ticker_filter="worldcup")
        assert [o.details["candidate"] for o in opps] == ["Spain"]  # England's +1% dropped

    def test_unknown_filter_returns_empty(self):
        assert pmf.scan_polymarket_futures(ticker_filter="cricket-world-domination") == []
