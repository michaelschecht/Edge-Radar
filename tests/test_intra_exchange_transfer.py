"""Kalshi sharded the exchange on 2026-08-24 and cash does not follow the markets.

Every assertion about the wire format here is a live 400 that came back from Kalshi
while getting the first transfer through -- a mock would have agreed with any of the
three wrong bodies. See CHANGELOG 2026-08-27.
"""

import pytest

from kalshi_client import KalshiClient, V2_XFER_PATH


@pytest.fixture
def client(monkeypatch):
    c = KalshiClient.__new__(KalshiClient)
    c.dry_run = False
    c.is_demo = False
    c._posted = []
    monkeypatch.setattr(
        c, "_post",
        lambda path, body=None: c._posted.append((path, body)) or {"ok": True},
        raising=False,
    )
    return c


def test_rejects_same_instance_and_shard(client):
    with pytest.raises(ValueError, match="same instance and shard"):
        client.intra_exchange_transfer(15.0, 0, 0)


def test_same_shard_is_allowed_across_instances(client):
    """0 -> 0 is only a no-op when the instance matches too."""
    client.intra_exchange_transfer(15.0, 0, 0, destination="margined")
    assert client._posted[0][1]["destination"] == "margined"


@pytest.mark.parametrize("amount", [0, -1, -0.0001])
def test_rejects_non_positive_amount(client, amount):
    with pytest.raises(ValueError, match="positive"):
        client.intra_exchange_transfer(amount, 0, 3)


@pytest.mark.parametrize("bad", ["", "event-contract", "EVENT_CONTRACT", "default"])
def test_rejects_unknown_instance(client, bad):
    """Kalshi's own error for this was `invalid exchange instance: ""`."""
    with pytest.raises(ValueError, match="must be one of"):
        client.intra_exchange_transfer(15.0, 0, 3, source=bad)


def test_dry_run_blocks_the_transfer(client):
    client.dry_run = True
    resp = client.intra_exchange_transfer(15.0, 0, 3)
    assert resp["status"] == "dry_run_blocked"
    assert client._posted == [], "DRY_RUN must not reach the venue"


def test_body_matches_the_documented_schema(client):
    client.intra_exchange_transfer(15.0, 0, 3)
    path, body = client._posted[0]
    assert path == V2_XFER_PATH
    assert body == {
        "source": "event_contract",
        "destination": "event_contract",
        "amount": 150_000,          # centicents: 10000 == $1.00
        "source_exchange_shard": 0,
        "destination_exchange_shard": 3,
    }


def test_amount_is_int_centicents(client):
    """Three separate live 400s live in this one assertion.

    `"15.0000"` -> `cannot unmarshal string into Go struct field ...amount of
    type int64`; plain cents would have moved 1/100th of the intended sum; and
    the field is `..._exchange_shard`, not `..._exchange_index`, which is why
    the first corrected attempt still reported `invalid source: ""`.
    """
    client.intra_exchange_transfer(15.0, 0, 3)
    amount = client._posted[0][1]["amount"]
    assert amount == 150_000 and isinstance(amount, int)
    assert "source_exchange_index" not in client._posted[0][1]


def test_sub_cent_amount_rounds_rather_than_truncating(client):
    client.intra_exchange_transfer(0.00009, 0, 3)
    assert client._posted[0][1]["amount"] == 1
