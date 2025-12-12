import re
import threading
import time
import subprocess

import numpy as np

from . import constants


ping_lock = threading.Lock()
ping_threads_running = True


gateway_host_info = None
gateway_removed_by_user = False


def ping_worker(host_info):
    while ping_threads_running:
        if not host_info["enabled"]:
            time.sleep(0.5)
            continue
        try:
            result = subprocess.check_output(
                ["ping", "-c", "1", "-W", "1", host_info["host"]],
                text=True,
                stderr=subprocess.DEVNULL,
            )
            match = re.search(r"time=([\d.]+)", result)
            with ping_lock:
                host_info["latest"] = float(match.group(1)) if match else None
        except Exception:
            with ping_lock:
                host_info["latest"] = None
        time.sleep(0.3)


def add_ping_host(host, label=None):
    current_len = len(constants.time_data)
    host_info = {
        "host": host,
        "label": label or host,
        "enabled": True,
        "data": np.full(current_len, np.nan),
        "failed": np.ones(current_len, dtype=bool),
        "latest": None,
        "thread": None,
    }
    thread = threading.Thread(target=ping_worker, args=(host_info,), daemon=True)
    host_info["thread"] = thread
    thread.start()
    constants.ping_hosts.append(host_info)
    return host_info


def remove_ping_host(index):
    if 0 <= index < len(constants.ping_hosts):
        constants.ping_hosts[index]["enabled"] = False
        constants.ping_hosts.pop(index)
