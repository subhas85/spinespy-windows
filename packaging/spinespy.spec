# PyInstaller spec — onedir, windowed (no console).
# Paths are anchored to SPECPATH (the packaging/ dir) so the build works
# regardless of the working directory pyinstaller is invoked from.
import os

from PyInstaller.utils.hooks import collect_all

ROOT = os.path.abspath(os.path.join(SPECPATH, os.pardir))

datas = [(os.path.join(ROOT, "assets"), "assets")]
binaries = []
hiddenimports = ["pystray._win32"]
for pkg in ("mediapipe", "cv2"):
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hiddenimports += h

a = Analysis(
    [os.path.join(ROOT, "spinespy_win", "main.py")],
    pathex=[ROOT],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="SpineSpy",
    console=False,
    icon=None,
)
coll = COLLECT(exe, a.binaries, a.datas, name="SpineSpy")
