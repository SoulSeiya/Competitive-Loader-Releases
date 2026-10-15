from pathlib import Path
import struct
import tempfile
import unittest
import competitive_loader as loader


class CoffTests(unittest.TestCase):
    def test_uninitialized_section_allocates_zeros_instead_of_coff_header(self):
        # Native locks and observer state require zero-initialized BSS.
        header = struct.pack("<HHIIIHH", 0x8664, 1, 0, 60, 0, 0, 0)
        section = struct.pack("<8sIIIIIIHHI", b".bss", 0, 0, 64, 0, 0, 0, 0, 0, 0xC0300080)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "zero.o"
            path.write_bytes(header + section + struct.pack("<I", 4))
            obj = loader.CoffObject(path)
            bss = obj.sections[1]
            self.assertEqual(bss.size, 64)
            self.assertTrue(bss.allocated)
            self.assertEqual(bss.data, b"")
