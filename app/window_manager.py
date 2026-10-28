"""
Window manager for Subway Surfers AI Body Controller.
Detects active foreground window on Windows to prevent keystrokes
from being dispatched to unintended applications.
"""
import sys
import webbrowser
from typing import List

try:
    import win32gui
    import win32process
    HAS_WIN32 = True
except ImportError:
    HAS_WIN32 = False

class WindowManager:
    """
    Inspects Windows active foreground window title against configured patterns.
    """
    def __init__(self, patterns: List[str] = None, require_focus: bool = True):
        self.patterns = [p.lower() for p in (patterns or [
            "subway surfers",
            "poki",
            "google chrome",
            "microsoft edge",
            "mozilla firefox",
            "brave",
            "opera",
        ])]
        self.require_focus = require_focus

    def set_require_focus(self, require: bool):
        self.require_focus = require

    def set_patterns(self, patterns: List[str]):
        self.patterns = [p.lower() for p in patterns]

    def get_foreground_window_title(self) -> str:
        """Get the title of the current foreground window on Windows."""
        if not HAS_WIN32 or sys.platform != "win32":
            return "Non-Windows / Fallback"
        try:
            hwnd = win32gui.GetForegroundWindow()
            if hwnd == 0:
                return ""
            return win32gui.GetWindowText(hwnd) or ""
        except Exception:
            return ""

    def is_game_focused(self) -> bool:
        """
        Check if the current active window appears to be the game or browser.
        If require_focus is disabled, always returns True.
        """
        if not self.require_focus:
            return True
            
        title = self.get_foreground_window_title().lower()
        if not title:
            return False
            
        return any(pattern in title for pattern in self.patterns)

    @staticmethod
    def open_game_url(url: str = "https://poki.com/en/g/subway-surfers"):
        """Open the official Subway Surfers Poki game in the default browser."""
        try:
            webbrowser.open(url, new=2)
        except Exception as e:
            print(f"[WindowManager] Failed to open game URL: {e}")
