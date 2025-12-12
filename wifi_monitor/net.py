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
