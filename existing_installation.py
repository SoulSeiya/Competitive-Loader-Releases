"""Locate an existing generated runtime without moving ISO or game files."""
from pathlib import Path

def find_installation(folder):
    root=Path(folder).expanduser().resolve()
    if not root.is_dir():raise ValueError('Selecciona una carpeta existente')
    for candidate in (root,root/'CompetitiveRuntime'):
        if all((candidate/f).is_file() for f in ('Tenkaichi3Decomp.exe','Tenkaichi3Decomp.exe.mem','Tenkaichi3Decomp.dat','SDL3.dll')) and (candidate/'gamedata').is_dir():
            return candidate
    raise ValueError('No se encontró la instalación generada. Selecciona la carpeta del Loader que contiene CompetitiveRuntime, o directamente CompetitiveRuntime. La ISO por sí sola todavía necesita prepararse.')
