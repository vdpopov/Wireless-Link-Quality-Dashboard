# WiFi Link & Latency Monitor

A lightweight Linux desktop app that graphs **Wi‑Fi link quality** and **network latency** over time.

It continuously samples Wi‑Fi metrics from `iw` and runs background pings to one or more hosts so you can correlate **signal / link rate changes** with **latency spikes** and **packet loss**.

## What it shows

- **Signal strength** (dBm)
- **RX / TX bitrate** (MBit/s)
- **Channel width / bandwidth** (MHz, when available from `iw`)
- **Ping latency** per host (ms), including failure periods

## Features

- Multi-plot dashboard (Signal, Ping, RX/TX, Bandwidth)
- Time window presets: **10m / 30m / 60m / 4h / 1D / ∞**
- Adjustable refresh interval
- Pause/Resume updates
- Add/remove ping targets (IP or domain)

## Requirements

- Linux
- Python 3
- System tools:
  - `iw`
  - `ip` (iproute2)
  - `ping` (iputils)
- Python packages:
  - `PyQt5`
  - `pyqtgraph`
  - `numpy`
  - (optional) `PyOpenGL`, `PyOpenGL_accelerate` for GPU/OpenGL acceleration

## Run

From the repo root:

```bash
python wifi_monitor.py
```

Or:

```bash
python -m wifi_monitor.main
```

On startup, you’ll be prompted to choose a wireless interface.

## How it works (high level)

- Wi‑Fi metrics are parsed from:
  - `iw dev <iface> link`
- Default gateway is detected from:
  - `ip route`
- Ping latency is collected by background threads running:
  - `ping -c 1 -W 1 <host>`

## Notes / limitations

- This tool is intended for **local diagnostics** on a machine you control.
- Some Wi‑Fi drivers/APs may not report all fields (e.g., bandwidth), in which case those points will appear as gaps.

