"""Tests for the PM1d Polymarket per-game edge detector (read-only)."""

import pytest

import polymarket_client as pm
import polymarket_futures_edge as pmf
import polymarket_games_edge as pmg
from opportunity import Opportunity


def _ml_market(**over):
    m = {
        "sportsMarketType": "moneyline",
        "question": "San Diego Padres vs. Atlanta Braves",
        "outcomes": '["San Diego Padres", "Atlanta Braves"]',
        "outcomePrices": '["0.435", "0.565"]',
        "bestBid": 0.43, "bestAsk": 0.44, "spread": 0.01,
        "line": None, "gameStartTime": "2099-07-21 23:15:00+00",
        "conditionId": "0x9bb9", "clobTokenIds": '["111", "222"]',
        "active": True, "closed": False,
    }
    m.update(over)
    return m


class TestIterGameRows:
    def test_parses_core_market_types(self):
        ev = {"markets": [
            _ml_market(),
            _ml_market(sportsMarketType="spreads",
                       question="Spread: Atlanta Braves (-1.5)",
                       outcomes='["Atlanta Braves", "San Diego Padres"]',
                       bestBid=0.38, bestAsk=0.40, line=-1.5, spread=0.02),
            _ml_market(sportsMarketType="totals",
                       question="San Diego Padres vs. Atlanta Braves: O/U 9.5",
                       outcomes='["Over", "Under"]',
                       bestBid=0.44, bestAsk=0.47, line=9.5, spread=0.03),
        ]}
        rows = pm.iter_game_rows(ev)
        assert [r["market_type"] for r in rows] == ["moneyline", "spreads", "totals"]
        assert rows[1]["line"] == -1.5
        assert rows[2]["line"] == 9.5
        assert rows[0]["yes_price"] == 0.44 and rows[0]["yes_bid"] == 0.43

    def test_skips_exotic_closed_and_degenerate(self):
        ev = {"markets": [
            _ml_market(sportsMarketType="baseball_team_first_five_total"),  # exotic
            _ml_market(closed=True),                                        # closed
            _ml_market(bestAsk=0, outcomePrices='["0", "1"]'),              # degenerate
            _ml_market(outcomes='["A", "B", "C"]'),                         # not binary
        ]}
        assert pm.iter_game_rows(ev) == []


class TestDetectGameMarketEdges:
    def _row(self, mtype, **over):
        base = {
            "market_type": mtype,
            "question": "San Diego Padres vs. Atlanta Braves",
            "outcomes": ["San Diego Padres", "Atlanta Braves"],
            "yes_price": 0.44, "yes_bid": 0.43, "line": None,
            "book_spread": 0.01, "game_start": "2099-07-21 23:15:00+00",
            "condition_id": "0x9bb9", "clob_token_ids": ["111", "222"],
            "volume": 100.0,
        }
        base.update(over)
        return base

    def test_moneyline_prices_both_sides(self, monkeypatch):
        fairs = {"San Diego Padres": 0.50, "Atlanta Braves": 0.50}
        meta = {"n_books": 9, "min_fair": 0.49, "max_fair": 0.51}
        monkeypatch.setattr(pmg, "consensus_fair_value",
                            lambda ev, team: (fairs[team], dict(meta)))
        opps = pmg.detect_game_market_edges(
            self._row("moneyline"), [{}], "MLB", "mlb-sd-atl-2099-07-21", "KXMLB")
        # YES side: fair .50 vs ask .44 → +6%. NO side: fair .50 vs (1-.43)=.57 → no edge.
        assert len(opps) == 1
        o = opps[0]
        assert o.side == "yes" and o.category == "game"
        assert abs(o.edge - 0.06) < 1e-9
        assert o.confidence == "high"
        assert o.details["venue"] == "polymarket"
        assert o.details["token_index"] == 0
        assert o.edge_source == "polymarket_vs_consensus"

    def test_spread_strike_is_negated_line(self, monkeypatch):
        seen = {}

        def fake_spread(ev, team, strike, ticker=""):
            seen.update(team=team, strike=strike, ticker=ticker)
            return 0.50, {"n_books": 5, "book_spread_range": 0.0}

        monkeypatch.setattr(pmg, "consensus_spread_prob", fake_spread)
        row = self._row("spreads", question="Spread: Atlanta Braves (-1.5)",
                        outcomes=["Atlanta Braves", "San Diego Padres"],
                        yes_price=0.40, yes_bid=0.38, line=-1.5)
        opps = pmg.detect_game_market_edges(row, [{}], "MLB", "slug", "KXMLB")
        assert seen == {"team": "Atlanta Braves", "strike": 1.5, "ticker": "KXMLB"}
        assert len(opps) == 1 and opps[0].category == "spread"
        assert abs(opps[0].edge - 0.10) < 1e-9

    def test_total_prices_over_and_under(self, monkeypatch):
        monkeypatch.setattr(pmg, "consensus_total_prob",
                            lambda ev, strike, ticker="": (0.55, {"n_books": 6}))
        row = self._row("totals", outcomes=["Over", "Under"],
                        yes_price=0.47, yes_bid=0.30, line=9.5)
        opps = pmg.detect_game_market_edges(row, [{}], "MLB", "slug", "KXMLB")
        # Over: fair .55 vs .47 → +8% (yes). Under: fair .45 vs (1-.30)=.70 → none.
        assert len(opps) == 1
        assert opps[0].side == "yes" and opps[0].category == "total"
        assert abs(opps[0].edge - 0.08) < 1e-9

    def test_no_consensus_yields_nothing(self, monkeypatch):
        monkeypatch.setattr(pmg, "consensus_fair_value", lambda ev, team: None)
        assert pmg.detect_game_market_edges(
            self._row("moneyline"), [{}], "MLB", "slug", "KXMLB") == []


class TestRouteFilter:
    def test_routing(self):
        assert pmf._route_filter(None) == ("futures", ["mlb", "nfl", "nba", "nhl"])
        assert pmf._route_filter("all") == ("futures", ["mlb", "nfl", "nba", "nhl"])
        assert pmf._route_filter("futures") == ("futures", [])
        assert pmf._route_filter("games") == (None, ["mlb", "nfl", "nba", "nhl"])
        assert pmf._route_filter("mlb-games") == (None, ["mlb"])
        assert pmf._route_filter("nba") == ("nba", [])  # a US futures key
        assert pmf._route_filter("worldcup") == (None, [])  # dropped in US repoint
        assert pmf._route_filter("cricket") == (None, [])


class TestScanOrchestration:
    @pytest.fixture(autouse=True)
    def _tmp_registry(self, tmp_path, monkeypatch):
        # The scan records ticker→token mappings; keep test writes out of the
        # real data/polymarket/market_registry.json.
        import market_registry
        monkeypatch.setattr(market_registry, "REGISTRY_PATH",
                            tmp_path / "market_registry.json")

    def test_skips_started_games_and_ambiguous_matchups(self, monkeypatch):
        past = _ml_market(gameStartTime="2020-01-01 00:00:00+00")
        future_ok = _ml_market()
        events = [
            {"title": "San Diego Padres vs. Atlanta Braves",
             "slug": "mlb-sd-atl", "markets": [future_ok]},
            {"title": "Chicago Cubs vs. Pittsburgh Pirates",
             "slug": "mlb-chc-pit", "markets": [past]},          # started → skipped
        ]
        odds = [{"id": 1, "commence_time": "2099-07-21T23:15:00Z"}]
        monkeypatch.setattr(pmg.pm, "get_tag_id", lambda slug: "100381")
        monkeypatch.setattr(pmg.pm, "fetch_game_events", lambda tag_id: events)
        monkeypatch.setattr(pmg, "fetch_odds_api", lambda k, markets: odds)
        monkeypatch.setattr(pmg, "_event_has_matchup", lambda e, a, b: True)
        monkeypatch.setattr(pmg, "consensus_fair_value",
                            lambda ev, team: (0.60, {"n_books": 9, "min_fair": 0.59,
                                                     "max_fair": 0.61}))
        opps = pmg.scan_polymarket_games(min_edge=0.03, sports=["mlb"])
        # Only the pre-game event priced; both ML sides evaluated, YES has edge.
        assert opps and all(isinstance(o, Opportunity) for o in opps)
        assert all("sd-atl" in o.ticker for o in opps)

    def test_series_game_on_other_date_not_priced_against_wrong_odds(self, monkeypatch):
        # Same matchup, but the PM game starts 2 days after the only odds
        # event — the start-time window must refuse the match (series bug).
        later = _ml_market(gameStartTime="2099-07-23 23:15:00+00")
        events = [{"title": "San Diego Padres vs. Atlanta Braves",
                   "slug": "mlb-sd-atl-2", "markets": [later]}]
        odds = [{"id": 1, "commence_time": "2099-07-21T23:15:00Z"}]
        monkeypatch.setattr(pmg.pm, "get_tag_id", lambda slug: "100381")
        monkeypatch.setattr(pmg.pm, "fetch_game_events", lambda tag_id: events)
        monkeypatch.setattr(pmg, "fetch_odds_api", lambda k, markets: odds)
        monkeypatch.setattr(pmg, "_event_has_matchup", lambda e, a, b: True)
        monkeypatch.setattr(pmg, "consensus_fair_value",
                            lambda ev, team: (0.99, {"n_books": 9, "min_fair": 0.98,
                                                     "max_fair": 0.99}))
        assert pmg.scan_polymarket_games(min_edge=0.01, sports=["mlb"]) == []


class TestGamesCompositeCalibration:
    """C10 extension (2026-07-31): the games composite scales edge as
    `edge / 0.01`, matching the sports composite in `edge_detector.py`.

    This file was written on 2026-07-20, three days before C10, and copied
    `edge * 20` from `polymarket_futures_edge` -- which had itself copied it
    from the `liquidity` line above it. C10 fixed both futures paths and left
    this one, so games kept the 5x-stricter scale (saturating at 50% edge
    rather than 10%).

    The consequence was identical and independently confirmed: across 362
    logged Gamma game rows, not one ever reached MIN_COMPOSITE_SCORE=6.0
    (max observed 5.30). Gate 4 was structurally unreachable.
    """

    @staticmethod
    def _score(edge: float, confidence: str, book_spread: float = 0.02) -> float:
        opp = pmg._build_opp(
            slug="mlb-sd-atl", label="MLB", bet_type="ML", pick="San Diego Padres",
            side="yes", price=0.40, fair=0.40 + edge, confidence=confidence,
            row={"book_spread": book_spread, "game_start": "2099-07-21 23:15:00+00",
                 "condition_id": "0x9bb9", "clob_token_ids": ["111", "222"],
                 "question": "San Diego Padres vs. Atlanta Braves"},
            meta={"n_books": 9}, token_index=0,
        )
        assert opp is not None and abs(opp.edge - edge) < 1e-6
        return opp.composite_score

    def test_edge_saturates_at_ten_percent_not_fifty(self):
        # The regression guard. Under `edge * 20` a 10% edge contributed only
        # 2.0 to the edge term; aligned, it saturates the term at 10.0.
        # medium conf (6), book_spread 0.02 -> liquidity 10 - 0.02*100 = 8.0.
        expected = 0.4 * 10 + 0.3 * 6 + 0.2 * 8.0 + 0.5
        assert self._score(0.10, "medium") == pytest.approx(round(expected, 1), abs=0.05)

    def test_realistic_edge_can_now_clear_gate_four(self):
        # The shape real game rows produce. Under the old scale this needed
        # ~26% edge at medium confidence and could never happen.
        assert self._score(0.06, "medium") >= 6.0
        assert self._score(0.04, "high") >= 6.0

    def test_not_a_floodgate(self):
        # The 1-3% edges that dominate the observed board stay below the gate
        # on their own merits, and low confidence still cannot buy its way in
        # at a realistic edge.
        assert self._score(0.01, "medium") < 6.0
        assert self._score(0.03, "medium") < 6.0
        assert self._score(0.07, "low") < 6.0

    def test_matches_sports_composite_at_equal_inputs(self):
        # Cross-surface parity: at the same edge, confidence and liquidity,
        # the games composite must equal the sports formula in edge_detector.
        #
        # Scoped to `medium` deliberately. Parity holds for medium and low but
        # NOT for high: C4 capped sports high->medium (6) on settled Kalshi
        # evidence, while this path still weights high at 9 for want of any
        # settled Polymarket data. Asserting parity at `high` would encode a
        # decision that has not been made -- see the conf_score note in
        # _build_opp.
        # (Liquidity is supplied directly here because the two paths derive it
        # from differently-scaled spreads by design -- see _build_opp.)
        edge, liquidity = 0.05, 8.0
        sports = (min(edge / 0.01, 10) * 0.40
                  + {"low": 3, "medium": 6, "high": 6}["medium"] * 0.30
                  + liquidity * 0.20 + 5 * 0.10)
        assert self._score(edge, "medium") == pytest.approx(round(sports, 1), abs=0.05)
