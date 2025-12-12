from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QHBoxLayout, QLabel, QLineEdit, QPushButton


def build_ping_bar(window, parent_layout):
    """Builds the ping host bar and attaches widgets to `window`."""

    ping_bar = QHBoxLayout()
    ping_bar.addWidget(QLabel("Ping:"))

    window.ping_labels_layout = QHBoxLayout()
    ping_bar.addLayout(window.ping_labels_layout)
    ping_bar.addStretch()

    window.host_entry = QLineEdit()
    window.host_entry.setPlaceholderText("type IP or domain")
    window.host_entry.setFixedWidth(150)
    window.host_entry.returnPressed.connect(window.add_host)
    ping_bar.addWidget(window.host_entry)

    add_btn = QPushButton("Add")
    add_btn.clicked.connect(window.add_host)
    ping_bar.addWidget(add_btn)

    parent_layout.addLayout(ping_bar)


def refresh_ping_host_buttons(window):
    from .. import constants
    from ..constants import PING_COLORS

    while window.ping_labels_layout.count():
        item = window.ping_labels_layout.takeAt(0)
        if item.widget():
            item.widget().deleteLater()

    for i, host_info in enumerate(constants.ping_hosts):
        color = PING_COLORS[i % len(PING_COLORS)]
        display = (
            f"{host_info['label']} ({host_info['host']})"
            if host_info["label"] != host_info["host"]
            else host_info["host"]
        )
        btn = QPushButton(f"✕ {display}")
        btn.setStyleSheet(f"color: {color}; border: none; text-align: left;")
        btn.setCursor(Qt.PointingHandCursor)
        btn.clicked.connect(lambda checked, idx=i: window.remove_host(idx))
        window.ping_labels_layout.addWidget(btn)
