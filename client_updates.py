"""Loader-only release policy. This module never consults or updates the engine."""
import competitive_loader as core
import json
import time
import urllib.request


def classify_release(info, installed=None):
    installed = core.APP_VERSION if installed is None else installed
    if info['version'] <= installed:
        return 'current'
    return 'available' if info.get('download_url') else 'missing_asset'


def note_pages(notes, limit=620):
    text = str(notes or 'Esta publicación no incluye notas de cambios.').strip()
    pages = []
    while text:
        end = min(limit, len(text))
        if end < len(text):
            split = text.rfind('\n', 0, end)
            if split < limit // 2:
                split = text.rfind(' ', 0, end)
            if split > 0:
                end = split
        pages.append(text[:end].strip())
        text = text[end:].strip()
    return pages or ['Sin notas de cambios.']


def release_history(latest):
    """Bounded public history; keep cached notes available on rate limits/offline."""
    path=core.HERE/'.loader-news-cache.json'
    try:
        saved=json.loads(path.read_text(encoding='utf-8'))
    except (OSError,ValueError):saved={}
    if not isinstance(saved,dict):saved={}
    from github_releases import number
    try:cooldown=json.loads(core.GITHUB_RELEASE_CACHE.read_text(encoding='utf-8'))
    except (OSError,ValueError):cooldown={}
    cooling=isinstance(cooldown,dict) and time.time()<number(cooldown.get('api_retry_at'))
    if cooling or 0<=time.time()-number(saved.get('at'))<300:
        rows=saved.get('rows',[])
    else:
        try:
            request=urllib.request.Request('https://api.github.com/repos/SoulSeiya/Competitive-Loader-Releases/releases?per_page=10',headers={'User-Agent':'Competitive-Loader','Accept':'application/vnd.github+json'})
            with urllib.request.urlopen(request,timeout=8) as response:
                data=response.read(1024*1024+1)
            if len(data)>1024*1024:raise ValueError('Historial demasiado grande')
            values=json.loads(data)
            if not isinstance(values,list):raise ValueError('Historial no válido')
            rows=[{'tag':r['tag_name'],'name':r.get('name') or r['tag_name'],'notes':str(r.get('body') or '')[:12000]} for r in values if isinstance(r,dict) and r.get('tag_name') and not r.get('draft') and not r.get('prerelease')][:10]
            temp=path.with_suffix('.tmp')
            temp.write_text(json.dumps({'at':time.time(),'rows':rows}),encoding='utf-8');temp.replace(path)
        except (OSError,ValueError):rows=saved.get('rows',[])
    current={'tag':latest['tag'],'name':latest.get('name') or latest['tag'],'notes':latest.get('notes','')}
    return [current]+[r for r in rows if isinstance(r,dict) and r.get('tag') and r['tag']!=latest['tag']][:9]
