import unittest
import tempfile
from pathlib import Path
from challonge_client import ChallongeAPI,ChallongeError,tournament_identifier


class ChallongeTests(unittest.TestCase):
    def test_links_cannot_redirect_credentials_to_other_hosts(self):
        self.assertEqual(tournament_identifier('https://challonge.com/es/torneobtc0'),'torneobtc0')
        for url in ('https://evil.test/torneo','https://challonge.com.evil.test/torneo','http://challonge.com/torneo','https://x@challonge.com/torneo','https://challonge.com/torneo/settings','https://challonge.com:8000/torneo'):
            with self.subTest(url=url),self.assertRaises(ValueError):tournament_identifier(url)

    def test_pagination_preserves_challonge_order_and_signed_losers_round(self):
        class API(ChallongeAPI):
            def request(self,url,token=None,form=None):
                self.calls.append(url)
                if '/participants.json?' in url:
                    if 'page=2&' in url:return {'data':[{'id':'101','attributes':{'name':'Last'}}]}
                    return {'data':[{'id':str(i),'attributes':{'name':f'Player {i}'}} for i in range(1,101)]}
                if '/matches.json?' in url:return {'data':[{'id':'99','attributes':{'round':-2,'state':'open','relationships':{'player1':{'data':{'id':'101'}},'player2':{'data':{'id':'1'}}}}}]}
                return {'data':{'id':'77','attributes':{'name':'Test','tournament_type':'double elimination'}}}
        api=API('test-client');api.calls=[]
        bracket=api.bracket('https://challonge.com/es/torneobtc0','secret')
        self.assertEqual(len(bracket['participants']),101)
        self.assertEqual(bracket['matches'][0]['round'],-2)
        self.assertEqual(bracket['matches'][0]['name1'],'Last')
        self.assertEqual(bracket['matches'][0]['name2'],'Player 1')
        self.assertTrue(all('secret' not in url for url in api.calls))

    def test_device_login_never_accepts_external_authorization_site(self):
        class API(ChallongeAPI):
            def request(self,*args,**kwargs):return dict(device_code='private',user_code='public',verification_uri='https://evil.test/',expires_in=300)
        with self.assertRaises(ChallongeError):API('public-client').device()

    def test_device_grant_uses_public_client_without_secret(self):
        class API(ChallongeAPI):
            def request(self,url,token=None,form=None):
                self.form=form
                return dict(device_code='private',user_code='public',verification_uri='https://connect.challonge.com/oauth/device',expires_in=300)
        api=API('public-client');api.device()
        self.assertNotIn('client_secret',api.form)
        self.assertEqual(api.form['client_id'],'public-client')

    def test_community_scope_is_requested_only_for_organizer_community_login(self):
        class API(ChallongeAPI):
            def request(self,url,token=None,form=None):
                self.form=form
                return dict(device_code='private',user_code='public',verification_uri='https://connect.challonge.com/oauth/device',expires_in=300)
        api=API('public-client');api.device()
        self.assertNotIn('communities:manage',api.form['scope'])
        api.device(community=True)
        self.assertIn('communities:manage',api.form['scope'])

    def test_existing_community_tournament_uses_community_endpoint_without_writes(self):
        class API(ChallongeAPI):
            def request(self,url,token=None,form=None):
                self.calls.append((url,form))
                if '/participants.json?' in url or '/matches.json?' in url:return {'data':[]}
                return {'data':{'id':'77','attributes':{'name':'Existing UT','tournament_type':'double elimination'}}}
        api=API('public-client');api.calls=[]
        result=api.bracket('https://challonge.com/es/torneobtc0','secret','universotenkaichi')
        self.assertEqual(result['title'],'Existing UT')
        self.assertTrue(all('/communities/universotenkaichi/tournaments/torneobtc0' in url and form is None for url,form in api.calls))
        with self.assertRaises(ValueError):api.bracket('https://challonge.com/es/torneobtc0','secret','../other')

    def test_live_match_format_without_player_relationships_keeps_player_slots(self):
        class API(ChallongeAPI):
            def request(self,url,token=None,form=None):
                if '/participants.json?' in url:return {'data':[{'id':'10','attributes':{'name':'P1'}},{'id':'20','attributes':{'name':'P2'}}]}
                if '/matches.json?' in url:return {'data':[{'id':'1','attributes':{'round':1,'points_by_participant':[{'participant_id':10},{'participant_id':20}]},'relationships':{'attachments':{'data':[]}}}]}
                return {'data':{'id':'77','attributes':{'name':'Live format'}}}
        m=API('public-client').bracket('https://challonge.com/es/trunksprofecyI','secret')['matches'][0]
        self.assertEqual((m['p1'],m['p2'],m['name1'],m['name2']),('10','20','P1','P2'))

    def test_organizer_login_cannot_replace_player_identity_or_tokens(self):
        from challonge_client import ChallongeManager
        from player_profile import ProfileStore
        class API:
            def me(self,token):return dict(id='organizer-id',username='Organizer',image_url='')
        with tempfile.TemporaryDirectory() as folder:
            store=ProfileStore(Path(folder)/'profile.sqlite3',initial_name='Player')
            player=ChallongeManager(store);organizer=ChallongeManager(store,organizer=True)
            organizer._profile(API(),{'access_token':'test'})
            self.assertEqual(store.profile()['name'],'Player')
            self.assertIsNone(player.identity)
            self.assertNotEqual(player.prefix,organizer.prefix)
            self.assertEqual(organizer.identity['username'],'Organizer')
