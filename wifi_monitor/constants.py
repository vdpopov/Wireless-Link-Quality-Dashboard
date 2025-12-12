import numpy as np

# Time window presets (label -> seconds)
TIME_WINDOWS = {
    "10m": 600,
    "30m": 1800,
    "60m": 3600,
    "4h": 14400,
    "1D": 86400,
    "∞": None,
}

PING_COLORS = ["#FF0000", "#FFA500", "#800080", "#8B4513", "#FF1493", "#00FFFF"]

# Defaults
DEFAULT_WINDOW = 600
DEFAULT_REFRESH_INTERVAL_MS = 1000

# Shared state (mutated by app)
current_window = DEFAULT_WINDOW
paused = False

signal_data = np.array([])
rx_rate_data = np.array([])
tx_rate_data = np.array([])
bandwidth_data = np.array([])
time_data = np.array([])

signal_failed = np.array([], dtype=bool)
rates_failed = np.array([], dtype=bool)
bandwidth_failed = np.array([], dtype=bool)

INTERFACE = None
REFRESH_INTERVAL = DEFAULT_REFRESH_INTERVAL_MS

ping_hosts = []
