"""Room challenges, separate from a tournament and its participant list."""
import secrets
from rising_tournament import Tournament,TournamentError

class Duels:
    def __init__(self,room):self.room=room;self.offer=None;self.battle=None
    def clear(self,message):
        self.offer=self.battle=None;self.room._announce(message)
    def expire(self):
        if self.offer and self.offer['status']=='pending' and self.room.clock()*1000>=self.offer['expires']:
            self.clear('El desafío caducó sin respuesta.')
    def remove(self,uid):
        if self.offer and uid in (self.offer['from'],self.offer['to']):self.clear('Duelo cancelado: un jugador salió de la sala.')
    def active(self):return bool(self.offer and self.offer['status']=='pending' or self.battle and self.battle.status=='running')
    def handle(self,user,d):
        r=self.room;op=d['op'];self.expire()
        if op=='duel_offer':
            if self.active() or r.tournament.status=='running':raise TournamentError('Ya hay un desafío o combate en curso')
            other=next((u for u in r.users.values() if u['id']==d.get('target')),None)
            if not other or other['id']==user['id']:raise TournamentError('Selecciona otro luchador de la sala')
            t=Tournament(r._announce);t.configure('Duelo libre BTC',d.get('ft'),d.get('characters'),d.get('seconds'))
            self.battle=None
            self.offer=dict(id=secrets.token_hex(12),status='pending',**{'from':user['id'],'to':other['id']},name1=user['name'],name2=other['name'],ft=t.ft,characters=t.characters,seconds=t.seconds,expires=r.clock()*1000+120000)
            r._announce(f"{user['name']} desafía a {other['name']}: FT{t.ft}, {t.seconds}s, máximo {t.characters} personajes.")
            return
        o=self.offer
        if not o or d.get('duel_id')!=o['id']:raise TournamentError('El desafío ya no está disponible')
        if op=='duel_accept':
            if user['id']!=o['to']:raise TournamentError('Solo el rival desafiado puede aceptar')
            if o['status']=='accepted':return
            players=[next((u for u in r.users.values() if u['id']==uid),None) for uid in (o['from'],o['to'])]
            if not all(players) or r.tournament.status=='running':raise TournamentError('Los jugadores ya no están disponibles')
            t=Tournament(r._announce,shuffle=lambda values:None);t.configure('Duelo libre BTC',o['ft'],o['characters'],o['seconds'])
            for p in players:t.register(p,['Libre']);p['ready']=True
            t.start();self.battle=t;o['status']='accepted'
        elif op=='duel_decline':
            if user['id']!=o['to'] or o['status']!='pending':raise TournamentError('Solo el rival puede rechazar un desafío pendiente')
            self.clear(user['name']+' rechazó el desafío.')
        elif op=='duel_cancel':
            if user['id'] not in (o['from'],o['to'],r.host_id):raise TournamentError('No puedes cancelar este duelo')
            self.clear(user['name']+' canceló el duelo.')
        else:raise TournamentError('Operación de duelo desconocida')
    def snapshot(self,uid):
        if not self.offer:return {}
        result=dict(duel=dict(self.offer))
        if self.battle:
            result['combat']=self.battle.snapshot(uid);result['combat']['mode']='duel'
        return result
