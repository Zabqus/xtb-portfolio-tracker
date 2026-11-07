"""
Lokalne powiadomienia Windows (balloon / toast) — bez chmury i bez maila.
"""

from __future__ import annotations

import subprocess
import sys


def show_windows_toast(title: str, message: str, *, timeout_ms: int = 6000) -> bool:
    """
    Pokazuje balon powiadomień Windows (NotifyIcon).

    Zwraca True gdy udało się odpalić PowerShell. Na nie-Windows zwraca False.
    """
    if sys.platform != "win32":
        return False

    safe_title = _ps_escape(title[:80])
    safe_msg = _ps_escape(message[:220])
    ms = max(1000, int(timeout_ms))

    script = f"""
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
$n = New-Object System.Windows.Forms.NotifyIcon
$n.Icon = [System.Drawing.SystemIcons]::Information
$n.Visible = $true
$n.BalloonTipTitle = '{safe_title}'
$n.BalloonTipText = '{safe_msg}'
$n.ShowBalloonTip({ms})
Start-Sleep -Milliseconds {ms + 400}
$n.Dispose()
"""
    try:
        subprocess.Popen(
            [
                "powershell",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                script,
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        return True
    except OSError:
        return False


def _ps_escape(text: str) -> str:
    return (
        str(text)
        .replace("'", "''")
        .replace("\r", " ")
        .replace("\n", " ")
        .replace("`", "``")
    )
