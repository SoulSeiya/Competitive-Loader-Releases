import json
import unittest
from challonge_shared import SharedChallongeClient
from challonge_client import ChallongeError


class SharedChallongeTests(unittest.TestCase):
    def client(self):
        class Response:
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def read(self,limit):return json.dumps(dict(protocol=1,tournament=dict(participants=[],matches=[]))).encode()
        class Opener:
            def open(self,request,timeout):self.request=request;return Response()
        client=SharedChallongeClient();client.opener=Opener();return client

    def test_participant_read_does_not_require_or_transmit_organizer_credentials(self):
        client=self.client();client.request('https://challonge.com/es/trunksprofecyI')
        request=client.opener.request
        self.assertEqual(request.get_method(),'GET')
        self.assertIsNone(request.data)
        self.assertIsNone(request.get_header('Authorization'))
        self.assertIn('slug=trunksprofecyI',request.full_url)

    def test_authorization_upload_is_https_post_body_never_a_query_string(self):
        client=self.client();client.request('https://challonge.com/es/trunksprofecyI',dict(access_token='private-token',refresh_token='private-refresh'))
        request=client.opener.request
        self.assertEqual(request.get_method(),'POST')
        self.assertTrue(request.full_url.startswith('https://'))
        self.assertNotIn('private',request.full_url)
        self.assertEqual(json.loads(request.data)['refresh_token'],'private-refresh')

    def test_arbitrary_links_are_rejected_before_contacting_service(self):
        client=self.client()
        with self.assertRaises(ValueError):client.request('https://example.com/tournament')
        self.assertFalse(hasattr(client.opener,'request'))
