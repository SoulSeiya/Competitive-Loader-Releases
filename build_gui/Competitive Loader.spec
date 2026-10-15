# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

PROJECT = Path(SPECPATH).parent

a = Analysis(
    [str(PROJECT / 'competitive_gui.py')],
    pathex=[str(PROJECT)],
    binaries=[],
    datas=[
        (str(PROJECT / 'payload'), 'payload'),
        (str(PROJECT / 'assets' / 'universo_tenkaichi_ui.png'), 'assets'),
        (str(PROJECT / 'assets' / 'competitive_edition_logo.png'), 'assets'),
        (str(PROJECT / 'tools' / 'ffmpeg-lite.exe'), 'tools'),
        (str(PROJECT / 'licenses' / 'FFmpeg-LGPL-2.1.txt'), 'licenses'),
        (str(PROJECT / 'licenses' / 'FFmpeg-SOURCE.txt'), 'licenses'),
    ],
    hiddenimports=['ps2_save'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='Competitive Loader',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=[str(PROJECT / 'assets' / 'universo_tenkaichi.ico')],
    version=str(PROJECT / 'assets' / 'version_info.txt'),
)
