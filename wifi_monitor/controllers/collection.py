import time

import numpy as np

from .. import constants
from ..net import get_default_gateway, get_link_info
from ..ping import ping_lock


def collect_data(window):
    """Collect one datapoint and append into constants.* arrays.

    `window` is the WifiMonitor instance (used for refresh_host_list callback).
    """

    from .. import ping

    current_time = time.time()
    signal, rx, tx, bw = get_link_info()

    constants.time_data = np.append(constants.time_data, current_time)
    constants.signal_data = np.append(
        constants.signal_data, signal if signal is not None else np.nan
    )
    constants.signal_failed = np.append(constants.signal_failed, signal is None)

    constants.rx_rate_data = np.append(constants.rx_rate_data, rx if rx is not None else np.nan)
    constants.tx_rate_data = np.append(constants.tx_rate_data, tx if tx is not None else np.nan)
    constants.rates_failed = np.append(constants.rates_failed, rx is None and tx is None)

    constants.bandwidth_data = np.append(
        constants.bandwidth_data, bw if bw is not None else np.nan
    )
    constants.bandwidth_failed = np.append(constants.bandwidth_failed, bw is None)

    if len(constants.time_data) % 5 == 0:
        new_gateway = get_default_gateway()
        if ping.gateway_host_info and new_gateway and new_gateway != ping.gateway_host_info["host"]:
            ping.gateway_host_info["host"] = new_gateway
            window.refresh_host_list()
        elif not ping.gateway_host_info and new_gateway and not ping.gateway_removed_by_user:
            from ..ping import add_ping_host

            ping.gateway_host_info = add_ping_host(new_gateway, "gateway")
            constants.ping_hosts.remove(ping.gateway_host_info)
            constants.ping_hosts.insert(0, ping.gateway_host_info)
            window.refresh_host_list()

    with ping_lock:
        for host_info in constants.ping_hosts:
            val = host_info["latest"] if host_info["enabled"] else None
            host_info["data"] = np.append(host_info["data"], val if val is not None else np.nan)
            host_info["failed"] = np.append(host_info["failed"], val is None)
