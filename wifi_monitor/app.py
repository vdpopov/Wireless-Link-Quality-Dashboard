"""Compatibility import.

The main window now lives in `wifi_monitor/windows/main_window.py`.
"""

from .windows.main_window import WifiMonitor

__all__ = ["WifiMonitor"]
