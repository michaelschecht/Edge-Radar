# Portable: use PYTHON env var if set, else try venv, else fall back to system python
PYTHON ?= $(shell if [ -x .venv/Scripts/python.exe ]; then echo .venv/Scripts/python.exe; elif [ -x .venv/bin/python ]; then echo .venv/bin/python; else echo python; fi)

# ── Scanning ─────────────────────────────────────────────────────────────────

scan-mlb:
	$(PYTHON) scripts/scan.py sports --filter mlb --date today --exclude-open --save

scan-nba:
	$(PYTHON) scripts/scan.py sports --filter nba --date today --exclude-open --save

scan-nhl:
	$(PYTHON) scripts/scan.py sports --filter nhl --date today --exclude-open --save

scan-nfl:
	$(PYTHON) scripts/scan.py sports --filter nfl --date today --exclude-open --save

scan-sports:
	$(PYTHON) scripts/scan.py sports --date today --exclude-open --save

scan-futures:
	$(PYTHON) scripts/scan.py futures --min-edge 0.01 --top 30

scan-predictions:
	$(PYTHON) scripts/scan.py prediction --min-edge 0.03 --top 20

scan-polymarket:
	$(PYTHON) scripts/scan.py polymarket --min-edge 0.03 --top 20

scan-all: scan-sports scan-futures scan-predictions scan-polymarket

# ── Portfolio Management ─────────────────────────────────────────────────────

status:
	$(PYTHON) scripts/kalshi/kalshi_executor.py status

risk:
	$(PYTHON) scripts/kalshi/risk_check.py

settle:
	$(PYTHON) scripts/kalshi/kalshi_settler.py settle

report:
	$(PYTHON) scripts/kalshi/kalshi_settler.py report --detail --save

reconcile:
	$(PYTHON) scripts/kalshi/kalshi_settler.py reconcile

backtest:
	$(PYTHON) scripts/backtest/backtester.py

backtest-sim:
	$(PYTHON) scripts/backtest/backtester.py --simulate --save

# ── Testing ──────────────────────────────────────────────────────────────────

test:
	$(PYTHON) -m pytest tests/ -v

test-quick:
	$(PYTHON) -m pytest tests/ -x -q

# ── Lint ─────────────────────────────────────────────────────────────────────

lint-config:
	$(PYTHON) scripts/lint/check_config_centralization.py

# ── Setup ────────────────────────────────────────────────────────────────────

doctor:
	$(PYTHON) scripts/doctor.py

install:
	pip install -r requirements.txt
	pip install -e .

hooks:
	pip install pre-commit
	pre-commit install

# ── Help ─────────────────────────────────────────────────────────────────────

help:
	@echo "Edge-Radar Makefile"
	@echo ""
	@echo "Scanning:"
	@echo "  make scan-mlb          Scan MLB (today, exclude open)"
	@echo "  make scan-nba          Scan NBA"
	@echo "  make scan-nhl          Scan NHL"
	@echo "  make scan-nfl          Scan NFL"
	@echo "  make scan-sports       Scan all sports"
	@echo "  make scan-futures      Scan championship futures"
	@echo "  make scan-predictions  Scan prediction markets"
	@echo "  make scan-polymarket   Scan Polymarket cross-ref"
	@echo "  make scan-all          Scan everything"
	@echo ""
	@echo "Portfolio:"
	@echo "  make status            Portfolio status"
	@echo "  make risk              Risk dashboard"
	@echo "  make settle            Settle completed bets"
	@echo "  make report            P&L report (saved to file)"
	@echo "  make reconcile         Verify trade log integrity"
	@echo "  make backtest          Run backtester (full report)"
	@echo "  make backtest-sim      Run backtester with strategy simulation"
	@echo ""
	@echo "Other:"
	@echo "  make test              Run full test suite"
	@echo "  make test-quick        Run tests (stop on first failure)"
	@echo "  make lint-config       Guard against os.getenv/os.environ regression"
	@echo "  make doctor            Validate environment setup"
	@echo "  make install           Install dependencies"
	@echo "  make hooks             Install pre-commit hooks"

.PHONY: scan-mlb scan-nba scan-nhl scan-nfl scan-sports scan-futures scan-predictions scan-polymarket scan-all status risk settle report reconcile backtest backtest-sim test test-quick lint-config doctor install hooks help
