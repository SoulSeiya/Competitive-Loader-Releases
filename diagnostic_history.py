"""Explicit bulk backfill of structured summaries, never raw historical files."""
import hashlib
import json
from pathlib import Path
import re
from diagnostic_reports import DesyncCapture

def read_summary(folder,owner):
    folder=Path(folder);meta={};lines=[]
    session=folder/'session.json'
    if session.is_file() and not session.is_symlink() and session.stat().st_size<=65536:
        try:meta=json.loads(session.read_text(encoding='utf-8-sig'))
        except (OSError,ValueError):pass
    for name in ('online.log','local.log'):
        p=folder/name
        if p.is_file() and not p.is_symlink() and p.stat().st_size<=16*1024*1024:
            lines=p.read_text(encoding='utf-8-sig',errors='replace').splitlines()
            if lines:break
    if not lines and not meta:return []
    for line in lines:
        m=re.search(r'VERSIONS loader=(\S+) decomp=(\S+) memory_sha256=([a-f0-9]{64}) payload=(\{.*\})',line)
        if m:
            try:meta.update(loader_version=m[1],decomp_release=m[2],memory_sha256=m[3],payload_sha256=json.loads(m[4]))
            except ValueError:pass
    reports=[];parser=DesyncCapture(meta,reports.append)
    for line in lines:parser.line(line)
    if not reports:
        # Closed / failed-start / crash sessions are useful too; label them, never manufacture a desync.
        reports.append(parser.report('session'))
        reports[-1]['divergence']=None
    for index,r in enumerate(reports):
        r['context']={'source':'history'}
        status=meta.get('status','unknown')
        if status not in ('preparing','running','closed','desync','crash','abnormal_exit','exit_unavailable','monitor_error','loader_closed_while_game_running'):status='unknown'
        code=meta.get('exit_code')
        if not isinstance(code,str) or not re.fullmatch(r'0x[0-9A-Fa-f]{8}',code):code=None
        r['summary']={'status':status,'exit_code':code,'online':bool(meta.get('online_observed')),'desync':r['kind']=='desync'}
        r.pop('report_id',None)
        content=json.dumps(r,sort_keys=True,separators=(',',':'))
        r['report_id']=hashlib.sha256(('history-v1:'+owner+':'+folder.name+':'+str(index)+':'+content).encode()).hexdigest()[:32]
    return reports

def history_reports(root,owner,limit=100):
    root=Path(root).resolve();folders=[]
    if not root.is_dir():return []
    for folder in root.iterdir():
        if folder.is_dir() and not folder.is_symlink() and re.fullmatch(r'\d{8}-\d{6}-[a-f0-9]{8}',folder.name) and folder.resolve().parent==root:folders.append(folder)
    out=[]
    for folder in sorted(folders,reverse=True)[:limit]:
        try:out.extend(read_summary(folder,owner))
        except (OSError,ValueError,TypeError):continue
    return out[:200]
