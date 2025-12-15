import time

import numpy as np
import pyqtgraph as pg

from .. import constants
from ..data import smooth_data


def _downsample_minmax(time_arr: np.ndarray, y_arr: np.ndarray, step: int):
    """Downsample by emitting min+max per bucket (peak-preserving).

    NOTE: This function buckets by index (0..n). For sliding windows, bucket
    boundaries can move as the window cutoff shifts.
    """
    n = len(time_arr)
    if step <= 1 or n <= 2:
        return time_arr, y_arr

    out_t = []
    out_y = []

    end = (n // step) * step
    for i in range(0, end, step):
        t_chunk = time_arr[i : i + step]
        y_chunk = y_arr[i : i + step]

        if np.all(~np.isfinite(y_chunk)):
            mid = len(t_chunk) // 2
            out_t.append(t_chunk[mid])
            out_y.append(np.nan)
            continue

        imin = int(np.nanargmin(y_chunk))
        imax = int(np.nanargmax(y_chunk))

        if imin <= imax:
            out_t.extend([t_chunk[imin], t_chunk[imax]])
            out_y.extend([y_chunk[imin], y_chunk[imax]])
        else:
            out_t.extend([t_chunk[imax], t_chunk[imin]])
            out_y.extend([y_chunk[imax], y_chunk[imin]])

    if end < n:
        out_t.extend(time_arr[end:])
        out_y.extend(y_arr[end:])

    return np.asarray(out_t), np.asarray(out_y)


def _downsample_minmax_timebucket(time_arr: np.ndarray, y_arr: np.ndarray, step: int, t0: float, dt: float):
    """Stable min/max downsampling using absolute-time buckets.

    Buckets are aligned to (t0 + k*step*dt), so a sliding cutoff does not move
    bucket boundaries and deep history stays visually stable.
    """
    n = len(time_arr)
    if step <= 1 or n <= 2:
        return time_arr, y_arr

    dt = max(float(dt), 1e-6)
    bucket = step * dt

    # Bucket index per sample.
    idx = np.floor((time_arr - t0) / bucket).astype(np.int64)

    out_t = []
    out_y = []

    i = 0
    while i < n:
        j = i + 1
        while j < n and idx[j] == idx[i]:
            j += 1

        t_chunk = time_arr[i:j]
        y_chunk = y_arr[i:j]

        if np.all(~np.isfinite(y_chunk)):
            mid = len(t_chunk) // 2
            out_t.append(t_chunk[mid])
            out_y.append(np.nan)
        else:
            imin = int(np.nanargmin(y_chunk))
            imax = int(np.nanargmax(y_chunk))
            if imin <= imax:
                out_t.extend([t_chunk[imin], t_chunk[imax]])
                out_y.extend([y_chunk[imin], y_chunk[imax]])
            else:
                out_t.extend([t_chunk[imax], t_chunk[imin]])
                out_y.extend([y_chunk[imax], y_chunk[imin]])

        i = j

    return np.asarray(out_t), np.asarray(out_y)


def _downsample_multi_timebucket(time_arr: np.ndarray, y_arrays: list, step: int, t0: float, dt: float):
    """Downsample multiple Y series using a shared time grid.

    Returns (out_time, [out_y1, out_y2, ...]) where all arrays have the same length.
    For each bucket, emits two points (at min/max times based on the FIRST y array).
    Other y arrays are sampled at the same indices.
    """
    n = len(time_arr)
    if step <= 1 or n <= 2:
        return time_arr, y_arrays

    dt = max(float(dt), 1e-6)
    bucket = step * dt

    idx = np.floor((time_arr - t0) / bucket).astype(np.int64)

    out_t = []
    out_ys = [[] for _ in y_arrays]

    i = 0
    while i < n:
        j = i + 1
        while j < n and idx[j] == idx[i]:
            j += 1

        t_chunk = time_arr[i:j]
        # Use the first Y array (signal) to determine which indices to sample
        y_primary = y_arrays[0][i:j]

        if np.all(~np.isfinite(y_primary)):
            # All NaN in primary - emit single midpoint for all series
            mid = len(t_chunk) // 2
            out_t.append(t_chunk[mid])
            for k, y_arr in enumerate(y_arrays):
                out_ys[k].append(y_arr[i:j][mid])
        else:
            imin = int(np.nanargmin(y_primary))
            imax = int(np.nanargmax(y_primary))
            if imin <= imax:
                out_t.extend([t_chunk[imin], t_chunk[imax]])
                for k, y_arr in enumerate(y_arrays):
                    y_chunk = y_arr[i:j]
                    out_ys[k].extend([y_chunk[imin], y_chunk[imax]])
            else:
                out_t.extend([t_chunk[imax], t_chunk[imin]])
                for k, y_arr in enumerate(y_arrays):
                    y_chunk = y_arr[i:j]
                    out_ys[k].extend([y_chunk[imax], y_chunk[imin]])

        i = j

    return np.asarray(out_t), [np.asarray(y) for y in out_ys]


def draw_failure_regions(window, plot_idx, failure_list, start_idx, x_range=None):
    plots = [window.signal_plot, window.ping_plot, window.rate_plot, window.bw_plot]
    plot = plots[plot_idx]
    overlay = window.failure_overlays[plot_idx]

    overlay.setGeometry(plot.viewport().rect())

    if len(constants.time_data) == 0 or len(failure_list) == 0:
        overlay.setRegions([])
        return

    vb = plot.getViewBox()
    view_range = vb.viewRange()
    x_min, x_max = view_range[0]

    if x_max <= x_min:
        overlay.setRegions([])
        return

    vis_start = max(0, np.searchsorted(constants.time_data, x_min, side="left") - 1)
    vis_end = min(
        len(failure_list),
        np.searchsorted(constants.time_data, x_max, side="right") + 1,
    )

    if vis_end <= vis_start:
        overlay.setRegions([])
        return

    vis_failures = failure_list[vis_start:vis_end]

    if not np.any(vis_failures):
        overlay.setRegions([])
        return

    padded = np.concatenate([[False], vis_failures.astype(bool), [False]])
    diff = np.diff(padded.astype(np.int8))
    starts = np.where(diff == 1)[0]
    ends = np.where(diff == -1)[0]

    pixel_regions = []
    for s, e in zip(starts, ends):
        global_start = vis_start + s
        global_end = vis_start + e - 1

        if global_start >= len(constants.time_data) or global_end >= len(constants.time_data):
            continue

        t_start = constants.time_data[global_start]
        t_end = constants.time_data[global_end]

        if global_start > 0:
            t_start = constants.time_data[global_start - 1]
        if global_end + 1 < len(constants.time_data):
            t_end = constants.time_data[global_end + 1]

        t_start = max(t_start, x_min)
        t_end = min(t_end, x_max)

        left_scene = vb.mapViewToScene(pg.Point(t_start, 0))
        right_scene = vb.mapViewToScene(pg.Point(t_end, 0))
        left_pixel = plot.mapFromScene(left_scene).x()
        right_pixel = plot.mapFromScene(right_scene).x()

        if right_pixel > left_pixel:
            pixel_regions.append((left_pixel, right_pixel))

    overlay.setRegions(pixel_regions)


def update_ping_curves(window):
    from ..constants import PING_COLORS
    from ..plot_items import setup_legend

    # Remove only the ping curves + their legend entries; do not clear the whole plot,
    # otherwise the ping graph visibly blinks on host add/remove.

    old_legend = getattr(window, "ping_legend", None)
    if old_legend is not None:
        try:
            old_legend.setParentItem(None)
            old_legend.scene().removeItem(old_legend)
        except Exception:
            pass

    for curve in getattr(window, "ping_curves", []):
        try:
            window.ping_plot.removeItem(curve)
        except Exception:
            pass
    window.ping_curves.clear()

    window.ping_legend = setup_legend(window.ping_plot)

    for i, host_info in enumerate(constants.ping_hosts):
        color = PING_COLORS[i % len(PING_COLORS)]
        curve = window.ping_plot.plot(
            pen=pg.mkPen(color, width=2),
            antialias=window.antialias_default,
            connect="finite",
        )
        window.ping_curves.append(curve)
        window.ping_legend.addItem(curve, host_info["label"])

    # The selection lines + overlays are created once in main_window.py and should be
    # left intact here.


def full_redraw(window):
    if len(constants.time_data) == 0:
        return

    # Use the same notion of "now" throughout this redraw.
    now = time.time()

    if constants.current_window is None:
        start_idx = 0
    else:
        cutoff = now - constants.current_window
        start_idx = np.searchsorted(constants.time_data, cutoff, side="left")

    vis_time = constants.time_data[start_idx:]
    vis_signal = constants.signal_data[start_idx:]
    vis_rx = constants.rx_rate_data[start_idx:]
    vis_tx = constants.tx_rate_data[start_idx:]
    vis_bw = constants.bandwidth_data[start_idx:]

    points_per_pixel = 1.2
    plot_px = max(1, window.signal_plot.viewport().width())
    max_points = max(200, int(plot_px * points_per_pixel))

    downsampled = False
    downsample_step = 1
    tail_points = 60

    # Cache downsampled history so long windows (e.g. 4h) don't rerender the entire
    # history every tick. Only recompute when the downsampling parameters change or
    # enough new points accumulate to add at least one full bucket.
    if not hasattr(window, "_ds_cache"):
        window._ds_cache = None

    if len(vis_time) > max_points + tail_points:
        hist_time_raw = vis_time[:-tail_points]
        hist_signal_raw = vis_signal[:-tail_points]
        hist_rx_raw = vis_rx[:-tail_points]
        hist_tx_raw = vis_tx[:-tail_points]
        hist_bw_raw = vis_bw[:-tail_points]

        tail_time = vis_time[-tail_points:]
        tail_signal = vis_signal[-tail_points:]
        tail_rx = vis_rx[-tail_points:]
        tail_tx = vis_tx[-tail_points:]
        tail_bw = vis_bw[-tail_points:]

        step = max(1, int(np.ceil(len(hist_time_raw) / max(1, max_points // 2))))

        # Stable bucket alignment: downsample history using absolute-time buckets
        # so deep history doesn't reshuffle as the 4h cutoff slides.
        dt = float(np.median(np.diff(constants.time_data))) if len(constants.time_data) > 2 else 1.0
        t0 = constants.time_data[0] if len(constants.time_data) else 0.0

        # Cache should not depend on start_idx (which changes every tick for sliding
        # windows); downsampling is stable in absolute time.
        cache_key = (step, tail_points, max_points, plot_px, float(t0), float(dt))
        cache = window._ds_cache

        can_reuse = (
            cache is not None
            and cache.get("key") == cache_key
            and cache.get("hist_raw_len", 0) <= len(hist_time_raw)
        )

        if can_reuse and (len(hist_time_raw) - cache["hist_raw_len"]) < step:
            hist_time = cache["hist_time"]
            hist_signal = cache["hist_signal"]
            hist_rx = cache["hist_rx"]
            hist_tx = cache["hist_tx"]
            hist_bw = cache["hist_bw"]
            # Extend tail to include points between cached history end and current tail start
            # to avoid a gap when cache is reused but new points accumulated.
            cached_hist_len = cache["hist_raw_len"]
            tail_time = vis_time[cached_hist_len:]
            tail_signal = vis_signal[cached_hist_len:]
            tail_rx = vis_rx[cached_hist_len:]
            tail_tx = vis_tx[cached_hist_len:]
            tail_bw = vis_bw[cached_hist_len:]
        else:
            # Downsample all series together using a shared time grid to ensure
            # all Y arrays stay aligned with the same X timestamps.
            hist_time, (hist_signal, hist_rx, hist_tx, hist_bw) = _downsample_multi_timebucket(
                hist_time_raw,
                [hist_signal_raw, hist_rx_raw, hist_tx_raw, hist_bw_raw],
                step,
                t0=t0,
                dt=dt,
            )

            window._ds_cache = {
                "key": cache_key,
                "hist_raw_len": len(hist_time_raw),
                "hist_time": hist_time,
                "hist_signal": hist_signal,
                "hist_rx": hist_rx,
                "hist_tx": hist_tx,
                "hist_bw": hist_bw,
            }

        vis_time = np.concatenate([hist_time, tail_time])
        vis_signal = np.concatenate([hist_signal, tail_signal])
        vis_rx = np.concatenate([hist_rx, tail_rx])
        vis_tx = np.concatenate([hist_tx, tail_tx])
        vis_bw = np.concatenate([hist_bw, tail_bw])

        downsampled = True
        downsample_step = step
        tail_time_for_downsample = tail_time
        # Track where tail starts in raw vis_* arrays (before downsampling) for ping alignment
        # When cache reused: cached_hist_len, otherwise: len(hist_time_raw) (original split point)
        if can_reuse and (len(hist_time_raw) - cache["hist_raw_len"]) < step:
            raw_tail_start = cache["hist_raw_len"]
        else:
            raw_tail_start = len(hist_time_raw)

    if not downsampled:
        vis_signal = smooth_data(vis_signal, alpha=0.3)
        vis_rx = smooth_data(vis_rx, alpha=0.3)
        vis_tx = smooth_data(vis_tx, alpha=0.3)
        vis_bw = smooth_data(vis_bw, alpha=0.3)

    for plot in [window.signal_plot, window.ping_plot, window.rate_plot, window.bw_plot]:
        plot.setUpdatesEnabled(False)

    window.signal_curve.setData(vis_time, vis_signal)
    window.rx_curve.setData(vis_time, vis_rx)
    window.tx_curve.setData(vis_time, vis_tx)
    window.bw_curve.setData(vis_time, vis_bw)

    for i, host_info in enumerate(constants.ping_hosts):
        if i >= len(window.ping_curves):
            break

        if len(host_info["data"]) > start_idx:
            vis_ping = host_info["data"][start_idx:]

            if len(vis_ping) > 0:
                if downsampled and len(vis_ping) > raw_tail_start:
                    hist_ping = vis_ping[:raw_tail_start]
                    tail_ping = vis_ping[raw_tail_start:]

                    # Use the original timebase for ping; `vis_time` may already be
                    # min/max downsampled for other series.
                    hist_ping_time = constants.time_data[start_idx:][:raw_tail_start]

                    # Ping downsampling must also be stable under sliding windows.
                    # Use absolute-time buckets (same as other plots), but aggregate
                    # with mean per bucket for ping.
                    bucket = max(1, downsample_step // 2)

                    dt = float(np.median(np.diff(constants.time_data))) if len(constants.time_data) > 2 else 1.0
                    t0 = constants.time_data[0] if len(constants.time_data) else 0.0
                    dt = max(float(dt), 1e-6)
                    bucket_period = bucket * dt

                    if len(hist_ping_time) > 0:
                        bidx = np.floor((hist_ping_time - t0) / bucket_period).astype(np.int64)
                        # Find bucket boundaries
                        changes = np.nonzero(np.diff(bidx))[0] + 1
                        starts = np.concatenate([[0], changes])
                        ends = np.concatenate([changes, [len(bidx)]])

                        out_t = []
                        out_y = []
                        for s, e in zip(starts, ends):
                            t_chunk = hist_ping_time[s:e]
                            y_chunk = hist_ping[s:e]
                            mid = len(t_chunk) // 2
                            out_t.append(t_chunk[mid])

                            finite = np.isfinite(y_chunk)
                            if not np.any(finite):
                                out_y.append(np.nan)
                            else:
                                out_y.append(float(np.nanmean(y_chunk[finite])))

                        hist_ping_time_ds = np.asarray(out_t)
                        hist_ping_ds = np.asarray(out_y)
                    else:
                        hist_ping_time_ds = np.array([], dtype=float)
                        hist_ping_ds = np.array([], dtype=float)

                    hist_ping_ds = smooth_data(hist_ping_ds, alpha=0.3)
                    tail_ping_smooth = smooth_data(tail_ping, alpha=0.3)

                    vis_ping_time = np.concatenate([hist_ping_time_ds, tail_time_for_downsample])
                    vis_ping = np.concatenate([hist_ping_ds, tail_ping_smooth])
                else:
                    vis_ping_time = vis_time

                min_len = min(len(vis_ping_time), len(vis_ping))

                window.ping_curves[i].setData(
                    vis_ping_time[:min_len],
                    vis_ping[:min_len],
                    connect="finite",
                )

    for plot in [window.signal_plot, window.ping_plot, window.rate_plot, window.bw_plot]:
        plot.enableAutoRange(axis="y")

    if not window.is_zoomed and len(vis_time) > 0:
        # Use the actual window boundaries (cutoff to now) rather than
        # data timestamps to avoid empty gaps at the left edge caused by
        # bucket alignment in downsampling.
        if constants.current_window is not None:
            x_start = now - constants.current_window
            x_end = now
        else:
            x_start = vis_time[0]
            x_end = vis_time[-1]
        window.signal_plot.setXRange(x_start, x_end, padding=0.02)

    for plot in [window.signal_plot, window.ping_plot, window.rate_plot, window.bw_plot]:
        plot.setUpdatesEnabled(True)

    draw_failure_regions(window, 0, constants.signal_failed, start_idx)
    draw_failure_regions(window, 2, constants.rates_failed, start_idx)
    draw_failure_regions(window, 3, constants.bandwidth_failed, start_idx)
    if constants.ping_hosts and len(constants.ping_hosts[0]["failed"]) > start_idx:
        draw_failure_regions(window, 1, constants.ping_hosts[0]["failed"], start_idx)
    else:
        draw_failure_regions(window, 1, [], start_idx)

    window.last_drawn_index = len(constants.time_data)


def draw_charts(window):
    if len(constants.time_data) == 0:
        return

    # When zoomed, avoid recomputing the full downsampled history every tick.
    # It's enough to append/update the newest points; the view is fixed by the zoom.
    if window.is_zoomed:
        window.needs_full_redraw = False
    elif window.needs_full_redraw:
        full_redraw(window)
        window.needs_full_redraw = False
        return

    if window.last_drawn_index >= len(constants.time_data):
        return

    if constants.current_window is None:
        start_idx = 0
    else:
        cutoff = time.time() - constants.current_window
        start_idx = np.searchsorted(constants.time_data, cutoff, side="left")

    vis_len = len(constants.time_data) - start_idx
    points_per_pixel = 1.2
    plot_px = max(1, window.signal_plot.viewport().width())
    max_points = max(200, int(plot_px * points_per_pixel))

    if vis_len <= max_points and not window.is_zoomed:
        new_start = window.last_drawn_index
        new_end = len(constants.time_data)

        if new_end > new_start:
            new_time = constants.time_data[new_start:new_end]

            context_start = max(0, new_start - 10)
            new_signal = smooth_data(constants.signal_data[context_start:new_end], alpha=0.3)[
                -(new_end - new_start) :
            ]
            new_rx = smooth_data(constants.rx_rate_data[context_start:new_end], alpha=0.3)[
                -(new_end - new_start) :
            ]
            new_tx = smooth_data(constants.tx_rate_data[context_start:new_end], alpha=0.3)[
                -(new_end - new_start) :
            ]
            new_bw = smooth_data(constants.bandwidth_data[context_start:new_end], alpha=0.3)[
                -(new_end - new_start) :
            ]

            existing_signal = window.signal_curve.getData()
            existing_rx = window.rx_curve.getData()
            existing_tx = window.tx_curve.getData()
            existing_bw = window.bw_curve.getData()

            if existing_signal[0] is not None and len(existing_signal[0]) > 0:
                all_time = np.concatenate([existing_signal[0], new_time])
                all_signal = np.concatenate([existing_signal[1], new_signal])
                all_rx = np.concatenate([existing_rx[1], new_rx])
                all_tx = np.concatenate([existing_tx[1], new_tx])
                all_bw = np.concatenate([existing_bw[1], new_bw])
            else:
                all_time = new_time
                all_signal = new_signal
                all_rx = new_rx
                all_tx = new_tx
                all_bw = new_bw

            if constants.current_window is not None:
                cutoff = time.time() - constants.current_window
                trim_idx = np.searchsorted(all_time, cutoff, side="left")
                all_time = all_time[trim_idx:]
                all_signal = all_signal[trim_idx:]
                all_rx = all_rx[trim_idx:]
                all_tx = all_tx[trim_idx:]
                all_bw = all_bw[trim_idx:]

            for plot in [window.signal_plot, window.ping_plot, window.rate_plot, window.bw_plot]:
                plot.setUpdatesEnabled(False)

            window.signal_curve.setData(all_time, all_signal)
            window.rx_curve.setData(all_time, all_rx)
            window.tx_curve.setData(all_time, all_tx)
            window.bw_curve.setData(all_time, all_bw)

            for i, host_info in enumerate(constants.ping_hosts):
                if i >= len(window.ping_curves):
                    break

                if len(host_info["data"]) >= new_end:
                    new_ping_smooth = smooth_data(
                        host_info["data"][context_start:new_end],
                        alpha=0.3,
                    )[-(new_end - new_start) :]

                    existing_ping = window.ping_curves[i].getData()

                    if existing_ping[0] is not None and len(existing_ping[0]) > 0:
                        all_ping_time = np.concatenate([existing_ping[0], new_time])
                        all_ping_data = np.concatenate([existing_ping[1], new_ping_smooth])

                        if constants.current_window is not None:
                            cutoff = time.time() - constants.current_window
                            trim_idx = np.searchsorted(all_ping_time, cutoff, side="left")
                            all_ping_time = all_ping_time[trim_idx:]
                            all_ping_data = all_ping_data[trim_idx:]

                        window.ping_curves[i].setData(
                            all_ping_time, all_ping_data, connect="finite"
                        )
                    else:
                        window.ping_curves[i].setData(
                            new_time, new_ping_smooth, connect="finite"
                        )

            if len(all_time) > 0:
                # Use actual window boundaries for consistent X-range
                if constants.current_window is not None:
                    now = time.time()
                    x_start = now - constants.current_window
                    x_end = now
                else:
                    x_start = all_time[0]
                    x_end = all_time[-1]
                window.signal_plot.setXRange(x_start, x_end, padding=0.02)

            for plot in [window.signal_plot, window.ping_plot, window.rate_plot, window.bw_plot]:
                plot.setUpdatesEnabled(True)

            draw_failure_regions(window, 0, constants.signal_failed, start_idx)
            draw_failure_regions(window, 2, constants.rates_failed, start_idx)
            draw_failure_regions(window, 3, constants.bandwidth_failed, start_idx)
            if constants.ping_hosts and len(constants.ping_hosts[0]["failed"]) > start_idx:
                draw_failure_regions(window, 1, constants.ping_hosts[0]["failed"], start_idx)
            else:
                draw_failure_regions(window, 1, [], start_idx)

        window.last_drawn_index = len(constants.time_data)

    else:
        full_redraw(window)
