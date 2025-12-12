import argparse
import sys

from PyQt5.QtWidgets import QApplication

from . import constants
from .data import generate_test_data
from .gpu import configure_pyqtgraph
from .net import get_default_gateway, get_wireless_interfaces
from .ping import add_ping_host
from .ui import InterfaceDialog
from .windows.main_window import WifiMonitor


def main(argv=None):
    parser = argparse.ArgumentParser(add_help=True)
    parser.add_argument(
        "--test-data",
        metavar="DURATION",
        help='Generate synthetic history (e.g. "20m", "4h", "1d").',
    )
    parser.add_argument(
        "--no-gpu",
        action="store_true",
        help="Disable OpenGL/GPU acceleration (force CPU rendering).",
    )
    args, qt_args = parser.parse_known_args(argv if argv is not None else sys.argv[1:])

    antialias_default = configure_pyqtgraph(force_no_gpu=args.no_gpu)

    app = QApplication([sys.argv[0], *qt_args])

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

    if args.test_data:
        generate_test_data(args.test_data)

    window = WifiMonitor(antialias_default=antialias_default)
    window.show()

    def cleanup():
        from . import ping

        ping.ping_threads_running = False

    app.aboutToQuit.connect(cleanup)
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
