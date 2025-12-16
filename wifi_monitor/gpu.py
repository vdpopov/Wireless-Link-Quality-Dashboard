import subprocess
import sys

import pyqtgraph as pg

try:
    from OpenGL import GL  # noqa: F401

    OPENGL_AVAILABLE = True
except ImportError:
    OPENGL_AVAILABLE = False


def detect_gpu_capability():
    if not OPENGL_AVAILABLE:
        return False, "None", "PyOpenGL not installed (pip install PyOpenGL)"

    try:
        from PyQt5.QtGui import QSurfaceFormat

        fmt = QSurfaceFormat.defaultFormat()
        if fmt.majorVersion() < 2:
            return False, "None", "OpenGL version too old (< 2.0)"

        gpu_name = "Unknown GPU"

        if sys.platform.startswith("linux"):
            try:
                result = subprocess.check_output(["lspci"], text=True)
                for line in result.split("\n"):
                    if "VGA" in line or "Display" in line or "3D" in line:
                        gpu_name = line.split(": ")[-1].strip()
                        break
            except Exception:
                pass

        if sys.platform.startswith("linux"):
            try:
                result = subprocess.check_output(
                    ["glxinfo"], text=True, stderr=subprocess.DEVNULL
                )
                for line in result.split("\n"):
                    if "OpenGL renderer" in line:
                        gpu_name = line.split(":")[-1].strip()
                        break
            except Exception:
                pass

        return True, gpu_name, "OpenGL available"

    except Exception as e:
        return False, "None", f"OpenGL test failed: {str(e)}"


def _detect_dark_mode():
    """Detect if system is using dark mode."""
    import os

    # Method 1: Check GTK_THEME environment variable
    gtk_theme = os.environ.get("GTK_THEME", "").lower()
    if "dark" in gtk_theme:
        return True

    # Method 2: Check GNOME/GTK settings via gsettings
    try:
        result = subprocess.run(
            ["gsettings", "get", "org.gnome.desktop.interface", "color-scheme"],
            capture_output=True, text=True, timeout=2
        )
        if "dark" in result.stdout.lower():
            return True
    except Exception:
        pass

    # Method 3: Check GTK theme name
    try:
        result = subprocess.run(
            ["gsettings", "get", "org.gnome.desktop.interface", "gtk-theme"],
            capture_output=True, text=True, timeout=2
        )
        if "dark" in result.stdout.lower():
            return True
    except Exception:
        pass

    # Method 4: Check Qt palette (works well for KDE)
    from PyQt5.QtWidgets import QApplication
    from PyQt5.QtGui import QPalette
    app = QApplication.instance()
    if app:
        palette = app.palette()
        bg_lightness = palette.color(QPalette.Window).lightness()
        if bg_lightness < 128:
            return True

    return False


def configure_pyqtgraph(force_no_gpu: bool = False, dark_mode: bool = None):
    pg.setConfigOptions(antialias=True)

    # Auto-detect dark mode from system if not specified
    if dark_mode is None:
        dark_mode = _detect_dark_mode()

    if dark_mode:
        pg.setConfigOption("background", (30, 30, 30))
        pg.setConfigOption("foreground", (200, 200, 200))
    else:
        pg.setConfigOption("background", "w")
        pg.setConfigOption("foreground", "k")

    if force_no_gpu:
        has_gpu, gpu_name, gpu_reason = False, "None", "disabled by --no-gpu"
    else:
        has_gpu, gpu_name, gpu_reason = detect_gpu_capability()

    if has_gpu:
        print(f"✅ GPU detected: {gpu_name}")
        print("🚀 Enabling OpenGL acceleration...")
        pg.setConfigOption("useOpenGL", True)
        pg.setConfigOption("enableExperimental", True)
        antialias_default = True
    else:
        print(f"⚠  No GPU acceleration: {gpu_reason}")
        print("💡 For better performance, install: pip install PyOpenGL PyOpenGL_accelerate")
        antialias_default = False

    print(f"📊 Antialiasing: {'ON' if antialias_default else 'OFF'}")
    print("")

    return antialias_default
