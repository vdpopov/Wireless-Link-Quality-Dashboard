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


def configure_pyqtgraph():
    pg.setConfigOptions(antialias=True)
    pg.setConfigOption("background", "w")
    pg.setConfigOption("foreground", "k")

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
