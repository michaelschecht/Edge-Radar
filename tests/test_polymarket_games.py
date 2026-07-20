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
