"""Prepare the private BTC engine beside this Loader; never replace the source installation."""
from pathlib import Path
import os
import shutil
import tempfile
import competitive_loader as core
from existing_installation import find_installation


def prepare_existing(folder, destination_parent=None):
    source=find_installation(folder)
    if core.sha256_file(source/'Tenkaichi3Decomp.exe') == core.BTC_1381_HASH:
        core.validate_payload(core.PAYLOAD,source/'Tenkaichi3Decomp.exe')
        return source
    engine=core.RESOURCE_ROOT/'engine'
    if core.sha256_file(engine/'Tenkaichi3Decomp.exe') != core.BTC_1381_HASH:
        raise core.LoaderError('El motor BTC incluido no coincide con la versión de prueba.')
    parent=Path(destination_parent or core.HERE).resolve()
    target=Path(tempfile.mkdtemp(prefix='CompetitiveRuntime-1381-',dir=parent))
    try:
        shutil.copytree(engine,target,dirs_exist_ok=True)
        def immutable_game_file(src,dst):
            # BIN assets are only read by the engine. Other files (caches, videos,
            # markers and configuration) have independent copies.
            if Path(src).suffix.lower()=='.bin':
                try:os.link(src,dst);return dst
                except OSError:pass
            return shutil.copy2(src,dst)
        print('[BTC] Preparando los datos generados en una carpeta de prueba...')
        shutil.copytree(source/'gamedata',target/'gamedata',copy_function=immutable_game_file)
        for name in ('saves','textures','songs','stages'):
            if (source/name).is_dir():shutil.copytree(source/name,target/name,dirs_exist_ok=True)
        for name in ('fonts','translations'):
            if (source/name).is_dir():
                for f in (source/name).rglob('*'):
                    dest=target/name/f.relative_to(source/name)
                    if f.is_file() and not dest.exists():
                        dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(f,dest)
        # Settings belong to this copy. Do not import logs, tokens or user profiles.
        for f in source.glob('*.ini'):shutil.copy2(f,target/f.name)
        for f in source.glob('*.cfg'):shutil.copy2(f,target/f.name)
        core.patch_dat(target/'Tenkaichi3Decomp.dat',target/'gamedata/disc/SLUS_216.78',target/'gamedata/disc/BIN/DBZP.BIN')
        image=core.validate_payload(core.PAYLOAD,target/'Tenkaichi3Decomp.exe')
        image.build(0x60000000,image.pe.preferred_base)
        (target/'INICIAR CON RISING BATTLE.txt').write_text('Inicia esta instalación con el Loader BTC de prueba que la preparó.\nAmbos jugadores necesitan la misma versión.\n',encoding='utf-8')
        print('[BTC] Instalación de prueba preparada:',target)
        return target
    except Exception:
        if target.resolve().parent == parent and target.name.startswith('CompetitiveRuntime-1381-'):
            shutil.rmtree(target)
        raise
