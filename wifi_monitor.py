#!/usr/bin/env python3
"""Compatibility wrapper.

This repository was restructured into a package under `wifi_monitor/`.

Run either:
  python wifi_monitor.py
or:
  python -m wifi_monitor.main
"""

from wifi_monitor.main import main


if __name__ == "__main__":
    main()
