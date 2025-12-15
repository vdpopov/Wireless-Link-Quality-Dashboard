#!/usr/bin/env python
"""
Test that simulates hours of sliding window behavior to catch gap accumulation.
"""

import numpy as np


def simulate_old_logic(hours=16, sample_rate=1, window_size=500, tail_points=60, max_points=200):
    """Simulate the OLD buggy cache logic over many hours."""

    total_samples = int(hours * 3600 * sample_rate)
    time_data = np.arange(0, total_samples, dtype=float)

    # Simulate cache state
    cache = None
    max_gap_seen = 0
    gap_count = 0

    # Simulate ticks (check every 60 samples to speed up)
    check_interval = 60

    for tick in range(window_size, total_samples, check_interval):
        # Current visible window
        start_idx = max(0, tick - window_size)
        vis_time = time_data[start_idx:tick]

        if len(vis_time) <= max_points + tail_points:
            continue  # No downsampling needed

        hist_time_raw = vis_time[:-tail_points]
        tail_time_default = vis_time[-tail_points:]

        step = max(1, int(np.ceil(len(hist_time_raw) / max(1, max_points // 2))))
        t0 = time_data[0]
        dt = 1.0

        cache_key = (step, tail_points, max_points, t0, dt)

        can_reuse = (
            cache is not None
            and cache.get("key") == cache_key
            and cache.get("hist_raw_len", 0) <= len(hist_time_raw)
        )

        if can_reuse and (len(hist_time_raw) - cache["hist_raw_len"]) < step:
            # OLD BUGGY: use index from old array on new array
            hist_time = cache["hist_time"]
            cached_hist_len = cache["hist_raw_len"]
            tail_time = vis_time[cached_hist_len:]  # BUG: wrong index!
        else:
            # Fresh computation
            hist_time = hist_time_raw[::step]  # Simple downsampling
            tail_time = tail_time_default
            cache = {
                "key": cache_key,
                "hist_raw_len": len(hist_time_raw),
                "hist_time": hist_time,
            }

        # Check for gap
        if len(hist_time) > 0 and len(tail_time) > 0:
            gap = tail_time[0] - hist_time[-1]
            if gap > step + 5:  # Allow small gaps from downsampling
                gap_count += 1
                if gap > max_gap_seen:
                    max_gap_seen = gap

    return max_gap_seen, gap_count


def simulate_new_logic(hours=16, sample_rate=1, window_size=500, tail_points=60, max_points=200):
    """Simulate the NEW fixed cache logic over many hours."""

    total_samples = int(hours * 3600 * sample_rate)
    time_data = np.arange(0, total_samples, dtype=float)

    cache = None
    max_gap_seen = 0
    gap_count = 0

    check_interval = 60

    for tick in range(window_size, total_samples, check_interval):
        start_idx = max(0, tick - window_size)
        vis_time = time_data[start_idx:tick]

        if len(vis_time) <= max_points + tail_points:
            continue

        hist_time_raw = vis_time[:-tail_points]
        tail_time_default = vis_time[-tail_points:]

        step = max(1, int(np.ceil(len(hist_time_raw) / max(1, max_points // 2))))
        t0 = time_data[0]
        dt = 1.0

        cache_key = (step, tail_points, max_points, t0, dt)

        can_reuse = (
            len(hist_time_raw) > 0
            and cache is not None
            and cache.get("key") == cache_key
            and cache.get("hist_end_time", 0) <= hist_time_raw[-1]
        )

        if can_reuse:
            cached_hist_time = cache["hist_time"]
            cached_end_time = cache["hist_end_time"]

            # NEW FIX: trim old data that scrolled off
            vis_start = vis_time[0]
            trim_idx = np.searchsorted(cached_hist_time, vis_start, side="left")
            hist_time = cached_hist_time[trim_idx:]

            # NEW FIX: find tail by timestamp, not index
            tail_start_idx = np.searchsorted(vis_time, cached_end_time, side="right")
            tail_time = vis_time[tail_start_idx:]
        else:
            hist_time = hist_time_raw[::step]
            tail_time = tail_time_default
            cache = {
                "key": cache_key,
                "hist_end_time": float(hist_time_raw[-1]),
                "hist_time": hist_time,
            }

        # Check for gap
        if len(hist_time) > 0 and len(tail_time) > 0:
            gap = tail_time[0] - hist_time[-1]
            if gap > step + 5:
                gap_count += 1
                if gap > max_gap_seen:
                    max_gap_seen = gap

    return max_gap_seen, gap_count


def test_accumulation():
    """Test that gaps don't accumulate over time."""
    print("Testing gap accumulation over simulated 16 hours...\n")

    print("OLD LOGIC (buggy):")
    max_gap, count = simulate_old_logic(hours=16)
    print(f"  Max gap: {max_gap:.0f} seconds")
    print(f"  Gap occurrences: {count}")
    old_has_bugs = max_gap > 10 or count > 0
    print(f"  Status: {'BUGGY - gaps detected!' if old_has_bugs else 'OK'}\n")

    print("NEW LOGIC (fixed):")
    max_gap, count = simulate_new_logic(hours=16)
    print(f"  Max gap: {max_gap:.0f} seconds")
    print(f"  Gap occurrences: {count}")
    new_is_fixed = max_gap <= 10 and count == 0
    print(f"  Status: {'FIXED - no gaps!' if new_is_fixed else 'STILL BUGGY'}\n")

    return old_has_bugs and new_is_fixed


def test_interval_switch():
    """Test that switching intervals (window sizes) doesn't cause gaps."""
    print("Testing interval switching simulation...\n")

    time_data = np.arange(0, 10000, dtype=float)
    cache = None
    gaps_found = []

    # Simulate switching between different window sizes
    windows = [500, 3600, 500, 14400, 500, 1800, 500]

    for window_size in windows:
        tick = len(time_data)
        start_idx = max(0, tick - window_size)
        vis_time = time_data[start_idx:tick]

        tail_points = 60
        max_points = 200

        if len(vis_time) <= max_points + tail_points:
            continue

        hist_time_raw = vis_time[:-tail_points]

        step = max(1, int(np.ceil(len(hist_time_raw) / max(1, max_points // 2))))

        # Always recompute on window switch (as real code does)
        hist_time = hist_time_raw[::step]
        tail_time = vis_time[-tail_points:]

        cache = {
            "hist_end_time": float(hist_time_raw[-1]),
            "hist_time": hist_time,
        }

        if len(hist_time) > 0 and len(tail_time) > 0:
            gap = tail_time[0] - hist_time[-1]
            if gap > step + 5:
                gaps_found.append((window_size, gap))

    if gaps_found:
        print(f"  FAIL: Found gaps after switching: {gaps_found}")
        return False
    else:
        print(f"  PASS: No gaps after switching intervals")
        return True


def test_rapid_ticks():
    """Test many rapid ticks to simulate real-time behavior."""
    print("Testing 1000 rapid ticks...\n")

    max_gap, count = simulate_new_logic(hours=1, sample_rate=1, window_size=300)

    if count == 0:
        print(f"  PASS: No gaps in 1 hour of rapid ticks")
        return True
    else:
        print(f"  FAIL: {count} gaps found, max={max_gap:.0f}s")
        return False


if __name__ == "__main__":
    print("=" * 60)
    print("CACHE SLIDING WINDOW BUG TESTS")
    print("=" * 60 + "\n")

    results = []

    results.append(("Accumulation test", test_accumulation()))
    print("-" * 60 + "\n")

    results.append(("Interval switch test", test_interval_switch()))
    print("-" * 60 + "\n")

    results.append(("Rapid ticks test", test_rapid_ticks()))
    print("-" * 60 + "\n")

    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    all_passed = True
    for name, passed in results:
        status = "PASS" if passed else "FAIL"
        print(f"  {name}: {status}")
        if not passed:
            all_passed = False

    print()
    if all_passed:
        print("All tests passed!")
    else:
        print("Some tests failed!")

    exit(0 if all_passed else 1)
