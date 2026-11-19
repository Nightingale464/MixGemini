# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

EXCLUDES = [
    "PySide6.QtWebEngineCore",
    "PySide6.QtWebEngineWidgets",
    "PySide6.QtQml",
    "PySide6.QtQuick",
    "PySide6.QtQuickWidgets",
    "PySide6.Qt3DCore",
    "PySide6.Qt3DRender",
    "PySide6.QtMultimedia",
    "PySide6.QtMultimediaWidgets",
    "PySide6.QtNetwork",
    "PySide6.QtOpenGL",
    "PySide6.QtOpenGLWidgets",
    "PySide6.QtPdf",
    "PySide6.QtPdfWidgets",
    "PySide6.QtCharts",
    "PySide6.QtDesigner",
    "PySide6.QtShaderTools",
    "PySide6.QtSql",
    "PySide6.QtTest",
    "PySide6.QtXml",
    "PySide6.QtDBus",
    "PySide6.QtPositioning",
    "PySide6.QtPrintSupport",
    "PySide6.QtSensors",
    "PySide6.QtSerialPort",
    "PySide6.QtStateMachine",
    "PySide6.QtWebChannel",
    "PySide6.QtWebSockets",
    "PySide6.QtHelp",
    "PySide6.QtBluetooth",
    "PySide6.QtNfc",
    "PySide6.QtLocation",
    "PySide6.QtRemoteObjects",
    "PySide6.QtScxml",
    "PySide6.QtTextToSpeech",
    "PySide6.QtSpatialAudio",
    "PySide6.QtGraphs",
    "PySide6.QtHttpServer",
    "numpy",
    "matplotlib",
    "PIL",
    "fitz",
    "pymupdf",
    "lxml",
    "google",
    "flask",
    "aiohttp",
    "httpx",
    "requests",
    "urllib3",
    "openpyxl",
    "pptx",
    "tornado",
    "zmq",
    "cryptography",
    "yaml",
    "bs4",
    "pydantic",
    "jinja2",
    "tkinter",
    "unittest",
    "pydoc",
    "doctest",
    "sqlite3",
    "xmlrpc",
    "pdb",
    "pytest",
    "IPython",
    "jupyter",
    "nbconvert",
    "nbformat",
    "scipy",
    "pandas",
    "cv2",
    "torch",
    "websockets",
    "curl_cffi",
    "jieba",
    "wordcloud",
    "edge_tts",
    "pywinstyles",
]

DROP_BINARY_PATTERNS = (
    "opengl32sw.dll",
    "d3dcompiler_47.dll",
    "qt6network.dll",
    "qt6pdf",
    "qt6qml",
    "qt6quick",
    "qt6opengl",
    "qt6dbus.dll",
    "qt6virtualkeyboard",
    "qt6shadertools",
    "qt6webengine",
    "avcodec",
    "avformat",
    "avutil",
    "swresample",
    "swscale",
    "qt6designer",
    "qt6sql",
    "qt6test",
    "qt6xml",
    "qt6printsupport",
    "qt6multimedia",
    "qt63d",
    "qt6charts",
    "qt6webchannel",
    "qt6websockets",
    "qt6positioning",
    "qt6sensors",
    "qt6serialport",
    "qt6bluetooth",
    "qt6location",
    "qt6httpserver",
    "qt6graphs",
)

DROP_QT_SUBDIRS = (
    "/translations/",
    "/qml/",
    "/plugins/tls/",
    "/plugins/networkinformation/",
    "/plugins/generic/",
    "/plugins/platforminputcontexts/",
    "/plugins/iconengines/",
    "/plugins/accessiblebridge/",
    "/plugins/multimedia/",
    "/plugins/sqldrivers/",
    "/plugins/printsupport/",
    "/plugins/position/",
    "/plugins/sensors/",
    "/plugins/geoservices/",
    "/plugins/texttospeech/",
)


def _should_keep_entry(dest_name: str) -> bool:
    norm = dest_name.replace("\\", "/").lower()
    wrapped = f"/{norm}"
    name = Path(norm).name

    for sub in DROP_QT_SUBDIRS:
        if sub in wrapped:
            return False

    if "/plugins/platforms/" in wrapped:
        return name == "qwindows.dll"

    if "/plugins/imageformats/" in wrapped:
        return name in ("qico.dll", "qsvg.dll")

    for pat in DROP_BINARY_PATTERNS:
        if pat in name:
            return False

    return True


a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=[],
    datas=[
        ("assets/mixgemini.ico", "assets"),
        ("assets/mixgemini.png", "assets"),
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=EXCLUDES,
    noarchive=False,
    optimize=0,
)

a.binaries = [entry for entry in a.binaries if _should_keep_entry(entry[0])]
a.datas = [entry for entry in a.datas if _should_keep_entry(entry[0])]

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="MixGemini",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="assets/mixgemini.ico",
)
