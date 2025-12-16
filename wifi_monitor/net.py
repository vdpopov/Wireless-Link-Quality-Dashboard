import subprocess
import re

from . import constants


def get_default_gateway():
    try:
        result = subprocess.check_output(["ip", "route"], text=True)
        for line in result.split("\n"):
            if line.startswith("default"):
                parts = line.split()
                if "via" in parts:
                    return parts[parts.index("via") + 1]
    except Exception:
        pass
    return None


def get_wireless_interfaces():
    interfaces = []
    try:
        result = subprocess.check_output(["iw", "dev"], text=True)
        for line in result.split("\n"):
            if "Interface" in line:
                interfaces.append(line.split()[-1])
    except Exception:
        pass
    return interfaces


def get_link_info():
    try:
        result = subprocess.check_output(
            ["iw", "dev", constants.INTERFACE, "link"], text=True
        )
        signal_match = re.search(r"signal: (-\d+)", result)
        rx_match = re.search(r"rx bitrate: ([\d.]+) MBit/s.*?(\d+)MHz", result)
        tx_match = re.search(r"tx bitrate: ([\d.]+) MBit/s.*?(\d+)MHz", result)

        signal = int(signal_match.group(1)) if signal_match else None
        rx_rate = float(rx_match.group(1)) if rx_match else None
        rx_bw = int(rx_match.group(2)) if rx_match else None
        tx_rate = float(tx_match.group(1)) if tx_match else None
        tx_bw = int(tx_match.group(2)) if tx_match else None

        return signal, rx_rate, tx_rate, rx_bw or tx_bw
    except Exception:
        return None, None, None, None


def get_current_frequency():
    """Get current connection frequency in MHz. Returns None if not connected."""
    try:
        result = subprocess.check_output(
            ["iw", "dev", constants.INTERFACE, "link"], text=True
        )
        freq_match = re.search(r"freq: ([\d.]+)", result)
        if freq_match:
            return float(freq_match.group(1))
    except Exception:
        pass
    return None


def get_current_band():
    """
    Detect if connected to 2.4GHz or 5GHz.
    Returns '2.4' or '5' or None if not connected.
    """
    freq = get_current_frequency()
    if freq is None:
        return None
    if freq < 3000:  # 2.4GHz is 2412-2484 MHz
        return "2.4"
    else:  # 5GHz is 5180-5825 MHz
        return "5"
