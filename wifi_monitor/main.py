import sys

from PyQt5.QtWidgets import QApplication

from . import constants
from .windows.main_window import WifiMonitor
from .gpu import configure_pyqtgraph
from .net import get_default_gateway, get_wireless_interfaces
from .ping import add_ping_host
from .ui import InterfaceDialog


def main():
    antialias_default = configure_pyqtgraph()

    app = QApplication(sys.argv)

    interfaces = get_wireless_interfaces()
    if not interfaces:
        print("No wireless interfaces found!")
        sys.exit(1)

    dialog = InterfaceDialog(interfaces)
    if dialog.exec_() != dialog.Accepted:
        sys.exit(0)
    constants.INTERFACE = dialog.get_interface()

    gateway = get_default_gateway()
    if gateway:
        from . import ping

        ping.gateway_host_info = add_ping_host(gateway, "gateway")
    add_ping_host("1.1.1.1", "internet")

    window = WifiMonitor(antialias_default=antialias_default)
    window.show()

    def cleanup():
        from . import ping

        ping.ping_threads_running = False

    app.aboutToQuit.connect(cleanup)
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
