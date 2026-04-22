# Remote Access — Scan & Execute from Phone

*2026-03-30*

The Edge-Radar project runs on a Windows 11 desktop. These are options for scanning edges and placing bets remotely from a phone.

---

## Options

### 1. Scheduled Scans + Email (Easiest — Partially Done)

AgentMail is already configured to send daily edge reports to mikeschecht@gmail.com. Extend this:
- Schedule MLB/NBA scans via Windows Task Scheduler
- Have each scan email the top picks as a formatted table
- Review on phone, then remote in only when you want to execute

**Pros:** Already halfway built. Zero new infrastructure.
**Cons:** One-way — you can see edges but can't execute from the email.

---

### 2. Telegram Bot (Recommended — Best Phone UX)

A small Python script (~100 lines) running on the PC that listens for Telegram messages. Interactive from your phone:

```
You:    /mlb
Bot:    [edge table with top 10 MLB picks]

You:    /execute 1,3,5
Bot:    Placed 3 bets: White Sox @ Miami (YES $0.45), ...

You:    /status
Bot:    Balance: $51.14 | Positions: 17 | Today P&L: $0.00

You:    /settle
Bot:    Settled 5 bets. Net P&L: +$2.35
```

**How it works:**
- `python-telegram-bot` library (free, well-documented)
- Create a bot via @BotFather on Telegram (takes 30 seconds)
- Bot calls the same functions the CLI scripts use (`scan_all_markets`, `execute_pipeline`, `show_status`)
- Runs as a background process or Windows Service on the PC
- Push notifications on your phone when scans complete

**Pros:** Real-time, interactive, native phone UX, push notifications, free.
**Cons:** PC must be running. ~100 lines of new code.

**This is the recommended option** — the scan → review → pick → execute loop maps perfectly to a chat interface.

---

### 3. Cloudflare Tunnel + Web API (Most Powerful)

Run a FastAPI server on the PC, expose it through a Cloudflare Tunnel (free tier, no port forwarding or dynamic DNS needed).

```
https://edge-radar.yourdomain.com/scan/mlb
https://edge-radar.yourdomain.com/status
https://edge-radar.yourdomain.com/execute?picks=1,3,5
```

**How it works:**
- FastAPI wraps the existing scan/execute functions as REST endpoints
- Cloudflare Tunnel (`cloudflared`) creates a secure connection from your PC to a public URL
- Access from any browser on your phone
- Could add a simple HTML dashboard with buttons

**Pros:** Full web dashboard, accessible from any device, shareable.
**Cons:** More code (~200-300 lines), needs Cloudflare account, needs a domain (optional — can use `.trycloudflare.com` for free).

---

### 4. Remote Desktop (Zero Code)

Use Chrome Remote Desktop or Tailscale + RDP to access the PC from your phone.

**Setup:**
- Install Chrome Remote Desktop extension on desktop Chrome
- Install Chrome Remote Desktop app on phone
- Connect and run CLI commands directly

**Pros:** Works immediately, no code changes, full access to everything.
**Cons:** Clunky on phone screen, typing CLI commands on mobile is painful, no notifications.

---

### 5. Claude Code Remote Triggers

Use the `/schedule` skill to create remote agents that run on a cron. Results could be posted to a Google Chat space (via the ax-gcp MCP server) or emailed.

**Pros:** No new code, uses existing Claude Code infrastructure.
**Cons:** Execution still needs manual confirmation, less interactive than Telegram.

---

## Recommendation

**Start with Telegram bot.** It's the best balance of effort vs. usability:

| Criteria | Email | Telegram | Web API | Remote Desktop |
|----------|:-----:|:--------:|:-------:|:--------------:|
| Phone UX | Good | Best | Good | Poor |
| Can execute bets | No | Yes | Yes | Yes |
| Push notifications | Yes | Yes | No | No |
| Setup effort | Minimal | Small | Medium | Minimal |
| New code | ~20 lines | ~100 lines | ~300 lines | 0 |
| PC must be running | No (if scheduled) | Yes | Yes | Yes |
| Interactive | No | Yes | Yes | Yes |

The Telegram bot can be built to wrap the exact same functions the CLI uses, so all the edge detection, risk gates, and position tracking work identically.
