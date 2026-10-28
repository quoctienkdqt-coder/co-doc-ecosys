# -*- mode: python ; coding: utf-8 -*-
datas = [
    ('installer/app_bundle.zip', '.'),
    ('assets', 'assets')
]
binaries = []
hiddenimports = [
    'win32com',
    'win32com.client',
    'win32com.shell',
    'win32com.shell.shell',
    'win32com.shell.shellcon',
    'pythoncom',
    'pywintypes'
]

excludes = [
    'torch', 'scipy', 'pandas', 'matplotlib', 'pymupdf', 'rapidocr_onnxruntime',
    'cv2', 'openpyxl', 'google', 'tkinter', 'customtkinter', 'unittest'
]

a = Analysis(
    ['installer\\setup_wizard.py'],
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
    a.binaries,
    a.datas,
    [],
    name='CaiDat_XNK_eCoSys_SC_v3.1',
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
    icon=['assets\\app_icon.ico'],
)
