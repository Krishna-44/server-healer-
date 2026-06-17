#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Healer - uninstaller  (Windows / Linux / macOS)
Removes the auto-start entry and stops the running daemon. Leaves your
healer.config.json and logs in place (delete the folder to remove those too).

  python uninstall.py            # remove
  python uninstall.py --dry-run  # show what it would do
"""
import os
import sys
import platform
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
LABEL = "healer-watchdog"
DRY = ("--dry-run" in sys.argv)


def run(cmd):
    print("   $ " + (cmd if isinstance(cmd, str) else " ".join(map(str, cmd))))
    if DRY:
        return
    try:
        subprocess.call(cmd, shell=isinstance(cmd, str))
    except Exception as e:
        print("   ! " + str(e))


def rm(path):
    if os.path.exists(path):
        print("   - " + path)
        if not DRY:
            try:
                os.remove(path)
            except Exception as e:
                print("   ! " + str(e))


def main():
    name = platform.system()
    print("Removing Healer (%s) ..." % name)
    if name == "Windows":
        run(["schtasks", "/End", "/TN", LABEL])
        run(["schtasks", "/Delete", "/TN", LABEL, "/F"])
        # kill the loop driver (vbs host + cmd loop) FIRST so it cannot respawn python
        run('powershell -NoProfile -Command "Get-CimInstance Win32_Process | '
            "Where-Object { $_.CommandLine -like '*run-daemon.cmd*' -or $_.CommandLine -like '*run-daemon-hidden.vbs*' } | "
            'ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"')
        run('powershell -NoProfile -Command "Get-CimInstance Win32_Process | '
            "Where-Object { $_.CommandLine -like '*port_watchdog.py*--daemon*' } | "
            'ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"')
        for f in ("run-daemon.cmd", "run-daemon-hidden.vbs", "_healer_register.ps1"):
            rm(os.path.join(HERE, f))
    elif name == "Linux":
        from shutil import which
        if which("systemctl"):
            run(["systemctl", "--user", "disable", "--now", LABEL + ".service"])
            rm(os.path.expanduser("~/.config/systemd/user/" + LABEL + ".service"))
            run(["systemctl", "--user", "daemon-reload"])
        run("crontab -l 2>/dev/null | grep -v 'run-daemon.sh' | crontab - 2>/dev/null")
        # kill the cron-fallback supervisor loop FIRST so it cannot respawn the daemon
        run("pkill -f run-daemon.sh")
        run("pkill -f 'port_watchdog.py --daemon'")
        rm(os.path.join(HERE, "run-daemon.sh"))
    elif name == "Darwin":
        plist = os.path.expanduser("~/Library/LaunchAgents/com.healer.watchdog.plist")
        run(["launchctl", "unload", "-w", plist])
        rm(plist)
        run("pkill -f 'port_watchdog.py --daemon'")
    else:
        print("  ! Unsupported OS: " + name)
        return
    print("Healer removed. (config + logs kept; delete this folder to remove them.)")


if __name__ == "__main__":
    main()
