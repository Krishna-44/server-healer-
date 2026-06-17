#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Healer - installer  (Windows / Linux / macOS)
=============================================
Sets up Healer as a background, auto-start "crash healer" service on THIS machine.
It keeps the apps you listed (enabled:true) in healer.config.json alive: if one
crashes, stops listening, or fails its health check, Healer restarts it.

This is a transparent, removable service - the same idea as systemd / supervisord
/ PM2 / a Windows Service:
  * It runs ONLY because you ran this installer (nothing auto-runs on git clone).
  * It runs under YOUR user account, is fully visible (Task Scheduler / systemctl
    / launchctl) and shows up in your process list. It is not hidden.
  * It only ever touches the services you set enabled:true in healer.config.json.
  * Remove it any time:   python uninstall.py   (or uninstall.cmd / uninstall.sh)

Usage:
  python install.py            # disclose -> confirm -> install
  python install.py --yes      # skip the confirmation prompt
  python install.py --dry-run  # print exactly what it WOULD do, change nothing
"""
import os
import sys
import platform
import subprocess
import getpass
from shutil import which

HERE = os.path.dirname(os.path.abspath(__file__))
PYEXE = os.path.abspath(sys.executable) if sys.executable else "python3"
ENGINE = os.path.join(HERE, "port_watchdog.py")
CONFIG = os.path.join(HERE, "healer.config.json")
LABEL = "healer-watchdog"
DRY = ("--dry-run" in sys.argv)
YES = ("--yes" in sys.argv) or ("-y" in sys.argv)


def say(*a):
    print(*a)


def run(cmd):
    say("   $ " + (cmd if isinstance(cmd, str) else " ".join(map(str, cmd))))
    if DRY:
        return 0
    try:
        return subprocess.call(cmd, shell=isinstance(cmd, str))
    except Exception as e:
        say("   ! " + str(e))
        return 1


def write_file(path, content, executable=False):
    say("   + " + path)
    if DRY:
        return
    d = os.path.dirname(path)
    if d and not os.path.isdir(d):
        os.makedirs(d, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(content)
    if executable:
        try:
            import stat
            os.chmod(path, os.stat(path).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        except Exception:
            pass


def disclose():
    say("=" * 66)
    say("  HEALER  -  background crash-healer   (installer)")
    say("=" * 66)
    say("  Installs a service that AUTO-STARTS at login and keeps the apps you")
    say("  enabled in healer.config.json alive (restarts them if they crash).")
    say("")
    say("  - Runs as your user account; fully visible; not hidden.")
    say("  - Only acts on services you set enabled:true in healer.config.json.")
    say("  - Remove any time:  python uninstall.py")
    say("  Detected OS: %s %s" % (platform.system(), platform.release()))
    say("=" * 66)


def confirm():
    if YES or DRY:
        return True
    try:
        return input("  Proceed with install? [y/N] ").strip().lower() in ("y", "yes")
    except EOFError:
        return True  # non-interactive (double-click wrapper / piped) -> proceed


def ensure_psutil():
    try:
        import psutil  # noqa: F401
        return
    except ImportError:
        say("  Installing dependency: psutil ...")
        run([PYEXE, "-m", "pip", "install", "--user", "psutil"])


# --------------------------------- Windows --------------------------------- #
def install_windows():
    cmdf = os.path.join(HERE, "run-daemon.cmd")
    vbs = os.path.join(HERE, "run-daemon-hidden.vbs")
    ps1 = os.path.join(HERE, "_healer_register.ps1")
    write_file(cmdf,
               '@echo off\r\n'
               'cd /d "%~dp0"\r\n'
               'if not exist logs md logs\r\n'
               ':loop\r\n'
               '"' + PYEXE + '" port_watchdog.py --daemon --config healer.config.json >> logs\\healer-daemon.log 2>&1\r\n'
               'timeout /t 3 /nobreak >nul\r\n'
               'goto loop\r\n')
    write_file(vbs,
               'Set sh = CreateObject("WScript.Shell")\r\n'
               'sh.Run """' + cmdf + '""", 0, True\r\n')
    write_file(ps1,
               '$ErrorActionPreference = "Stop"\r\n'
               '$a = New-ScheduledTaskAction -Execute "wscript.exe" -Argument \'"' + vbs + '"\'\r\n'
               '$t = New-ScheduledTaskTrigger -AtLogOn\r\n'
               '$s = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit ([TimeSpan]::Zero)\r\n'
               '$p = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited\r\n'
               'Register-ScheduledTask -TaskName "' + LABEL + '" -Action $a -Trigger $t -Settings $s -Principal $p -Force | Out-Null\r\n'
               '# recycle any already-running instance so a re-install picks up new config\r\n'
               'Stop-ScheduledTask -TaskName "' + LABEL + '" -ErrorAction SilentlyContinue\r\n'
               'Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -like "*run-daemon.cmd*" -or $_.CommandLine -like "*run-daemon-hidden.vbs*" -or $_.CommandLine -like "*port_watchdog.py*--daemon*" } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }\r\n'
               'Start-Sleep -Milliseconds 600\r\n'
               'Start-ScheduledTask -TaskName "' + LABEL + '"\r\n'
               'Write-Host "registered + started scheduled task: ' + LABEL + '"\r\n')
    run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", ps1])
    say("  Done. Healer runs at every logon (Task Scheduler -> '%s')." % LABEL)


# ---------------------------------- Linux ---------------------------------- #
def install_linux():
    if which("systemctl"):
        unit = os.path.expanduser("~/.config/systemd/user/" + LABEL + ".service")
        write_file(unit,
                   "[Unit]\n"
                   "Description=Healer crash-healer watchdog\n"
                   "After=network.target\n\n"
                   "[Service]\n"
                   "Type=simple\n"
                   'ExecStart="%s" "%s" --daemon --config "%s"\n' % (PYEXE, ENGINE, CONFIG) +
                   "Restart=always\n"
                   "RestartSec=3\n\n"
                   "[Install]\n"
                   "WantedBy=default.target\n")
        run(["systemctl", "--user", "daemon-reload"])
        run(["systemctl", "--user", "enable", "--now", LABEL + ".service"])
        # let the user service run even when not logged in (best effort, may need sudo)
        linger_user = os.environ.get("USER") or os.environ.get("LOGNAME") or getpass.getuser()
        if linger_user:
            run(["loginctl", "enable-linger", linger_user])
        say("  Done. systemd user service '%s' enabled + started." % LABEL)
    else:
        sh = os.path.join(HERE, "run-daemon.sh")
        write_file(sh,
                   '#!/bin/sh\ncd "$(dirname "$0")"\nmkdir -p logs\n'
                   'while true; do "%s" port_watchdog.py --daemon --config healer.config.json >> logs/healer-daemon.log 2>&1; sleep 3; done\n' % PYEXE,
                   executable=True)
        say("   (systemd not found - using cron @reboot fallback)")
        if not DRY:
            try:
                cur = subprocess.run(["crontab", "-l"], capture_output=True, text=True).stdout
            except Exception:
                cur = ""
            if sh not in cur:
                p = subprocess.Popen(["crontab", "-"], stdin=subprocess.PIPE, text=True)
                p.communicate(cur + ('@reboot "%s" >/dev/null 2>&1\n' % sh))
        run(["sh", "-c", 'nohup "%s" >/dev/null 2>&1 &' % sh])
        say("  Done (cron @reboot + started now).")


# ---------------------------------- macOS ---------------------------------- #
def install_macos():
    plist = os.path.expanduser("~/Library/LaunchAgents/com.healer.watchdog.plist")
    logs = os.path.join(HERE, "logs")
    if not DRY:
        os.makedirs(logs, exist_ok=True)
    write_file(plist,
               '<?xml version="1.0" encoding="UTF-8"?>\n'
               '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">\n'
               '<plist version="1.0"><dict>\n'
               '  <key>Label</key><string>com.healer.watchdog</string>\n'
               '  <key>ProgramArguments</key>\n  <array>\n'
               '    <string>%s</string>\n    <string>%s</string>\n    <string>--daemon</string>\n    <string>--config</string>\n    <string>%s</string>\n  </array>\n' % (PYEXE, ENGINE, CONFIG) +
               '  <key>RunAtLoad</key><true/>\n  <key>KeepAlive</key><true/>\n'
               '  <key>StandardOutPath</key><string>%s/healer.out.log</string>\n' % logs +
               '  <key>StandardErrorPath</key><string>%s/healer.err.log</string>\n' % logs +
               '</dict></plist>\n')
    uid = str(os.getuid())
    run(["launchctl", "bootout", "gui/" + uid, plist])          # remove if already loaded (ignore err)
    rc = run(["launchctl", "bootstrap", "gui/" + uid, plist])   # modern load (macOS 10.10+)
    if rc != 0:
        run(["launchctl", "unload", plist])
        run(["launchctl", "load", "-w", plist])                 # legacy fallback
    run(["launchctl", "enable", "gui/" + uid + "/com.healer.watchdog"])
    say("  Done. LaunchAgent 'com.healer.watchdog' loaded (starts at login).")


def main():
    disclose()
    if not os.path.exists(ENGINE):
        say("  ! port_watchdog.py not found next to install.py - aborting.")
        sys.exit(1)
    if not confirm():
        say("  Cancelled - nothing changed.")
        return
    ensure_psutil()
    name = platform.system()
    say("  Installing for %s ..." % name)
    if name == "Windows":
        install_windows()
    elif name == "Linux":
        install_linux()
    elif name == "Darwin":
        install_macos()
    else:
        say("  ! Unsupported OS: " + name)
        sys.exit(2)
    if DRY:
        say("\n  (dry-run complete - nothing was changed)")
    else:
        say("\n  Healer is active. Edit healer.config.json to add your apps, then it")
        say("  will keep them alive 24x7. Remove with: python uninstall.py")


if __name__ == "__main__":
    main()
