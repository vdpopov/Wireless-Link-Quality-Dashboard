from PyQt5.QtWidgets import QComboBox, QDialog, QDialogButtonBox, QLabel, QVBoxLayout


class InterfaceDialog(QDialog):
    def __init__(self, interfaces):
        super().__init__()
        self.setWindowTitle("WiFi Monitor")
        self.setFixedSize(300, 150)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Select wireless interface:"))

        self.combo = QComboBox()
        self.combo.addItems(interfaces)
        layout.addWidget(self.combo)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)

    def get_interface(self):
        return self.combo.currentText()
