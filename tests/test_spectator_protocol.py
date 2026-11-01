from unittest import TestCase
from spectator_protocol import InputStream,SpectatorError,encode_chunk,decode_chunk,compatible

def header(**values):
    result=dict(version=1,tournament_id='cup',generation='first',match=1,seed=123,rules=0,
        first_tick=1,exe_sha256='a'*64,payload_sha256='b'*64,data_sha256='c'*64,memory_sha256='d'*64,
        names=['P1','P2'],options=[0,0])
    result.update(values);return result

class SpectatorProtocolTests(TestCase):
    def test_confirmed_frames_are_ordered_and_retries_are_idempotent(self):
        stream=InputStream(header());chunk=encode_chunk(1,b'x'*72)
        self.assertTrue(stream.append('first',chunk));self.assertFalse(stream.append('first',chunk))
        self.assertEqual(stream.frame(2),b'x'*36)
        with self.assertRaises(SpectatorError):stream.append('first',encode_chunk(4,b'y'*36))
        with self.assertRaises(SpectatorError):stream.append('first',encode_chunk(1,b'y'*72))
        with self.assertRaises(SpectatorError):stream.frame(3)

    def test_reconnect_cannot_mix_generations_and_finished_stream_cannot_extend(self):
        stream=InputStream(header());chunk=encode_chunk(1,b'x'*36)
        with self.assertRaises(SpectatorError):stream.append('second',chunk)
        stream.append('first',chunk);stream.finish('first',2)
        self.assertFalse(stream.append('first',chunk))
        with self.assertRaises(SpectatorError):stream.append('first',encode_chunk(2,b'y'*36))

    def test_receiver_rejects_corruption_or_wrong_game_build(self):
        chunk=encode_chunk(1,b'x'*36);chunk['pads']='YQ=='
        with self.assertRaises(SpectatorError):decode_chunk(chunk)
        fingerprints={name:header()[name] for name in ('exe_sha256','payload_sha256','data_sha256','memory_sha256')}
        self.assertEqual(compatible(header(),fingerprints)['seed'],123)
        fingerprints['data_sha256']='d'*64
        with self.assertRaises(SpectatorError):compatible(header(),fingerprints)

    def test_header_never_accepts_memory_or_unbounded_payloads(self):
        with self.assertRaises(SpectatorError):InputStream(header(first_tick=-1))
        with self.assertRaises(SpectatorError):InputStream(header(seed=True))
        with self.assertRaises(SpectatorError):InputStream(header(generation='../other'))
        with self.assertRaises(SpectatorError):InputStream(header(names=['x'*65,'P2']))
        with self.assertRaises(SpectatorError):encode_chunk(1,b'x'*(36*49))
