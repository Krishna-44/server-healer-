# 🩹 Healer — universal crash-healer

A tiny, **cross-platform self-healing service**. Tell it which apps/ports are
critical; it watches them and, the instant one **crashes, stops listening, hangs,
or fails its health check**, it **restarts it** — with a new PID, on the same
port — usually in a few seconds. Install once and it runs in the background and
**auto-starts at login** so your services stay up 24×7.

Think of it as a small, friendly `systemd` / `supervisord` / `PM2` that works the
same way on **Windows, Linux, and macOS**.

---

## What it does

- **Monitors** each service you enable: TCP port listening, HTTP health URL +
  latency, WebSocket handshake, RTSP cameras, or just process-presence.
- **Heals** crashed services: gracefully kills the stuck owner *(guarded by a
  process-fingerprint + a protected-process denylist so it never kills the wrong
  thing)*, waits for the port to free, relaunches it, and **validates** the new
  instance is actually healthy before declaring success.
- **Won't loop forever**: per-service cooldown, a sliding restart-window, and a
  **circuit breaker** stop flapping; databases / remote devices can be set to
  *monitor + alert only* (never restarted).
- **Optional alerts**: set `alert_webhook` in the config (Slack/Discord/Teams).

## Install (≈30 seconds)

Requires **Python 3** on PATH. `psutil` is installed automatically.

| OS | Run |
|----|-----|
| **Windows** | double-click **`install.cmd`** (or `python install.py`) |
| **Linux** | `sh install.sh` (or `python3 install.py`) |
| **macOS** | `sh install.sh` (or `python3 install.py`) |

The installer **detects your OS** and registers the right auto-start mechanism:

- **Windows** → a Scheduled Task at logon (`healer-watchdog`)
- **Linux** → a `systemd --user` service (`Restart=always`); falls back to `cron @reboot`
- **macOS** → a `LaunchAgent` (`KeepAlive`) in `~/Library/LaunchAgents`

> Preview first without changing anything: `python install.py --dry-run`

## Configure — `healer.config.json`

Everything is **OFF by default** (a fresh install does nothing until you add your
apps). Open `healer.config.json`, edit an example, and set `"enabled": true`:

```jsonc
{
  "name": "my-app",
  "enabled": true,
  "host": "127.0.0.1",
  "port": 3000,
  "health_url": "http://127.0.0.1:3000/",
  "recover": true,
  "proc_match": "node",
  "restart": { "argv": ["node", "server.js"], "cwd": "/path/to/app", "log": "logs/my-app.log" }
}
```

- `recover: false` → **monitor + alert only** (use for cameras, DBs, remote gear
  you can't restart).
- `port: 0` + `proc_match` → watch a port-less process by name (ffmpeg, a worker…).

Changes take effect on the next restart of the service (re-run the installer, or
`systemctl --user restart healer-watchdog` / re-run `install.cmd`).

## Uninstall

| OS | Run |
|----|-----|
| Windows | double-click **`uninstall.cmd`** (or `python uninstall.py`) |
| Linux / macOS | `sh uninstall.sh` (or `python3 uninstall.py`) |

Removes the auto-start entry and stops the daemon. Your config + logs stay; delete
the folder to remove everything.

## Logs

Written next to Healer in `logs/`:
`watchdog_incidents.jsonl` (every crash + heal, with PIDs & duration),
`watchdog_status.json` (latest scan), `healer-daemon.log` (daemon output).

```bash
python port_watchdog.py --scan --config healer.config.json     # one-off health check
python port_watchdog.py --status --config healer.config.json   # last snapshot
```

---

## Transparency & safety (please read)

Healer is a normal, **consent-based, removable** background service — not stealth
software:

- It runs **only because you ran the installer**. Nothing executes on `git clone`.
- It runs under **your own user account**, is **visible** (Task Scheduler /
  `systemctl --user` / `launchctl list`) and appears in your **process list**.
- It **only touches the services you set `enabled:true`** in `healer.config.json`,
  and kills a process only if it owns the watched port *and* matches your
  `proc_match` fingerprint (system/critical processes are denylisted).
- It is **fully removable** with one command (above).

Don't deploy it on machines you don't own or administer. It's an
infrastructure-reliability tool for keeping *your* services alive.

## Requirements
Python 3.7+ and `psutil` (auto-installed). No other dependencies.
