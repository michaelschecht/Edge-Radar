"""Tests for the Polymarket US market-data client + shared Ed25519 signing."""

import base64

import pytest

import polymarket_us_auth as auth
import polymarket_us_data as usd

# A valid base64 Ed25519 secret (64 bytes) so the signer can build.
_SECRET = base64.b64encode(b"\x02" * 64).decode()


# ── shared signing (polymarket_us_auth) ──────────────────────────────────────

class TestSignedHeaders:
    def test_headers_present_and_signature_verifies_bare_path(self):
        signer = auth.load_signer(_SECRET)
        headers = auth.signed_headers("key-123", signer, "GET", "/v1/account/balances")
        assert headers["X-PM-Access-Key"] == "key-123"
        assert headers["X-PM-Timestamp"].isdigit()
        assert headers["Content-Type"] == "application/json"
        # The signature must verify against the message "{ts}{method}{path}".
        msg = f"{headers['X-PM-Timestamp']}GET/v1/account/balances".encode()
        pub = signer.public_key()
        pub.verify(base64.b64decode(headers["X-PM-Signature"]), msg)  # raises if bad

    def test_signature_is_path_specific(self):
        signer = auth.load_signer(_SECRET)
        h = auth.signed_headers("k", signer, "GET", "/v1/orders")
        pub = signer.public_key()
        wrong = f"{h['X-PM-Timestamp']}GET/v1/markets".encode()
        with pytest.raises(Exception):
            pub.verify(base64.b64decode(h["X-PM-Signature"]), wrong)


# ── question matching ────────────────────────────────────────────────────────

class TestQuestionMatches:
    def test_matches_all_words_whole_word(self):
        assert usd.question_matches("World Series Champion", ("world series champion",))
        assert usd.question_matches("2027 NBA Champion", ("nba champion",))

    def test_whole_word_excludes_wnba(self):
        # "nba champion" must not match "WNBA Champion".
        assert not usd.question_matches("WNBA Champion", ("nba champion",))

    def test_exclude_words_drop_near_misses(self):
        # Conference boards contain both "nba" and "champion" — exclude drops them.
        assert not usd.question_matches(
            "NBA Eastern Conference Champion", ("nba champion",),
            exclude=("conference",))

    def test_no_term_matches_returns_false(self):
        assert not usd.question_matches("Pro Football MVP", ("pro football champion",))


# ── candidate extraction ─────────────────────────────────────────────────────

def _mkt(question, team, league, ask, bid, slug):
    return {
        "question": question, "slug": slug, "sportsMarketType": "futures",
        "bestAskQuote": {"value": str(ask), "currency": "USD"},
        "bestBidQuote": {"value": str(bid), "currency": "USD"},
        "marketSides": [
            {"description": "Yes", "price": str(ask),
             "team": {"name": team, "league": league}},
            {"description": "No", "price": str(round(1 - ask, 4))},
        ],
    }


class TestChampionshipCandidates:
    def _board(self):
        return [
            _mkt("World Series Champion", "Los Angeles Dodgers", "mlb", 0.32, 0.319,
                 "tec-mlb-champ-lad"),
            _mkt("World Series Champion", "New York Yankees", "mlb", 0.129, 0.128,
                 "tec-mlb-champ-nyy"),
            _mkt("National League Champion", "New York Mets", "mlb", 0.10, 0.09,
                 "tec-mlb-nlchamp-nym"),   # different championship — must not match
        ]

    def test_extracts_only_matching_championship(self):
        cands = usd.championship_candidates(
            self._board(), ("world series champion",), league="mlb")
        names = {c["candidate"] for c in cands}
        assert names == {"Los Angeles Dodgers", "New York Yankees"}

    def test_candidate_shape_uses_ask_and_slug(self):
        c = usd.championship_candidates(
            self._board(), ("world series champion",), league="mlb")[0]
        assert c["yes_price"] == 0.32       # bestAskQuote (tradeable ask)
        assert c["yes_bid"] == 0.319
        assert c["market_slug"] == "tec-mlb-champ-lad"

    def test_league_scope_filters(self):
        assert usd.championship_candidates(
            self._board(), ("world series champion",), league="nfl") == []

    def test_skips_zero_ask(self):
        board = [_mkt("World Series Champion", "Dead Team", "mlb", 0.0, 0.0, "s")]
        assert usd.championship_candidates(board, ("world series champion",)) == []


class TestFetchOpenFutures:
    def test_paginates_and_filters(self, monkeypatch):
        monkeypatch.setattr(usd.PolymarketUSData, "__init__", lambda self: None)
        client = usd.PolymarketUSData()
        pages = {
            0: {"markets": [{"sportsMarketType": "futures", "closed": False, "id": i}
                            for i in range(500)]},
            500: {"markets": [
                {"sportsMarketType": "futures", "closed": False, "id": 500},
                {"sportsMarketType": "moneyline", "closed": False, "id": 501},  # dropped
                {"sportsMarketType": "futures", "closed": True, "id": 502},     # dropped
            ]},
        }
        client._get = lambda path: pages[int(path.split("offset=")[1])]
        out = client.fetch_open_futures()
        assert len(out) == 501  # 500 + 1 open future; non-future & closed dropped
        assert all(m["sportsMarketType"] == "futures" and not m["closed"] for m in out)

    def test_missing_creds_raise(self, monkeypatch):
        from types import SimpleNamespace
        monkeypatch.setattr(usd, "get_config", lambda: SimpleNamespace(
            polymarket=SimpleNamespace(key_id="", secret_key="", host="h")))
        with pytest.raises(FileNotFoundError, match="POLYMARKET_KEY_ID"):
            usd.PolymarketUSData()
