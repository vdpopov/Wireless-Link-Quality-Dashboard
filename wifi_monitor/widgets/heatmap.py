from datetime import datetime

import numpy as np
import pyqtgraph as pg
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from .. import constants, scanner, storage
from ..overlays import HoverOverlay


class ChannelAxisItem(pg.AxisItem):
    """Custom axis for channel labels."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.channels = list(range(1, 15))  # Default to 2.4GHz

    def set_channels(self, channels):
        """Set channel numbers to display."""
        self.channels = channels

    def tickStrings(self, values, scale, spacing):
        strings = []
        for v in values:
            idx = int(round(v))
            if 0 <= idx < len(self.channels):
                strings.append(str(self.channels[idx]))
            else:
                strings.append("")
        return strings


class DateAxisItem(pg.AxisItem):
    """Custom axis for date labels."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.date_labels = []

    def set_dates(self, dates):
        """Set date labels (list of 'YYYY-MM-DD' strings)."""
        self.date_labels = dates

    def tickStrings(self, values, scale, spacing):
        strings = []
        for v in values:
            idx = int(round(v))
            if 0 <= idx < len(self.date_labels):
                # Format as "Dec 16"
                try:
                    date = datetime.strptime(self.date_labels[idx], "%Y-%m-%d")
                    strings.append(date.strftime("%b %d"))
                except ValueError:
                    strings.append(self.date_labels[idx])
            else:
                strings.append("")
        return strings


class ChannelHeatmap(QWidget):
    """Widget displaying channel congestion heatmap."""

    # Auto-scan interval: 1 hour in milliseconds
    AUTO_SCAN_INTERVAL_MS = 60 * 60 * 1000

    def __init__(self, parent=None):
        super().__init__(parent)
        self.days = 7
        self.scan_details = {}  # {date_str: {channel: [network_names]}}
        self.current_dates = []
        self.current_channels = list(range(1, 15))  # Current channel list
        self.current_band = "2.4"
        self._last_detected_band = None

        self._setup_ui()
        self.refresh_heatmap()

        # Set up auto-scan timer (checks every hour, scans if needed)
        self.auto_scan_timer = QTimer()
        self.auto_scan_timer.timeout.connect(self._check_auto_scan)
        self.auto_scan_timer.start(60 * 60 * 1000)  # Check every hour

        # Set up band change detection timer (check every 5 seconds)
        self.band_check_timer = QTimer()
        self.band_check_timer.timeout.connect(self._check_band_change)
        self.band_check_timer.start(5000)

        # Do initial scan check after a short delay (let UI settle)
        QTimer.singleShot(2000, self._check_auto_scan)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        # Top controls bar
        controls = QHBoxLayout()

        self.title_label = QLabel("Channel Congestion")
        self.title_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        controls.addWidget(self.title_label)

        controls.addStretch()

        # Days selector
        controls.addWidget(QLabel("Days:"))
        self.days_combo = QComboBox()
        self.days_combo.addItems(["7", "14", "30"])
        self.days_combo.currentTextChanged.connect(self._on_days_changed)
        controls.addWidget(self.days_combo)

        layout.addLayout(controls)

        # Create custom axes
        self.channel_axis = ChannelAxisItem(orientation="bottom")
        self.date_axis = DateAxisItem(orientation="left")

        # Create plot widget with custom axes
        self.plot = pg.PlotWidget(
            axisItems={"bottom": self.channel_axis, "left": self.date_axis}
        )
        self.plot.setMenuEnabled(False)
        self.plot.setLabel("bottom", "Channel")
        self.plot.setLabel("left", "Date")
        self.plot.showGrid(x=False, y=False)
        self.plot.setMouseEnabled(x=False, y=False)
        self.plot.hideButtons()

        # Enable mouse tracking for tooltips
        self.plot.scene().sigMouseMoved.connect(self._on_mouse_moved)

        # Create ImageItem for heatmap
        self.img = pg.ImageItem()
        self.plot.addItem(self.img)

        # Apply colormap to image (must be done after creating cmap below)

        # Create colormap: gray (no data) -> green (clear) -> red (congested)
        # With levels [-1, 8]: -1 maps to 0.0, 0 maps to 0.111, 8 maps to 1.0
        colors = [
            (0.3, 0.3, 0.3),      # Gray for "no data" (value -1 -> pos 0.0)
            (0.0, 0.75, 0.0),     # Green for 0 (clear channel -> pos 0.111)
            (0.5, 0.85, 0.0),     # Light green for 1-2
            (0.9, 0.9, 0.0),      # Yellow for 3-4
            (1.0, 0.5, 0.0),      # Orange for 5-6
            (1.0, 0.0, 0.0),      # Red for 7-8
        ]
        # Gray only at 0.0, green starts at 0.05 (before value 0's position of 0.111)
        positions = [0.0, 0.05, 0.25, 0.50, 0.75, 1.0]
        self.cmap = pg.ColorMap(positions, [tuple(int(c * 255) for c in color) + (255,) for color in colors])

        # Get lookup table from colormap
        self.lut = self.cmap.getLookupTable(0.0, 1.0, 256)

        # Create color bar (don't link to image - it overrides our LUT)
        self.colorbar = pg.ColorBarItem(
            values=(0, 8),
            colorMap=self.cmap,
            label="Networks"
        )
        # Don't call setImageItem - we'll manage the LUT ourselves

        # Apply LUT to image
        self.img.setLookupTable(self.lut)

        layout.addWidget(self.plot, stretch=1)

        # Add hover overlay for tooltips
        self.hover_overlay = HoverOverlay(self.plot.viewport())
        self.hover_overlay.setGeometry(self.plot.viewport().rect())
        self.hover_overlay.show()

        # Status bar
        status_layout = QHBoxLayout()
        self.status_label = QLabel("No scan data")
        self.status_label.setStyleSheet("color: gray;")
        status_layout.addWidget(self.status_label)
        status_layout.addStretch()
        layout.addLayout(status_layout)

    def _on_days_changed(self, text):
        self.days = int(text)
        self.refresh_heatmap()

    def _check_band_change(self):
        """Check if the WiFi band changed and trigger a scan if needed."""
        from ..net import get_current_band

        current = get_current_band()
        if current and current != self._last_detected_band:
            old_band = self._last_detected_band
            self._last_detected_band = current

            # If we actually switched bands (not initial detection), do a scan
            if old_band is not None:
                self._do_band_switch_scan(current)
            else:
                self.refresh_heatmap()

    def _do_band_switch_scan(self, band):
        """Scan immediately when switching bands to populate data."""
        from PyQt5.QtWidgets import QApplication

        self.status_label.setText(f"Switched to {band}GHz, scanning...")
        self.status_label.setStyleSheet("color: blue;")
        QApplication.processEvents()

        try:
            scan_data = scanner.scan_channels(band=band)
            if scan_data:
                storage.save_scan(scan_data)
                self.status_label.setText(
                    f"Scanned {band}GHz: {datetime.now().strftime('%H:%M')}"
                )
                self.status_label.setStyleSheet("color: green;")
        except Exception:
            pass

        self.refresh_heatmap()

    def refresh_heatmap(self):
        """Reload data and update heatmap display."""
        data, dates, channels, band = storage.get_heatmap_data(self.days)

        # Store for tooltip lookup
        self.current_dates = dates
        self.current_channels = channels
        self.current_band = band

        # Update title with band info
        band_label = "2.4GHz" if band == "2.4" else "5GHz"
        self.title_label.setText(f"Channel Congestion ({band_label})")

        # Update channel axis labels
        self.channel_axis.set_channels(channels)

        # Load scan details for tooltips (network names per channel per day)
        self.scan_details = {}
        for date_str in dates:
            scans = storage.load_day_scans(date_str)
            if scans:
                # Filter by band and use the best scan (most networks) for this day
                band_scans = [s for s in scans if s.get("band") == band]
                if not band_scans and band == "2.4":
                    band_scans = [s for s in scans if s.get("band") is None]
                if band_scans:
                    best_scan = max(band_scans, key=storage._scan_total_networks)
                    channels_data = best_scan.get("channels", {})
                    self.scan_details[date_str] = {}
                    for ch in channels:
                        ch_data = channels_data.get(str(ch)) or channels_data.get(ch) or {}
                        self.scan_details[date_str][ch] = ch_data.get("networks", [])

        # Update date axis labels
        self.date_axis.set_dates(dates)

        if np.all(np.isnan(data)):
            # No data at all
            self.status_label.setText("No scan data available. Click 'Scan Now' to start.")
            self.status_label.setStyleSheet("color: gray;")
            self.img.clear()
            return

        # Replace NaN with -1 (no data = gray)
        display_data = np.nan_to_num(data, nan=-1)

        # Set image data
        # ImageItem expects (width, height) so transpose
        self.img.setImage(display_data.T, autoLevels=False)

        # Set levels: -1 (no data) to 8 (max for color spread)
        # This makes: -1 -> gray, 0 -> green, higher -> yellow/orange/red
        self.img.setLevels([-1, 8])

        # Re-apply lookup table after setImage
        self.img.setLookupTable(self.lut)

        # Position image correctly (channels on X, dates on Y)
        self.img.setRect(-0.5, -0.5, len(channels), len(dates))

        # Set axis ranges
        self.plot.setXRange(-0.5, len(channels) - 0.5, padding=0.05)
        self.plot.setYRange(-0.5, len(dates) - 0.5, padding=0.05)

        # Update status with last scan time
        last_scan = storage.get_last_scan_time()
        if last_scan:
            self.status_label.setText(
                f"Last scan: {last_scan.strftime('%b %d, %Y %H:%M')}"
            )
            self.status_label.setStyleSheet("color: gray;")

    def _check_auto_scan(self):
        """Auto-scan every hour, or immediately if no data for current band."""
        from datetime import timedelta
        from ..net import get_current_band

        current_band = get_current_band() or "2.4"
        self._last_detected_band = current_band

        # Check if we have any data for current band today
        today_scans = storage.load_day_scans(datetime.now().strftime("%Y-%m-%d"))
        band_scans = [s for s in today_scans if s.get("band") == current_band]

        needs_scan = False
        if not band_scans:
            # No data for current band - scan now
            needs_scan = True
        else:
            # Check if last scan was more than an hour ago
            last_scan = storage.get_last_scan_time()
            if last_scan is None or (datetime.now() - last_scan) > timedelta(hours=1):
                needs_scan = True

        if needs_scan:
            self._do_auto_scan()

    def _do_auto_scan(self):
        """Perform automatic background scan."""
        from PyQt5.QtWidgets import QApplication

        self.status_label.setText("Auto-scanning...")
        self.status_label.setStyleSheet("color: blue;")
        QApplication.processEvents()

        try:
            scan_data = scanner.scan_channels()
            if scan_data:
                storage.save_scan(scan_data)
                self.status_label.setText(
                    f"Auto-scan: {datetime.now().strftime('%b %d, %H:%M')}"
                )
                self.status_label.setStyleSheet("color: green;")
                self.refresh_heatmap()
        except Exception:
            pass  # Silent fail for auto-scan

    def _on_mouse_moved(self, pos):
        """Show tooltip with channel info on hover."""
        # Update overlay geometry in case of resize
        self.hover_overlay.setGeometry(self.plot.viewport().rect())

        # Convert scene position to view coordinates
        vb = self.plot.plotItem.vb
        if not self.plot.sceneBoundingRect().contains(pos):
            self.hover_overlay.hideAll()
            return

        mouse_point = vb.mapSceneToView(pos)
        x, y = mouse_point.x(), mouse_point.y()

        # Convert to channel and date indices
        channel_idx = int(round(x))
        date_idx = int(round(y))

        # Check bounds
        if not (0 <= channel_idx < len(self.current_channels) and 0 <= date_idx < len(self.current_dates)):
            self.hover_overlay.hideAll()
            return

        channel = self.current_channels[channel_idx]
        date_str = self.current_dates[date_idx]

        # Look up scan details
        if date_str in self.scan_details:
            networks = self.scan_details[date_str].get(channel, [])
            count = len(networks)

            # Format date nicely
            try:
                date_display = datetime.strptime(date_str, "%Y-%m-%d").strftime("%b %d")
            except ValueError:
                date_display = date_str

            # Build tooltip text
            if networks:
                network_list = "\n".join(f"  {n}" for n in networks[:8])
                if len(networks) > 8:
                    network_list += f"\n  +{len(networks) - 8} more"
                tooltip = f"Ch {channel} | {date_display} | {count} networks\n{network_list}"
            else:
                tooltip = f"Ch {channel} | {date_display}\nClear (no networks)"
        else:
            tooltip = f"Ch {channel} | No scan data"

        # Get pixel position for the label
        view_pos = self.plot.plotItem.vb.mapViewToScene(mouse_point)
        pixel_pos = self.plot.mapFromScene(view_pos)

        self.hover_overlay.setLabel(tooltip, pixel_pos.x(), pixel_pos.y())
