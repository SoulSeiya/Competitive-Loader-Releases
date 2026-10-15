"""Package only explicit public files; never copy a runtime, config or logs to friends."""
import argparse
import json
from pathlib import Path
import shutil
import zipfile

ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--host-folder',type=Path,required=True)
    parser.add_argument('--cloudflared',type=Path,required=True)
    parser.add_argument('--cloudflared-license',type=Path,required=True)
    parser.add_argument('--host-runtime',type=Path)
    parser.add_argument('--four-player',action='store_true')
    args=parser.parse_args()
    public=[(ROOT/'dist/Competitive Loader.exe','Competitive Loader.exe'),
            (ROOT/'README.txt','README.txt'),(ROOT/'RISING-BATTLE.md','RISING-BATTLE.md'),
            (ROOT/'service/PRUEBA-CON-AMIGOS.txt','LEEME - prueba con amigos.txt')]
    public.extend((p,'licenses/'+p.name) for p in (ROOT/'licenses').iterdir() if p.is_file())
    for source,_ in public:
        if not source.is_file():raise FileNotFoundError(source)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(args.output,'w',zipfile.ZIP_DEFLATED) as archive:
        for source,name in public:archive.write(source,'BTC-Prueba-Amigos/'+name)
    host=args.host_folder
    host.mkdir(parents=True,exist_ok=True)
    for source,name in public:
        target=host/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target)
    shutil.copy2(args.cloudflared,host/'cloudflared.exe')
    shutil.copy2(args.cloudflared_license,host/'licenses/cloudflared-APACHE-2.0.txt')
    host_mode='--four-player-room-test-host' if args.four_player else '--room-test-host'
    (host/'Iniciar servidor de prueba.cmd').write_text('@echo off\nstart "" "%~dp0Competitive Loader.exe" '+host_mode+'\n',encoding='ascii')
    config=host/'competitive_loader.json'
    if args.host_runtime and not config.exists():
        config.write_text(json.dumps({'runtime':str(args.host_runtime.resolve())},indent=2),encoding='utf-8')
    print('ZIP para el amigo:',args.output.resolve())
    print('Carpeta exclusiva del anfitrion:',host.resolve())


if __name__=='__main__':main()
