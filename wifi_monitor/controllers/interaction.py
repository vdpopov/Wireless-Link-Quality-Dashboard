from datetime import datetime

import numpy as np
import pyqtgraph as pg
from PyQt5.QtCore import QEvent, Qt
from PyQt5.QtGui import QCursor
from PyQt5.QtWidgets import QApplication

from .. import constants


def resize_event(window, event):
    window._base_resize_event(event)

    if not window.is_resizing:
        window.is_resizing = True
        for overlay in window.failure_overlays:
            overlay.hide()

    for i, plot in enumerate([window.signal_plot, window.ping_plot, window.rate_plot, window.bw_plot]):
        window.failure_overlays[i].setGeometry(plot.viewport().rect())
        window.hover_overlays[i].setGeometry(plot.viewport().rect())
        window.selection_overlays[i].setGeometry(plot.viewport().rect())

    window.resize_timer.stop()
    window.resize_timer.start(100)


def on_resize_finished(window):
    window.is_resizing = False

    for overlay in window.failure_overlays:
        overlay.show()

    window.needs_full_redraw = True
    window.draw_charts()


def event_filter(window, obj, event):
    plots = [window.signal_plot, window.ping_plot, window.rate_plot, window.bw_plot]

    if event.type() == QEvent.MouseButtonPress and event.button() == Qt.LeftButton:
        for idx, plot in enumerate(plots):
            if obj == plot.viewport():
                scene_pos = plot.mapToScene(event.pos())

                if idx == 1 and getattr(window, "ping_legend", None):
                    if window.ping_legend.sceneBoundingRect().contains(scene_pos):
                        return False

                if idx == 2 and getattr(window, "rate_legend", None):
                    if window.rate_legend.sceneBoundingRect().contains(scene_pos):
                        return False

                vb = plot.getViewBox()
                if vb.sceneBoundingRect().contains(scene_pos):
                    mouse_point = vb.mapSceneToView(scene_pos)
                    window.select_start = mouse_point.x()
                    window.selecting = True
                    window.selecting_plot_idx = idx
                    window.selection_left_lines[idx].setPos(window.select_start)
                    window.selection_right_lines[idx].setPos(window.select_start)
                    window.selection_left_lines[idx].show()
                    window.selection_right_lines[idx].show()
                break

    elif event.type() == QEvent.MouseMove and window.selecting:
        if hasattr(window, "selecting_plot_idx"):
            plot = plots[window.selecting_plot_idx]
            scene_pos = plot.mapToScene(event.pos())
            on_mouse_move(window, scene_pos, window.selecting_plot_idx)

    elif event.type() == QEvent.MouseButtonRelease and event.button() == Qt.LeftButton:
        if window.selecting:
            apply_selection(window)

    elif event.type() == QEvent.MouseButtonDblClick and event.button() == Qt.LeftButton:
        window.reset_zoom()

    elif event.type() == QEvent.Leave:
        for idx, plot in enumerate(plots):
            if obj == plot.viewport():
                hide_hover_for_plot(window, idx)
                break

    elif event.type() == QEvent.MouseMove:
        if window.active_hover_plot is not None:
            validate_active_hover(window)

    elif event.type() == QEvent.ApplicationDeactivate:
        hide_all_hovers(window)

    return window._base_event_filter(obj, event)


def apply_selection(window):
    if hasattr(window, "selecting_plot_idx") and window.select_start is not None:
        idx = window.selecting_plot_idx
        if window.selection_left_lines[idx].isVisible():
            x_min = window.selection_left_lines[idx].pos().x()
            x_max = window.selection_right_lines[idx].pos().x()
            if abs(x_max - x_min) > 0.5:
                window.signal_plot.setXRange(x_min, x_max, padding=0)
                window.is_zoomed = True
                window.reset_btn.show()
                window.needs_full_redraw = True

    for i in range(4):
        window.selection_left_lines[i].hide()
        window.selection_right_lines[i].hide()
        window.selection_overlays[i].hide()
    window.selecting = False
    window.select_start = None

    if window.is_zoomed:
        window._full_redraw()


def on_mouse_move(window, pos, plot_idx):
    if not window.selecting:
        return

    if not hasattr(window, "selecting_plot_idx") or window.selecting_plot_idx != plot_idx:
        return

    plots = [window.signal_plot, window.ping_plot, window.rate_plot, window.bw_plot]
    plot = plots[plot_idx]
    vb = plot.getViewBox()

    mouse_point = vb.mapSceneToView(pos)
    x = mouse_point.x()

    window.hover_overlays[plot_idx].hideAll()

    min_x = min(window.select_start, x)
    max_x = max(window.select_start, x)
    window.selection_left_lines[plot_idx].setPos(min_x)
    window.selection_right_lines[plot_idx].setPos(max_x)

    vb_rect = vb.sceneBoundingRect()
    topleft = plot.mapFromScene(vb_rect.topLeft())
    bottomright = plot.mapFromScene(vb_rect.bottomRight())

    left_scene = vb.mapViewToScene(pg.Point(min_x, 0))
    right_scene = vb.mapViewToScene(pg.Point(max_x, 0))
    left_pixel = plot.mapFromScene(left_scene).x()
    right_pixel = plot.mapFromScene(right_scene).x()

    overlay = window.selection_overlays[plot_idx]
    overlay.setGeometry(plot.viewport().rect())
    overlay.setSelection(left_pixel, right_pixel, topleft.y(), bottomright.y())
    overlay.show()
    overlay.raise_()


def hide_hover_for_plot(window, plot_idx):
    if 0 <= plot_idx < len(window.hover_overlays):
        window.hover_overlays[plot_idx].hideAll()
        if window.active_hover_plot == plot_idx:
            window.active_hover_plot = None


def hide_all_hovers(window):
    for overlay in window.hover_overlays:
        overlay.hideAll()
    window.active_hover_plot = None


def validate_active_hover(window):
    if window.active_hover_plot is None:
        return

    plots = [window.signal_plot, window.ping_plot, window.rate_plot, window.bw_plot]
    plot = plots[window.active_hover_plot]

    cursor_pos = QCursor.pos()
    widget_pos = plot.viewport().mapFromGlobal(cursor_pos)

    is_inside = plot.viewport().rect().contains(widget_pos)

    if not is_inside:
        hide_hover_for_plot(window, window.active_hover_plot)


def update_hover_from_cursor(window):
    if window.selecting:
        for overlay in window.hover_overlays:
            overlay.hideAll()
        return

    if not window.underMouse():
        for overlay in window.hover_overlays:
            overlay.hideAll()
        return

    cursor_pos = QCursor.pos()

    widget_under_cursor = QApplication.widgetAt(cursor_pos)
    if widget_under_cursor is None or widget_under_cursor.window() != window:
        for overlay in window.hover_overlays:
            overlay.hideAll()
        return

    plots = [window.signal_plot, window.ping_plot, window.rate_plot, window.bw_plot]

    for idx, plot in enumerate(plots):
        widget_pos = plot.viewport().mapFromGlobal(cursor_pos)
        if plot.viewport().rect().contains(widget_pos):
            window.hover_overlays[idx].setGeometry(plot.viewport().rect())

            update_hover_for_plot(window, idx, widget_pos)

            for other_idx in range(4):
                if other_idx != idx:
                    window.hover_overlays[other_idx].hideAll()
            return

    for overlay in window.hover_overlays:
        overlay.hideAll()


def update_hover_for_plot(window, plot_idx, widget_pos):
    plots = [window.signal_plot, window.ping_plot, window.rate_plot, window.bw_plot]
    plot = plots[plot_idx]
    vb = plot.getViewBox()
    overlay = window.hover_overlays[plot_idx]

    scene_pos = plot.mapToScene(widget_pos)

    if not vb.sceneBoundingRect().contains(scene_pos):
        overlay.hideAll()
        return

    if plot_idx == 1 and getattr(window, "ping_legend", None):
        if window.ping_legend.sceneBoundingRect().contains(scene_pos):
            overlay.hideAll()
            return

    if plot_idx == 2 and getattr(window, "rate_legend", None):
        if window.rate_legend.sceneBoundingRect().contains(scene_pos):
            overlay.hideAll()
            return

    mouse_point = vb.mapSceneToView(scene_pos)
    x = mouse_point.x()
    y = mouse_point.y()

    view_range = vb.viewRange()
    if not (view_range[0][0] <= x <= view_range[0][1] and view_range[1][0] <= y <= view_range[1][1]):
        overlay.hideAll()
        return

    data_point = pg.Point(x, view_range[1][0])
    scene_point = vb.mapViewToScene(data_point)
    pixel_point = plot.mapFromScene(scene_point)
    pixel_x = pixel_point.x()

    overlay.setCrosshair(pixel_x)

    if len(constants.time_data) == 0:
        overlay.setLabel(None, 0, 0)
        return

    closest_idx = np.searchsorted(constants.time_data, x, side="left")
    if closest_idx > 0 and closest_idx < len(constants.time_data):
        if abs(constants.time_data[closest_idx - 1] - x) < abs(constants.time_data[closest_idx] - x):
            closest_idx -= 1
    elif closest_idx >= len(constants.time_data):
        closest_idx = len(constants.time_data) - 1

    ts = constants.time_data[closest_idx]
    dt = datetime.fromtimestamp(ts)

    if len(constants.time_data) > 1 and (constants.time_data[-1] - constants.time_data[0]) > 86400:
        lines = [dt.strftime("%Y-%m-%d %H:%M:%S")]
    else:
        lines = [dt.strftime("%H:%M:%S")]

    if plot_idx == 0:
        if closest_idx < len(constants.signal_data) and not np.isnan(constants.signal_data[closest_idx]):
            lines.append(f"Signal: {constants.signal_data[closest_idx]:.0f} dBm")
    elif plot_idx == 1:
        for host_info in constants.ping_hosts:
            if closest_idx < len(host_info["data"]) and not np.isnan(host_info["data"][closest_idx]):
                lines.append(f"{host_info['label']}: {host_info['data'][closest_idx]:.1f}ms")
    elif plot_idx == 2:
        if closest_idx < len(constants.rx_rate_data) and not np.isnan(constants.rx_rate_data[closest_idx]):
            lines.append(f"RX: {constants.rx_rate_data[closest_idx]:.1f} Mbps")
        if closest_idx < len(constants.tx_rate_data) and not np.isnan(constants.tx_rate_data[closest_idx]):
            lines.append(f"TX: {constants.tx_rate_data[closest_idx]:.1f} Mbps")
    elif plot_idx == 3:
        if closest_idx < len(constants.bandwidth_data) and not np.isnan(constants.bandwidth_data[closest_idx]):
            lines.append(f"BW: {constants.bandwidth_data[closest_idx]:.0f} MHz")

    if len(lines) > 1:
        overlay.setLabel("\n".join(lines), widget_pos.x(), widget_pos.y())
    else:
        overlay.setLabel(None, 0, 0)
