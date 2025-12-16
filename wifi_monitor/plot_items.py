from datetime import datetime

import pyqtgraph as pg


class ClickableLegend(pg.LegendItem):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setAcceptHoverEvents(True)

    def addItem(self, item, name):
        super().addItem(item, name)

        if len(self.items) > 0:
            sample, label = self.items[-1]

            sample._plot_item = item
            label._plot_item = item

            sample.setAcceptHoverEvents(True)
            label.setAcceptHoverEvents(True)

            original_sample_hover_enter = (
                sample.hoverEnterEvent if hasattr(sample, "hoverEnterEvent") else None
            )
            original_sample_hover_leave = (
                sample.hoverLeaveEvent if hasattr(sample, "hoverLeaveEvent") else None
            )

            def sample_hover_enter(ev):
                from PyQt5.QtCore import Qt

                sample.setCursor(Qt.PointingHandCursor)
                if original_sample_hover_enter:
                    original_sample_hover_enter(ev)
                ev.accept()

            def sample_hover_leave(ev):
                from PyQt5.QtCore import Qt

                sample.setCursor(Qt.ArrowCursor)
                if original_sample_hover_leave:
                    original_sample_hover_leave(ev)
                ev.accept()

            sample.hoverEnterEvent = sample_hover_enter
            sample.hoverLeaveEvent = sample_hover_leave

            def label_hover_enter(ev):
                from PyQt5.QtCore import Qt

                label.setCursor(Qt.PointingHandCursor)
                ev.accept()

            def label_hover_leave(ev):
                from PyQt5.QtCore import Qt

                label.setCursor(Qt.ArrowCursor)
                ev.accept()

            label.hoverEnterEvent = label_hover_enter
            label.hoverLeaveEvent = label_hover_leave

            def sample_mouse_press(ev):
                from PyQt5.QtCore import Qt

                if ev.button() == Qt.LeftButton:
                    item.setVisible(not item.isVisible())

                    if item.isVisible():
                        sample.setOpacity(1.0)
                        label.setOpacity(1.0)
                    else:
                        sample.setOpacity(0.3)
                        label.setOpacity(0.3)

                    ev.accept()
                else:
                    ev.ignore()

            def label_mouse_press(ev):
                from PyQt5.QtCore import Qt

                if ev.button() == Qt.LeftButton:
                    item.setVisible(not item.isVisible())

                    if item.isVisible():
                        sample.setOpacity(1.0)
                        label.setOpacity(1.0)
                    else:
                        sample.setOpacity(0.3)
                        label.setOpacity(0.3)

                    ev.accept()
                else:
                    ev.ignore()

            sample.mousePressEvent = sample_mouse_press
            label.mousePressEvent = label_mouse_press

    def mousePressEvent(self, ev):
        ev.accept()

    def mouseMoveEvent(self, ev):
        ev.accept()

    def mouseReleaseEvent(self, ev):
        ev.accept()

    def mouseDragEvent(self, ev):
        ev.accept()


def setup_legend(plot, offset=(5, 5)):
    legend = ClickableLegend(offset=offset)
    legend.setParentItem(plot.getPlotItem().vb)
    legend.anchor((0, 0), (0, 0), offset=offset)

    # Detect dark mode from pyqtgraph background config
    bg = pg.getConfigOption("background")
    if isinstance(bg, tuple) and len(bg) >= 3:
        is_dark = (bg[0] + bg[1] + bg[2]) / 3 < 128
    elif bg == "k" or bg == "black":
        is_dark = True
    else:
        is_dark = False

    if is_dark:
        # Dark theme: dark legend background, light text
        legend.setBrush(pg.mkBrush(50, 50, 50, 200))
        legend.setLabelTextColor((200, 200, 200))
    else:
        # Light theme: light legend background, dark text
        legend.setBrush(pg.mkBrush(255, 255, 255, 200))
        legend.setLabelTextColor((0, 0, 0))

    legend.setPen(pg.mkPen(None))

    legend.layout.setSpacing(3)
    legend.layout.setContentsMargins(7, 5, 7, 0)

    return legend


class TimeAxisItem(pg.AxisItem):
    def tickStrings(self, values, scale, spacing):
        if len(values) < 2:
            return [datetime.fromtimestamp(v).strftime("%H:%M:%S") for v in values]

        time_span = values[-1] - values[0] if len(values) > 1 else 0

        if time_span > 86400 * 2:
            return [datetime.fromtimestamp(v).strftime("%m-%d %H:%M") for v in values]
        elif time_span > 86400:
            return [datetime.fromtimestamp(v).strftime("%d %H:%M") for v in values]
        else:
            return [datetime.fromtimestamp(v).strftime("%H:%M:%S") for v in values]
