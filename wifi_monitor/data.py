import time
from datetime import datetime

import numpy as np

from . import constants


def smooth_data(data, alpha=0.3):
    if len(data) == 0:
        return data

    data = np.asarray(data, dtype=float)
    smoothed = np.empty_like(data)

    valid_mask = ~np.isnan(data)
    if not np.any(valid_mask):
        return data

    first_valid_idx = np.argmax(valid_mask)
    ema = data[first_valid_idx]

    for i in range(len(data)):
        if np.isnan(data[i]):
            smoothed[i] = np.nan
        else:
            if i == first_valid_idx:
                ema = data[i]
            else:
                ema = alpha * data[i] + (1 - alpha) * ema
            smoothed[i] = ema

    return smoothed


def generate_test_data(duration="1h"):
    duration = duration.lower().strip()
    if duration.endswith("m"):
        total_seconds = int(duration[:-1]) * 60
    elif duration.endswith("h"):
        total_seconds = int(duration[:-1]) * 3600
    elif duration.endswith("d"):
        total_seconds = int(duration[:-1]) * 86400
    elif duration.endswith("w"):
        total_seconds = int(duration[:-1]) * 604800
    else:
        total_seconds = int(duration)

    num_points = total_seconds

    current_time = time.time()
    start_time = current_time - total_seconds

    print(f"Generating {num_points:,} test data points ({duration})...")

    constants.time_data = np.linspace(start_time, current_time, num_points)

    base_signal = np.random.randint(-65, -45, num_points).astype(float)
    drift = 10 * np.sin(np.linspace(0, 8 * np.pi, num_points))
    constants.signal_data = np.clip(base_signal + drift, -80, -30)
    constants.signal_failed = np.zeros(num_points, dtype=bool)

    num_failures = np.random.randint(5, 15)
    for _ in range(num_failures):
        fail_start = np.random.randint(0, num_points - 100)
        fail_len = np.random.randint(10, 60)
        constants.signal_failed[fail_start : fail_start + fail_len] = True
        constants.signal_data[fail_start : fail_start + fail_len] = np.nan

    for offset in [100, 250, 400]:
        fail_start = num_points - offset
        fail_len = 30
        constants.signal_failed[fail_start : fail_start + fail_len] = True
        constants.signal_data[fail_start : fail_start + fail_len] = np.nan

    rx_base = np.random.uniform(80, 150, num_points)
    tx_base = np.random.uniform(50, 120, num_points)
    constants.rx_rate_data = np.convolve(rx_base, np.ones(10) / 10, mode="same")
    constants.tx_rate_data = np.convolve(tx_base, np.ones(10) / 10, mode="same")
    constants.rates_failed = np.zeros(num_points, dtype=bool)

    num_failures = np.random.randint(3, 10)
    for _ in range(num_failures):
        fail_start = np.random.randint(0, num_points - 100)
        fail_len = np.random.randint(5, 30)
        constants.rates_failed[fail_start : fail_start + fail_len] = True
        constants.rx_rate_data[fail_start : fail_start + fail_len] = np.nan
        constants.tx_rate_data[fail_start : fail_start + fail_len] = np.nan

    for offset in [150, 350]:
        fail_start = num_points - offset
        fail_len = 20
        constants.rates_failed[fail_start : fail_start + fail_len] = True
        constants.rx_rate_data[fail_start : fail_start + fail_len] = np.nan
        constants.tx_rate_data[fail_start : fail_start + fail_len] = np.nan

    bw_choices = [20, 40, 80, 160]
    constants.bandwidth_data = np.zeros(num_points)
    current_bw = np.random.choice(bw_choices)
    for i in range(num_points):
        if np.random.random() < 0.001:
            current_bw = np.random.choice(bw_choices)
        constants.bandwidth_data[i] = current_bw
    constants.bandwidth_failed = np.zeros(num_points, dtype=bool)

    num_failures = np.random.randint(3, 8)
    for _ in range(num_failures):
        fail_start = np.random.randint(0, num_points - 100)
        fail_len = np.random.randint(5, 40)
        constants.bandwidth_failed[fail_start : fail_start + fail_len] = True
        constants.bandwidth_data[fail_start : fail_start + fail_len] = np.nan

    for offset in [200, 450]:
        fail_start = num_points - offset
        fail_len = 25
        constants.bandwidth_failed[fail_start : fail_start + fail_len] = True
        constants.bandwidth_data[fail_start : fail_start + fail_len] = np.nan

    for host_info in constants.ping_hosts:
        base_ping = np.random.uniform(10, 40, num_points)
        spikes = np.random.random(num_points) < 0.02
        base_ping[spikes] *= np.random.uniform(2, 5, np.sum(spikes))
        host_info["data"] = np.convolve(base_ping, np.ones(5) / 5, mode="same")
        host_info["failed"] = np.zeros(num_points, dtype=bool)

        num_failures = np.random.randint(5, 15)
        for _ in range(num_failures):
            fail_start = np.random.randint(0, num_points - 100)
            fail_len = np.random.randint(5, 30)
            host_info["failed"][fail_start : fail_start + fail_len] = True
            host_info["data"][fail_start : fail_start + fail_len] = np.nan

        for offset in [120, 300, 500]:
            fail_start = num_points - offset
            fail_len = 15
            host_info["failed"][fail_start : fail_start + fail_len] = True
            host_info["data"][fail_start : fail_start + fail_len] = np.nan

    print(
        f"Done! Generated {len(constants.time_data):,} points from {datetime.fromtimestamp(start_time)} to {datetime.fromtimestamp(current_time)}"
    )
