import time

import numpy as np
import pyqtgraph as pg

from .. import constants
from ..data import smooth_data


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

    if constants.current_window is None:
        start_idx = 0
    else:
        cutoff = time.time() - constants.current_window
        start_idx = np.searchsorted(constants.time_data, cutoff, side="left")

    vis_time = constants.time_data[start_idx:]
    vis_signal = constants.signal_data[start_idx:]
    vis_rx = constants.rx_rate_data[start_idx:]
    vis_tx = constants.tx_rate_data[start_idx:]
    vis_bw = constants.bandwidth_data[start_idx:]

    if constants.current_window is None or constants.current_window >= 14400:
        max_points = 600
    elif constants.current_window >= 3600:
        max_points = 1000
    else:
        max_points = 2000

    downsampled = False
    downsample_step = 1
    tail_points = 60

    if len(vis_time) > max_points + tail_points:
        hist_time = vis_time[:-tail_points]
        hist_signal = vis_signal[:-tail_points]
        hist_rx = vis_rx[:-tail_points]
        hist_tx = vis_tx[:-tail_points]
        hist_bw = vis_bw[:-tail_points]

        tail_time = vis_time[-tail_points:]
        tail_signal = vis_signal[-tail_points:]
        tail_rx = vis_rx[-tail_points:]
        tail_tx = vis_tx[-tail_points:]
        tail_bw = vis_bw[-tail_points:]

        if constants.current_window is not None:
            step = max(1, constants.current_window // max_points)
        else:
            raw_step = len(hist_time) // max_points
            step = 2 ** int(np.log2(max(1, raw_step))) if raw_step > 0 else 1

        offset = (step - (start_idx % step)) % step
        hist_time = hist_time[offset::step]
        hist_signal = hist_signal[offset::step]
        hist_rx = hist_rx[offset::step]
        hist_tx = hist_tx[offset::step]
        hist_bw = hist_bw[offset::step]

        vis_time = np.concatenate([hist_time, tail_time])
        vis_signal = np.concatenate([hist_signal, tail_signal])
        vis_rx = np.concatenate([hist_rx, tail_rx])
        vis_tx = np.concatenate([hist_tx, tail_tx])
        vis_bw = np.concatenate([hist_bw, tail_bw])

        downsampled = True
        downsample_step = step

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
                if downsampled and len(vis_ping) > tail_points:
                    hist_ping = vis_ping[:-tail_points]
                    tail_ping = vis_ping[-tail_points:]
                    offset = (downsample_step - (start_idx % downsample_step)) % downsample_step
                    hist_ping = hist_ping[offset::downsample_step]
                    vis_ping = np.concatenate([hist_ping, tail_ping])

                min_len = min(len(vis_time), len(vis_ping))

                window.ping_curves[i].setData(
                    vis_time[:min_len],
                    vis_ping[:min_len],
                    connect="finite",
                )

    for plot in [window.signal_plot, window.ping_plot, window.rate_plot, window.bw_plot]:
        plot.enableAutoRange(axis="y")

    if not window.is_zoomed and len(vis_time) > 0:
        window.signal_plot.setXRange(vis_time[0], vis_time[-1], padding=0.02)

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

    if window.needs_full_redraw or window.is_zoomed:
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
    if constants.current_window is None or constants.current_window >= 14400:
        max_points = 600
    elif constants.current_window >= 3600:
        max_points = 1000
    else:
        max_points = 2000

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
                window.signal_plot.setXRange(all_time[0], all_time[-1], padding=0.02)

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
