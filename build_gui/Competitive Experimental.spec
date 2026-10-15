from pathlib import Path
PROJECT = Path(SPECPATH).parent
a = Analysis([str(PROJECT / 'competitive_experimental_gui.py')], pathex=[str(PROJECT)],
    binaries=[], datas=[(str(PROJECT / 'payload'), 'payload'), (str(PROJECT / 'assets'), 'assets')],
    hiddenimports=['ps2_save'], hookspath=[], hooksconfig={}, runtime_hooks=[], excludes=[], noarchive=False, optimize=0)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], name='Competitive Loader Experimental',
    debug=False, bootloader_ignore_signals=False, strip=False, upx=True, console=False,
    disable_windowed_traceback=False, icon=[str(PROJECT / 'assets' / 'universo_tenkaichi.ico')])
