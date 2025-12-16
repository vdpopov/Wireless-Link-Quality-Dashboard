import re

import pyqtgraph as pg
from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtWidgets import (
    QApplication,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from .. import constants
from ..controllers import collection, interaction, rendering
from ..overlays import FailureOverlay, HoverOverlay, SelectionOverlay
from ..ping import remove_ping_host
from ..plot_items import TimeAxisItem, setup_legend
from ..widgets.heatmap import ChannelHeatmap
from ..widgets.ping_bar import build_ping_bar, refresh_ping_host_buttons


class WifiMonitor(QMainWindow):
    def __init__(self, antialias_default: bool):
        super().__init__()
        self.antialias_default = antialias_default

        self.setWindowTitle(f"WiFi Monitor [{constants.INTERFACE}]")
        self.setGeometry(100, 100, 1200, 850)

        self.last_drawn_index = 0
        self.needs_full_redraw = True

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setSpacing(5)

        top_bar = QHBoxLayout()

        self.window_buttons = {}
        for label in ["10m", "30m", "60m", "4h", "1D", "∞"]:
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.clicked.connect(lambda checked, l=label: self.set_window(l))
            top_bar.addWidget(btn)
            self.window_buttons[label] = btn
        self.window_buttons["10m"].setChecked(True)

        self.reset_btn = QPushButton("Reset Zoom")
        self.reset_btn.clicked.connect(self.reset_zoom)
        self.reset_btn.hide()
        top_bar.addWidget(self.reset_btn)

        top_bar.addSpacing(20)
        top_bar.addWidget(QLabel("Refresh:"))
        self.refresh_combo = QComboBox()
        self.refresh_combo.addItems(["500ms", "1 sec", "2 sec", "3 sec", "5 sec"])
        self.refresh_combo.setCurrentText("1 sec")
        self.refresh_combo.currentTextChanged.connect(self.on_refresh_change)
        top_bar.addWidget(self.refresh_combo)

        top_bar.addSpacing(20)
        self.pause_btn = QPushButton("Pause")
        self.pause_btn.clicked.connect(self.toggle_pause)
        top_bar.addWidget(self.pause_btn)

        top_bar.addStretch()
        layout.addLayout(top_bar)

        # Create tab widget
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)

        # Tab 0: Live Monitor
        live_monitor = QWidget()
        live_layout = QVBoxLayout(live_monitor)
        live_layout.setContentsMargins(0, 0, 0, 0)
        live_layout.setSpacing(5)
        self.tabs.addTab(live_monitor, "Live Monitor")

        # Tab 1: Channel Heatmap
        self.heatmap_widget = ChannelHeatmap()
        self.tabs.addTab(self.heatmap_widget, "Channel Heatmap")

        self.signal_plot = pg.PlotWidget(axisItems={"bottom": TimeAxisItem(orientation="bottom")})
        self.signal_plot.setMenuEnabled(False)
        self.signal_plot.setLabel("left", "dBm")
        self.signal_plot.setTitle("Signal", anchor="w")
        self.signal_plot.showGrid(x=True, y=True, alpha=0.15)
        self.signal_curve = self.signal_plot.plot(
            pen=pg.mkPen("b", width=2),
            antialias=self.antialias_default,
        )
        self.signal_plot.setMouseEnabled(x=False, y=False)
        self.signal_plot.wheelEvent = lambda evt: None
        self.signal_plot.hideButtons()
        self.signal_plot.setClipToView(True)
        self.signal_plot.setDownsampling(auto=False)
        live_layout.addWidget(self.signal_plot)

        build_ping_bar(self, live_layout)

        self.ping_plot = pg.PlotWidget(axisItems={"bottom": TimeAxisItem(orientation="bottom")})
        self.ping_plot.setMenuEnabled(False)
        self.ping_plot.setLabel("left", "ms")
        self.ping_plot.setTitle("Ping", anchor="w")
        self.ping_plot.showGrid(x=True, y=True, alpha=0.15)
        self.ping_legend = setup_legend(self.ping_plot)
        self.ping_curves = []
        self.ping_plot.setMouseEnabled(x=False, y=False)
        self.ping_plot.wheelEvent = lambda evt: None
        self.ping_plot.hideButtons()
        self.ping_plot.setClipToView(True)
        self.ping_plot.setDownsampling(auto=False)
        live_layout.addWidget(self.ping_plot)

        self.rate_plot = pg.PlotWidget(axisItems={"bottom": TimeAxisItem(orientation="bottom")})
        self.rate_plot.setMenuEnabled(False)
        self.rate_plot.setLabel("left", "Mbps")
        self.rate_plot.setTitle("RX / TX", anchor="w")
        self.rate_plot.showGrid(x=True, y=True, alpha=0.10)
        self.rate_legend = setup_legend(self.rate_plot)
        self.rx_curve = self.rate_plot.plot(
            pen=pg.mkPen("g", width=2),
            antialias=self.antialias_default,
        )
        self.tx_curve = self.rate_plot.plot(
            pen=pg.mkPen("m", width=2),
            antialias=self.antialias_default,
        )
        self.rate_legend.addItem(self.rx_curve, "RX")
        self.rate_legend.addItem(self.tx_curve, "TX")
        self.rate_plot.setMouseEnabled(x=False, y=False)
        self.rate_plot.wheelEvent = lambda evt: None
        self.rate_plot.hideButtons()
        self.rate_plot.setClipToView(True)
        self.rate_plot.setDownsampling(auto=False)
        live_layout.addWidget(self.rate_plot)

        self.bw_plot = pg.PlotWidget(axisItems={"bottom": TimeAxisItem(orientation="bottom")})
        self.bw_plot.setMenuEnabled(False)
        self.bw_plot.setLabel("left", "MHz")
        self.bw_plot.setTitle("Bandwidth", anchor="w")
        self.bw_plot.setLabel("bottom", "Time")
        self.bw_plot.showGrid(x=True, y=True, alpha=0.15)
        self.bw_curve = self.bw_plot.plot(
            pen=pg.mkPen("#FFA500", width=2),
            antialias=self.antialias_default,
        )
        self.bw_plot.setMouseEnabled(x=False, y=False)
        self.bw_plot.wheelEvent = lambda evt: None
        self.bw_plot.hideButtons()
        self.bw_plot.setClipToView(True)
        self.bw_plot.setDownsampling(auto=False)
        live_layout.addWidget(self.bw_plot)

        self.ping_plot.setXLink(self.signal_plot)
        self.rate_plot.setXLink(self.signal_plot)
        self.bw_plot.setXLink(self.signal_plot)

        self.is_zoomed = False

        self.selection_left_lines = []
        self.selection_right_lines = []
        self.selection_overlays = []
        for plot in [self.signal_plot, self.ping_plot, self.rate_plot, self.bw_plot]:
            left = pg.InfiniteLine(angle=90, movable=False, pen=pg.mkPen("b", width=2))
            right = pg.InfiniteLine(angle=90, movable=False, pen=pg.mkPen("b", width=2))
            left.hide()
            right.hide()
            plot.addItem(left, ignoreBounds=True)
            plot.addItem(right, ignoreBounds=True)
            self.selection_left_lines.append(left)
            self.selection_right_lines.append(right)

            overlay = SelectionOverlay(plot.viewport())
            overlay.setGeometry(plot.viewport().rect())
            overlay.hide()
            self.selection_overlays.append(overlay)

        self.selecting = False
        self.select_start = None

        for plot in [self.signal_plot, self.ping_plot, self.rate_plot, self.bw_plot]:
            plot.viewport().installEventFilter(self)

        self.hover_overlays = []
        for plot in [self.signal_plot, self.ping_plot, self.rate_plot, self.bw_plot]:
            overlay = HoverOverlay(plot.viewport())
            overlay.setGeometry(plot.viewport().rect())
            overlay.show()
            self.hover_overlays.append(overlay)

        self.failure_overlays = []
        for plot in [self.signal_plot, self.ping_plot, self.rate_plot, self.bw_plot]:
            overlay = FailureOverlay(plot.viewport())
            overlay.setGeometry(plot.viewport().rect())
            overlay.show()
            overlay.lower()
            self.failure_overlays.append(overlay)

        self.refresh_host_list()

        self.timer = QTimer()
        self.timer.timeout.connect(self.update_data)
        self.timer.start(constants.REFRESH_INTERVAL)

        self.active_hover_plot = None

        QApplication.instance().installEventFilter(self)

        self.hover_timer = QTimer()
        self.hover_timer.timeout.connect(self._update_hover_from_cursor)
        self.hover_timer.start(16)

        self.resize_timer = QTimer()
        self.resize_timer.setSingleShot(True)
        self.resize_timer.timeout.connect(self._on_resize_finished)
        self.is_resizing = False

    # ---- Qt events delegated to controller ----

    def resizeEvent(self, event):
        return interaction.resize_event(self, event)

    def _on_resize_finished(self):
        return interaction.on_resize_finished(self)

    def eventFilter(self, obj, event):
        return interaction.event_filter(self, obj, event)

    # ---- Hover tick ----

    def _update_hover_from_cursor(self):
        return interaction.update_hover_from_cursor(self)

    # ---- Commands / actions ----

    def set_window(self, label):
        constants.current_window = constants.TIME_WINDOWS[label]
        for l, btn in self.window_buttons.items():
            btn.setChecked(l == label)
        self.needs_full_redraw = True
        self.last_drawn_index = 0

        # Reset zoom state, and trigger redraw on the next Qt event-loop turn.
        # This keeps the UI responsive while still feeling immediate.
        self.is_zoomed = False
        self.reset_btn.hide()
        QTimer.singleShot(0, self.draw_charts)

    def reset_zoom(self):
        self.is_zoomed = False
        self.reset_btn.hide()
        self.needs_full_redraw = True
        self.draw_charts()

    def on_refresh_change(self, text):
        mapping = {
            "500ms": 500,
            "1 sec": 1000,
            "2 sec": 2000,
            "3 sec": 3000,
            "5 sec": 5000,
        }
        constants.REFRESH_INTERVAL = mapping.get(text, 1000)
        self.timer.setInterval(constants.REFRESH_INTERVAL)

    def toggle_pause(self):
        constants.paused = not constants.paused
        self.pause_btn.setText("Resume" if constants.paused else "Pause")
        if not constants.paused:
            self.needs_full_redraw = True

    # ---- Ping hosts ----

    def refresh_host_list(self):
        refresh_ping_host_buttons(self)
        rendering.update_ping_curves(self)

        # Immediately repopulate the newly-created ping curves (no visible blink).
        self.needs_full_redraw = True
        self.draw_charts()

    def add_host(self):
        host = self.host_entry.text().strip()
        if host:
            pattern = r"^[\d]{1,3}\.[\d]{1,3}\.[\d]{1,3}\.[\d]{1,3}$|^[a-zA-Z0-9][a-zA-Z0-9.\-]*$"
            if re.match(pattern, host):
                existing = [h["host"] for h in constants.ping_hosts] + [
                    h["label"] for h in constants.ping_hosts
                ]
                if host not in existing:
                    from ..ping import add_ping_host

                    add_ping_host(host)
                    self.refresh_host_list()
        self.host_entry.clear()

    def remove_host(self, idx):
        from .. import ping

        if 0 <= idx < len(constants.ping_hosts):
            if constants.ping_hosts[idx] is ping.gateway_host_info:
                ping.gateway_host_info = None
                ping.gateway_removed_by_user = True
        remove_ping_host(idx)
        self.refresh_host_list()

    # ---- Data + rendering ----

    def update_data(self):
        if not constants.paused:
            collection.collect_data(self)
            self.draw_charts()

    def draw_charts(self):
        return rendering.draw_charts(self)

    def _full_redraw(self):
        return rendering.full_redraw(self)

    # ---- Internal base calls (used by controllers) ----

    def _base_event_filter(self, obj, event):
        return super().eventFilter(obj, event)

    def _base_resize_event(self, event):
        return super().resizeEvent(event)
