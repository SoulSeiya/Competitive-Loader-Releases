import unittest
from unittest.mock import patch
import client_updates as updates


class ClientUpdateTests(unittest.TestCase):
    def test_only_newer_installable_release_is_available(self):
        base={'version':(2,1,0),'download_url':'https://example.invalid/loader.zip'}
        self.assertEqual(updates.classify_release(base,(2,0,0)),'available')
        self.assertEqual(updates.classify_release(base,(2,1,0)),'current')
        self.assertEqual(updates.classify_release({**base,'download_url':''},(2,0,0)),'missing_asset')

    def test_notes_paginate_without_losing_content(self):
        notes=('Cambio del loader\n'*200).strip()
        pages=updates.note_pages(notes)
        self.assertTrue(all(len(page)<=620 for page in pages))
        self.assertEqual(' '.join(notes.split()),' '.join(' '.join(pages).split()))

    def test_long_unbroken_note_and_empty_notes(self):
        self.assertEqual(''.join(updates.note_pages('a'*1400)),'a'*1400)
        self.assertTrue(updates.note_pages(''))

    def test_history_can_fall_back_to_current_release_without_engine_lookup(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as folder,patch.object(updates.core,'HERE',Path(folder)),patch('client_updates.urllib.request.urlopen',side_effect=OSError('offline')),patch.object(updates.core,'latest_release_info') as upstream:
            rows=updates.release_history({'tag':'v2.0.1','notes':'Notas'})
            self.assertEqual(rows[0]['tag'],'v2.0.1')
            upstream.assert_not_called()
