# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all
import os
import glob

py_datas = [(f, '.') for f in glob.glob('*.py')]

datas = [
    ('assets', 'assets'),
    ('co_core', 'co_core'),
    ('sc_core', 'sc_core'),
    ('extension', 'extension'),
    ('settings.json', '.'),
    ('version.json', '.')
] + py_datas

binaries = []
hiddenimports = [
    'pydantic',
    'pydantic_core',
    'openpyxl',
    'fitz',
    'cv2',
    'rapidocr_onnxruntime',
    'google.genai',
    'requests',
    'urllib3',
    'co_core',
    'co_core.app_co_extractor',
    'co_core.co_schema',
    'co_core.gemini_extractor',
    'co_core.local_stream_server',
    'co_core.batch_signer',
    'local_stream_server',
    'batch_signer',
    'github_updater'
]

# Collect rapidocr_onnxruntime
tmp_ret = collect_all('rapidocr_onnxruntime')
datas += tmp_ret[0]
binaries += tmp_ret[1]
hiddenimports += tmp_ret[2]

# Collect pymupdf
tmp_ret = collect_all('pymupdf')
datas += tmp_ret[0]
binaries += tmp_ret[1]
hiddenimports += tmp_ret[2]

# Excludes to keep bundle as lightweight as possible
excludes = [
    'torch', 'torchvision', 'torchaudio', 'scipy', 'matplotlib',
    'pandas', 'IPython', 'notebook', 'jupyter', 'pytest',
    'transformers', 'sklearn', 'crewai', 'selenium',
    'tkinter', 'customtkinter', 'unittest', 'pydoc', 'doctest',
    'test', 'sqlite3', 'wx', 'curses'
]

a = Analysis(
    ['app_unified_suite.py'],
    pathex=['.'],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
    optimize=1,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='XNK_eCoSys_SC',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    icon=['assets\\app_icon.ico'],
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='XNK_eCoSys_SC',
)
