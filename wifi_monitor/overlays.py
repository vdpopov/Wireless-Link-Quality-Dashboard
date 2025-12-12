from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QWidget


class SelectionOverlay(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.left_x = 0
        self.right_x = 0
        self.top_y = 0
        self.bottom_y = 0

    def setSelection(self, left_x, right_x, top_y, bottom_y):
        self.left_x = left_x
        self.right_x = right_x
        self.top_y = top_y
        self.bottom_y = bottom_y
        self.update()

    def paintEvent(self, event):
        from PyQt5.QtGui import QColor, QPainter

        painter = QPainter(self)
        painter.fillRect(
            int(self.left_x),
            int(self.top_y),
            int(self.right_x - self.left_x),
            int(self.bottom_y - self.top_y),
            QColor(100, 100, 255, 50),
        )


class FailureOverlay(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.regions = []

    def setRegions(self, regions):
        self.regions = regions
        self.update()

    def paintEvent(self, event):
        from PyQt5.QtGui import QColor, QPainter

        painter = QPainter(self)
        color = QColor(255, 0, 0, 60)
        for left_x, right_x in self.regions:
            painter.fillRect(int(left_x), 0, int(right_x - left_x), self.height(), color)


class HoverOverlay(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.crosshair_x = None
        self.label_text = None
        self.label_x = 0
        self.label_y = 0

    def setCrosshair(self, x):
        self.crosshair_x = x
        self.update()

    def setLabel(self, text, x, y):
        self.label_text = text
        self.label_x = x
        self.label_y = y
        self.update()

    def hideAll(self):
        self.crosshair_x = None
        self.label_text = None
        self.update()

    def paintEvent(self, event):
        from PyQt5.QtGui import QColor, QFont, QFontMetrics, QPainter, QPen

        painter = QPainter(self)

        if self.crosshair_x is not None:
            pen = QPen(QColor(136, 136, 136), 1, Qt.DashLine)
            painter.setPen(pen)
            painter.drawLine(int(self.crosshair_x), 0, int(self.crosshair_x), self.height())

        if self.label_text:
            font = QFont()
            font.setPointSize(9)
            painter.setFont(font)
            fm = QFontMetrics(font)

            lines = self.label_text.split("\n")
            line_height = fm.height()
            max_width = max(fm.horizontalAdvance(line) for line in lines)
            total_height = line_height * len(lines)

            padding = 4
            box_width = max_width + padding * 2
            box_height = total_height + padding * 2

            label_x = self.label_x + 10
            label_y = self.label_y - box_height

            if label_x + box_width > self.width():
                label_x = self.label_x - box_width - 10
            if label_y < 0:
                label_y = self.label_y + 10

            painter.fillRect(
                int(label_x),
                int(label_y),
                int(box_width),
                int(box_height),
                QColor(255, 255, 200, 240),
            )

            painter.setPen(QColor(0, 0, 0))
            for i, line in enumerate(lines):
                painter.drawText(
                    int(label_x + padding),
                    int(label_y + padding + (i + 1) * line_height - fm.descent()),
                    line,
                )
