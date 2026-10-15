import struct
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import competitive_loader as core


class DecompContractTests(unittest.TestCase):
    def image(self, calls=1, labels=1, rva=0x1010):
        pe = SimpleNamespace(rvas={"hook": rva}, absolute=set(), text_rva=0x1000,
                             text_data=bytes(64), preferred_base=0x20000000,
                             path=Path("fixture.exe"),
                             direct_branches_to=lambda name: [(0x1020, 0xE8)] * calls,
                             literal_addresses=lambda text, base: [base + 0x2000] * labels)
        return SimpleNamespace(pe=pe, patch_symbols={"hook": "wrapper"},
                               wrapper_targets={"hook"}, entry_targets=set(),
                               time_label_patches={b"old\0": b"new\0"})

    def test_symbol_without_call_sites_is_rejected_before_launch(self):
        with self.assertRaisesRegex(core.IncompatibleDecompError, "no hay llamadas"):
            core.validate_patch_contract(self.image(calls=0))

    def test_symbol_in_data_or_short_code_tail_is_rejected(self):
        for rva in (0x800, 0x103F):
            with self.subTest(rva=rva), self.assertRaisesRegex(core.IncompatibleDecompError, "código ejecutable"):
                core.validate_patch_contract(self.image(rva=rva))

    def test_ambiguous_label_is_rejected_before_launch(self):
        with self.assertRaisesRegex(core.IncompatibleDecompError, "etiqueta"):
            core.validate_patch_contract(self.image(labels=2))

    def test_complete_contract_reports_version_and_hook_coverage(self):
        digest = next(k for k, v in core.REVIEWED_DECOMP_HASHES.items() if v == "v0.1.35.4")
        with mock.patch.object(core, "sha256_file", return_value=digest):
            report = core.validate_patch_contract(self.image())
        self.assertEqual(report["version"], "v0.1.35.4")
        self.assertEqual(report["wrapper_calls"], {"hook": 1})

    def test_branch_index_handles_relocation_aliases_and_negative_displacements(self):
        pe = core.PeSymbols.__new__(core.PeSymbols)
        pe.text_rva = 0x1000
        pe.rvas = {"target": 0x1018, "alias": 0x1018}
        data = bytearray(40)
        data[0:5] = struct.pack("<Bi", 0xE8, 0x1018 - 0x1005)
        data[30:35] = struct.pack("<Bi", 0xE9, 0x1018 - 0x1023)
        pe.text_data = bytes(data)
        pe._branch_index = None
        expected = [(0x1000, 0xE8), (0x101E, 0xE9)]
        self.assertEqual(pe.direct_branches_to("target"), expected)
        self.assertEqual(pe.direct_branches_to("alias"), expected)
        self.assertEqual(pe.direct_branches_to("absent"), [])

    def test_payload_keeps_its_plan_when_another_profile_is_selected(self):
        pe = SimpleNamespace(address=lambda name, base: None)
        with (tempfile.TemporaryDirectory() as folder,
              mock.patch.object(core, "PATCH_OBJECTS", ()),
              mock.patch.object(core, "PATCH_SYMBOLS", {"first": "wrapper"}),
              mock.patch.object(core, "ENTRY_PATCH_TARGETS", {"first"}),
              mock.patch.object(core, "CALL_WRAPPER_TARGETS", set())):
            image = core.PayloadImage(Path(folder), pe)
        with mock.patch.object(core, "PATCH_SYMBOLS", {}):
            # A global plan change must not silently turn this payload into a no-op.
            with self.assertRaisesRegex(core.LoaderError, "wrapper"):
                image.build(0x60000000, 0x20000000)
        self.assertEqual(image.entry_targets, {"first"})


if __name__ == "__main__":
    unittest.main()
