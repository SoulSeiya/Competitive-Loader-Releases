"""Local identity and confirmed room history, shared across private Loader builds.

This is not server authentication or a public ranking. No room tokens are stored.
"""
from datetime import datetime, timezone
from contextlib import contextmanager
import os
import json
from pathlib import Path
import sqlite3
import uuid


class ProfileStore:
    def __init__(self,path=None,initial_name='Jugador'):
        self.path=Path(path) if path else Path(os.environ.get('LOCALAPPDATA',Path.home()/'AppData'/'Local'))/'RisingBattle'/'profile.sqlite3'
        self.path.parent.mkdir(parents=True,exist_ok=True)
        with self.connect() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS profile (id TEXT PRIMARY KEY,name TEXT NOT NULL);
                CREATE UNIQUE INDEX IF NOT EXISTS one_profile ON profile ((1));
                CREATE TABLE IF NOT EXISTS participation (
                    profile_id TEXT, tournament_id TEXT, title TEXT, status TEXT, created TEXT,
                    PRIMARY KEY(profile_id,tournament_id));
                CREATE TABLE IF NOT EXISTS matches (
                    profile_id TEXT,battle_id TEXT,match_id INTEGER,kind TEXT,opponent TEXT,
                    mine INTEGER,theirs INTEGER,won INTEGER,ft INTEGER,seconds INTEGER,characters INTEGER,finished TEXT,
                    PRIMARY KEY(profile_id,battle_id,match_id));
            ''')
            existed=bool(db.execute('SELECT id FROM profile').fetchone())
            db.execute('CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value BLOB)')
            if not existed:
                initial_name=''.join(c for c in initial_name if ord(c)>=32 and ord(c)!=127).strip().encode('utf-8')[:16].decode('utf-8','ignore') or 'Jugador'
                db.execute('INSERT OR IGNORE INTO profile VALUES (?,?)',(uuid.uuid4().hex,initial_name))
            db.execute("INSERT OR IGNORE INTO settings VALUES('btc_profile_ready',?)",(b'1' if existed or initial_name!='Jugador' else b'0',))

    @contextmanager
    def connect(self):
        db=sqlite3.connect(self.path,timeout=5);db.row_factory=sqlite3.Row
        try:
            with db:yield db
        finally:db.close()

    def profile(self):
        with self.connect() as db:return dict(db.execute('SELECT * FROM profile LIMIT 1').fetchone())

    def rename(self,name):
        name=name.strip()
        if not name or any(ord(c)<32 or ord(c)==127 for c in name) or len(name.encode('utf-8'))>16:
            raise ValueError('Usa un nombre de hasta 16 bytes UTF-8, sin saltos de línea.')
        with self.connect() as db:db.execute('UPDATE profile SET name=?',(name,))

    def identity_state(self):
        with self.connect() as db:
            rows={r['key']:bytes(r['value']) for r in db.execute("SELECT * FROM settings WHERE key IN ('btc_profile_ready','btc_linked_identity')")}
        return {'ready':rows.get('btc_profile_ready')==b'1',
                'challonge':json.loads(rows['btc_linked_identity']) if rows.get('btc_linked_identity') else None}

    def complete_profile(self,name):
        if self.identity_state()['challonge']:raise ValueError('Desvincula Challonge antes de cambiar tu nombre local.')
        self.rename(name)
        with self.connect() as db:db.execute("INSERT OR REPLACE INTO settings VALUES('btc_profile_ready',?)",(b'1',))

    def link_identity(self,identity,avatar=None):
        # Keep the local UUID and every social/ranked key unchanged.
        name=str(identity['username']).strip().encode('utf-8')[:16].decode('utf-8','ignore')
        if not name or any(ord(c)<32 or ord(c)==127 for c in name):raise ValueError('Nombre de Challonge no válido.')
        target=self.avatar_path()
        import tempfile
        with tempfile.TemporaryDirectory(prefix='btc-profile-') as folder:
            image=None
            if avatar:
                from avatar_image import convert_avatar
                source=Path(folder)/'source';source.write_bytes(avatar)
                image=Path(folder)/'avatar.png';convert_avatar(source,image)
            with self.connect() as db:
                previous=db.execute("SELECT value FROM settings WHERE key='btc_linked_identity'").fetchone()
                if not previous:
                    local=db.execute('SELECT name FROM profile').fetchone()['name']
                    db.execute("INSERT OR REPLACE INTO settings VALUES('btc_local_name',?)",(local.encode(),))
                    db.execute("INSERT OR REPLACE INTO settings VALUES('btc_local_avatar',?)",(target.read_bytes() if target.exists() else b'',))
                    ready=db.execute("SELECT value FROM settings WHERE key='btc_profile_ready'").fetchone()
                    db.execute("INSERT OR REPLACE INTO settings VALUES('btc_local_ready',?)",(ready['value'] if ready else b'0',))
                elif json.loads(bytes(previous['value']))['id']!=str(identity['id']):
                    raise ValueError('Desvincula la cuenta actual antes de conectar otra.')
                safe={'id':str(identity['id']),'username':str(identity['username'])}
                db.execute("INSERT OR REPLACE INTO settings VALUES('btc_linked_identity',?)",(json.dumps(safe).encode(),))
                db.execute("INSERT OR REPLACE INTO settings VALUES('btc_profile_ready',?)",(b'1',))
                db.execute('UPDATE profile SET name=?',(name,))
                if image:
                    target.parent.mkdir(parents=True,exist_ok=True)
                    temp=target.with_suffix('.tmp');temp.write_bytes(image.read_bytes());os.replace(temp,target)

    def unlink_identity(self):
        target=self.avatar_path()
        with self.connect() as db:
            rows={r['key']:bytes(r['value']) for r in db.execute("SELECT * FROM settings WHERE key IN ('btc_linked_identity','btc_local_name','btc_local_avatar','btc_local_ready')")}
            if not rows.get('btc_linked_identity'):return
            if rows.get('btc_local_avatar'):
                target.parent.mkdir(parents=True,exist_ok=True)
                temp=target.with_suffix('.tmp');temp.write_bytes(rows['btc_local_avatar']);os.replace(temp,target)
            else:target.unlink(missing_ok=True)
            db.execute('UPDATE profile SET name=?',(rows['btc_local_name'].decode(),))
            db.execute("INSERT OR REPLACE INTO settings VALUES('btc_profile_ready',?)",(rows.get('btc_local_ready',b'1'),))
            db.execute("DELETE FROM settings WHERE key IN ('btc_linked_identity','btc_local_name','btc_local_avatar','btc_local_ready')")

    def avatar_path(self):
        identity=uuid.UUID(self.profile()['id']).hex
        return self.path.parent/'avatars'/(identity+'.png')

    def set_avatar(self,source):
        from avatar_image import convert_avatar
        target=self.avatar_path();target.parent.mkdir(parents=True,exist_ok=True)
        temporary=target.with_name(uuid.uuid4().hex+'.tmp')
        try:convert_avatar(source,temporary);os.replace(temporary,target)
        finally:temporary.unlink(missing_ok=True)

    def clear_avatar(self):
        self.avatar_path().unlink(missing_ok=True)

    def observe(self,snapshot):
        if not snapshot:return
        uid=snapshot['self_id'];pid=self.profile()['id'];now=datetime.now(timezone.utc).isoformat()
        with self.connect() as db:
            t=snapshot.get('tournament') or {}
            if t.get('self_enrolled'):
                db.execute('''INSERT INTO participation VALUES (?,?,?,?,?)
                    ON CONFLICT(profile_id,tournament_id) DO UPDATE SET status=excluded.status,title=excluded.title''',
                    (pid,t['id'],t['title'],t['status'],now))
            for kind,battle in (('Duelo',snapshot.get('combat')),('Torneo',t)):
                if not battle:continue
                for match in battle.get('matches',[]):
                    if uid not in (match.get('p1'),match.get('p2')) or match.get('state')!='done' or match.get('score') is None:continue
                    side=0 if match['p1']==uid else 1;score=match['score']
                    db.execute('INSERT OR IGNORE INTO matches VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',
                        (pid,battle['id'],match['id'],kind,match['name2' if side==0 else 'name1'],score[side],score[1-side],
                         int(match['winner']==uid),battle['ft'],battle.get('seconds',180),battle['characters'],now))

    def history(self):
        with self.connect() as db:return [dict(r) for r in db.execute('SELECT * FROM matches ORDER BY finished DESC LIMIT 200')]

    def participations(self):
        with self.connect() as db:return [dict(r) for r in db.execute('SELECT * FROM participation ORDER BY created DESC LIMIT 100')]

    def stats(self):
        with self.connect() as db:
            row=db.execute('SELECT COUNT(*) played,COALESCE(SUM(won),0) wins FROM matches').fetchone()
            return dict(played=row['played'],wins=row['wins'],tournaments=db.execute('SELECT COUNT(*) FROM participation').fetchone()[0])
