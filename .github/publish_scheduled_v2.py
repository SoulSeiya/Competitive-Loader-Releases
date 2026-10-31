"""Publish only the reviewed draft, after the authorized date. No stored secrets."""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import subprocess
import tempfile
from datetime import datetime, timezone
import urllib.request
import zipfile


class SafeRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        from urllib.parse import urlsplit
        target=urlsplit(newurl)
        if target.scheme!='https' or not (target.hostname or '').endswith('.githubusercontent.com'):
            raise RuntimeError('Unexpected asset redirect')
        result=super().redirect_request(req,fp,code,msg,headers,newurl)
        result.remove_header('Authorization')
        return result


def main():
    root=Path.cwd();cfg=json.loads((root/'.github/rising-battle-release.json').read_text())
    now=datetime.now(timezone.utc)
    requested=os.environ.get('GITHUB_EVENT_NAME')=='schedule' or os.environ.get('INPUT_PUBLISH')=='true'
    due=datetime.fromisoformat(cfg['publish_at'])
    expired=now>datetime.fromisoformat(cfg['expires_at'])
    authorized=requested and now>=due and not expired
    token=os.environ['GH_TOKEN'];base='https://api.github.com/repos/'+cfg['repository']
    opener=urllib.request.build_opener(SafeRedirect())
    def api(path,method='GET',data=None,binary=False):
        headers={'Authorization':'Bearer '+token,'Accept':'application/octet-stream' if binary else 'application/vnd.github+json','User-Agent':'RisingBattle-Scheduled-Release','X-GitHub-Api-Version':'2022-11-28'}
        body=json.dumps(data).encode() if data is not None else None
        if body:headers['Content-Type']='application/json'
        req=urllib.request.Request(base+path,data=body,method=method,headers=headers)
        with opener.open(req,timeout=180) as response:raw=response.read()
        return raw if binary else json.loads(raw)
    release=api('/releases/'+str(cfg['release_id']))
    if not release['draft']:
        assert release['tag_name']==cfg['tag']
        print('Release already published; no changes made.');return
    assert not release['prerelease']
    assets={a['name']:a for a in api('/releases/'+str(cfg['release_id'])+'/assets')}
    for name,expected in cfg['assets'].items():
        actual=assets[name]
        assert actual['id']==expected['id'] and actual['size']==expected['size']
        assert actual.get('digest')=='sha256:'+expected['sha256']
    source=cfg['assets']['RisingBattle-v2.0.0-source.zip']
    raw=api('/releases/assets/'+str(source['id']),binary=True)
    assert hashlib.sha256(raw).hexdigest()==source['sha256']
    with tempfile.TemporaryDirectory(prefix='rising-release-') as folder:
        archive=Path(folder)/'source.zip';archive.write_bytes(raw)
        with zipfile.ZipFile(archive) as z:
            assert z.testzip() is None
            for entry in z.infolist():
                p=PurePosixPath(entry.filename)
                assert not p.is_absolute() and '..' not in p.parts and '\\' not in entry.filename
                assert p.parts[0] not in ('.git','.github')
                assert p.suffix.lower() not in ('.iso','.ps2','.sqlite3','.log')
                assert (entry.external_attr>>16)&0o170000!=0o120000
            manifest=json.loads(z.read('SOURCE-MANIFEST.json'))
            assert set(z.namelist())==set(manifest)|{'SOURCE-MANIFEST.json'}
            for name,digest in manifest.items():assert hashlib.sha256(z.read(name)).hexdigest()==digest
            if not authorized:
                print('DRY RUN OK: draft and source verified; publication time not reached or publish not requested.');return
            # Preserve repository automation; replace only the reviewed application tree.
            tracked=subprocess.check_output(['git','ls-files','-z']).decode().split('\0')
            remove=[p for p in tracked if p and p not in manifest and p!='SOURCE-MANIFEST.json' and not p.startswith('.github/') and p not in ('.gitignore','LICENSE','LICENSE-MIT')]
            for offset in range(0,len(remove),100):subprocess.run(['git','rm','--ignore-unmatch','--',*remove[offset:offset+100]],check=True,stdout=subprocess.DEVNULL)
            z.extractall(root)
        subprocess.run(['git','config','user.name','github-actions[bot]'],check=True)
        subprocess.run(['git','config','user.email','41898282+github-actions[bot]@users.noreply.github.com'],check=True)
        subprocess.run(['git','add','--all'],check=True)
        if subprocess.run(['git','diff','--cached','--quiet']).returncode:
            subprocess.run(['git','commit','-m','Release Rising Battle 2.0.0 beta client'],check=True,stdout=subprocess.DEVNULL)
            subprocess.run(['git','push','origin','HEAD:main'],check=True)
        sha=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
        public=api('/releases/'+str(cfg['release_id']),'PATCH',{'tag_name':cfg['tag'],'target_commitish':sha,'draft':False,'prerelease':False,'make_latest':'true'})
        assert not public['draft'] and public['tag_name']==cfg['tag']
        latest=api('/releases/latest');assert latest['id']==cfg['release_id']
        print('PUBLISHED '+public['html_url'])


if __name__=='__main__':main()
