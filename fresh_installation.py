"""First installation with the pinned bundled engine and user-owned ISO/save.

Never merge with an existing destination. Publish the runtime and config only
after extraction, save import and payload relocation have all succeeded.
"""
import json
import os
from pathlib import Path
import shutil
import tempfile

import competitive_loader as core


def install_from_iso(iso, destination, memory=None, report=None):
    iso=Path(iso).resolve();target=Path(destination).resolve()
    memory=Path(memory).resolve() if memory else None
    parent=target.parent
    def status(stage,text):
        if report:report(stage,text)
    if not iso.is_file():raise core.LoaderError('Selecciona una ISO competitiva existente.')
    if memory and not memory.is_file():raise core.LoaderError('La memory seleccionada no existe.')
    if target.exists():raise core.LoaderError('La carpeta de destino ya existe. Elige otra carpeta para conservar la instalación anterior.')
    if not parent.is_dir():raise core.LoaderError('La carpeta elegida no existe.')
    if core._is_game_running():raise core.LoaderError('Cierra Tenkaichi3Decomp antes de instalar.')
    engine=core.RESOURCE_ROOT/'engine'
    if core.sha256_file(engine/'Tenkaichi3Decomp.exe')!=core.BTC_1381_HASH:
        raise core.LoaderError('El motor incluido no coincide con la versión BTC revisada.')
    # AFS extraction temporarily holds both the archives and their split files.
    required=iso.stat().st_size*2+(1<<30)
    if shutil.disk_usage(parent).free<required:
        raise core.LoaderError(f'Necesitas aproximadamente {required/(1<<30):.1f} GB libres para preparar esta ISO.')
    staging=Path(tempfile.mkdtemp(prefix='.btc-install-',dir=parent)).resolve()
    published=False;config_temp=None
    try:
        status('engine','Preparando el motor BTC incluido (0.1.38.1).')
        shutil.copytree(engine,staging,dirs_exist_ok=True)
        status('extract','Comprobando y extrayendo tu ISO competitiva.')
        slus,dbzp=core._extract_competitive_iso(iso,staging/'gamedata',report=lambda text:status('extract',text))
        status('intro','Preparando la intro compatible.')
        core.ensure_intro_compatible(staging)
        status('memory','Importando y comprobando la memory.' if memory else 'Sin memory: podrás importarla después desde Ajustes para online.')
        fingerprint=core.import_ps2_card(memory,staging,persist_config=False) if memory else None
        status('validate','Validando los datos competitivos y los parches del juego.')
        core.patch_dat(staging/'Tenkaichi3Decomp.dat',slus,dbzp)
        image=core.validate_payload(core.PAYLOAD,staging/'Tenkaichi3Decomp.exe')
        image.build(0x60000000,image.pe.preferred_base)
        (staging/'INICIAR CON RISING BATTLE.txt').write_text('Inicia este juego con Competitive Loader.exe. No abras directamente el decomp.\n',encoding='utf-8')
        state=dict(core.load_config())
        state.update(runtime=str(target),iso=str(iso),exe_sha256=core.BTC_1381_HASH,release_source='bundled-btc-0.1.38.1')
        state.pop('online_memory_sha256',None)
        if fingerprint:state['online_memory_sha256']=fingerprint
        # Write configuration beside its destination so the final replace is atomic.
        fd,name=tempfile.mkstemp(prefix='.btc-config-',suffix='.tmp',dir=core.CONFIG.parent)
        config_temp=Path(name)
        with os.fdopen(fd,'w',encoding='utf-8') as f:json.dump(state,f,ensure_ascii=False,indent=2)
        status('publish','Guardando la instalación verificada.')
        os.rename(staging,target);published=True
        os.replace(config_temp,core.CONFIG);config_temp=None
        return {'runtime':str(target),'memory_ready':bool(fingerprint),'engine_sha256':core.BTC_1381_HASH}
    finally:
        if config_temp:config_temp.unlink(missing_ok=True)
        # These are only the directories created by this operation. Never delete
        # the user's parent, source files or an already-existing installation.
        if staging.exists() and staging.parent==parent and staging.name.startswith('.btc-install-'):
            shutil.rmtree(staging)
        if published and config_temp is not None and target.parent==parent:
            shutil.rmtree(target)
