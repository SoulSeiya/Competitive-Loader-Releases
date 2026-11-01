import struct
import unittest
from replay_spectator import split_replay,HEADER,BLOCK,FILE_SIZE,COUNTS
from competitive_loader import LoaderError


class ReplayTests(unittest.TestCase):
    def test_split_copy_preserves_both_input_tracks_and_only_changes_layout(self):
        data=bytearray(FILE_SIZE);data[HEADER:HEADER+8]=b'btls\x07\0\0\0'
        for o in COUNTS:struct.pack_into('<i',data,HEADER+o,600)
        data[HEADER+0x5A8:HEADER+0x5B8]=bytes(range(16))
        original=bytes(data);expected=bytearray(data);struct.pack_into('<i',expected,HEADER+0x24,1)
        self.assertEqual(split_replay(data),bytes(expected))
        self.assertEqual(bytes(data),original)

    def test_reject_incompatible_and_incomplete_replay(self):
        for data in (b'',bytes(FILE_SIZE),bytes(HEADER+BLOCK)):
            with self.assertRaises(LoaderError):split_replay(data)
        data=bytearray(FILE_SIZE);data[HEADER:HEADER+8]=b'btls\x07\0\0\0'
        for o in COUNTS:struct.pack_into('<i',data,HEADER+o,9001)
        with self.assertRaises(LoaderError):split_replay(data)
