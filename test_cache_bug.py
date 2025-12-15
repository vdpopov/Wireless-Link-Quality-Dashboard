#!/usr/bin/env python
"""Test to reproduce the sliding window cache bug."""

import numpy as np
import sys

# Simulate the OLD buggy logic vs NEW fixed logic

def test_old_logic():
    """Reproduces the bug with index-based tail calculation."""
    print("=== OLD LOGIC (buggy) ===\n")

    # Time 0: Create cache
    time_data = np.arange(0, 600, 1.0)  # 600 seconds of data
    window = 500  # Show last 500 seconds
    tail_points = 60

    start_idx = len(time_data) - window  # 100
    vis_time = time_data[start_idx:]  # [100..599]
    hist_time_raw = vis_time[:-tail_points]  # [100..539]

    # Simulate downsampling (just take every 10th point for simplicity)
    step = 10
    cached_hist_time = hist_time_raw[::step]  # [100, 110, 120, ..., 530]
    cached_hist_len = len(hist_time_raw)  # 440

    print(f"Time 0:")
    print(f"  vis_time range: [{vis_time[0]:.0f} .. {vis_time[-1]:.0f}]")
    print(f"  cached_hist_time range: [{cached_hist_time[0]:.0f} .. {cached_hist_time[-1]:.0f}]")
    print(f"  cached_hist_len: {cached_hist_len}")

    # Time 60: Window slides, 60 new points added
    time_data = np.arange(0, 660, 1.0)  # 660 seconds now
    start_idx = len(time_data) - window  # 160
    vis_time = time_data[start_idx:]  # [160..659]

    # OLD BUGGY CODE: use cached_hist_len as index into NEW vis_time
    tail_time = vis_time[cached_hist_len:]  # vis_time[440:] = [600..659]

    print(f"\nTime 60 (window slid):")
    print(f"  vis_time range: [{vis_time[0]:.0f} .. {vis_time[-1]:.0f}]")
    print(f"  cached_hist_time ends at: {cached_hist_time[-1]:.0f}")
    print(f"  tail_time starts at: {tail_time[0]:.0f}")
    print(f"\n  *** GAP: {cached_hist_time[-1]:.0f} -> {tail_time[0]:.0f} = {tail_time[0] - cached_hist_time[-1]:.0f} seconds! ***")
    print(f"  This is the FLAT LINE!\n")


def test_new_logic():
    """Shows the fix with timestamp-based tail calculation."""
    print("=== NEW LOGIC (fixed) ===\n")

    # Time 0: Create cache
    time_data = np.arange(0, 600, 1.0)
    window = 500
    tail_points = 60

    start_idx = len(time_data) - window
    vis_time = time_data[start_idx:]
    hist_time_raw = vis_time[:-tail_points]

    step = 10
    cached_hist_time = hist_time_raw[::step]
    cached_end_time = float(hist_time_raw[-1])  # 539.0 - TIMESTAMP not index!

    print(f"Time 0:")
    print(f"  vis_time range: [{vis_time[0]:.0f} .. {vis_time[-1]:.0f}]")
    print(f"  cached_hist_time range: [{cached_hist_time[0]:.0f} .. {cached_hist_time[-1]:.0f}]")
    print(f"  cached_end_time: {cached_end_time:.0f}")

    # Time 60: Window slides
    time_data = np.arange(0, 660, 1.0)
    start_idx = len(time_data) - window
    vis_time = time_data[start_idx:]

    # NEW FIXED CODE: find tail start by TIMESTAMP
    tail_start_idx = np.searchsorted(vis_time, cached_end_time, side="right")
    tail_time = vis_time[tail_start_idx:]

    # Also trim cached history to current visible range
    vis_start = vis_time[0]
    trim_idx = np.searchsorted(cached_hist_time, vis_start, side="left")
    trimmed_hist_time = cached_hist_time[trim_idx:]

    print(f"\nTime 60 (window slid):")
    print(f"  vis_time range: [{vis_time[0]:.0f} .. {vis_time[-1]:.0f}]")
    print(f"  trimmed_hist_time range: [{trimmed_hist_time[0]:.0f} .. {trimmed_hist_time[-1]:.0f}]")
    print(f"  tail_start_idx: {tail_start_idx} (found by searching for timestamp {cached_end_time:.0f})")
    print(f"  tail_time starts at: {tail_time[0]:.0f}")
    print(f"\n  Gap: {trimmed_hist_time[-1]:.0f} -> {tail_time[0]:.0f} = {tail_time[0] - trimmed_hist_time[-1]:.0f} seconds")
    print(f"  NO FLAT LINE! (gap is just the normal sample interval)\n")


if __name__ == "__main__":
    test_old_logic()
    test_new_logic()
