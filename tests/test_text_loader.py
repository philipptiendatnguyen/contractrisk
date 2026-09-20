"""
tests/test_text_loader.py
----------------------------
Unit-Tests für den Import und die Validierung von Vertragsdateien.
"""

from __future__ import annotations

import os
import tempfile
import unittest

from contractrisk.io_utils.text_loader import (
    load_contract_from_file,
    load_contracts_from_files,
)
from contractrisk.utils.exceptions import UnreadableContractFileError


class TestLoadContractFromFile(unittest.TestCase):
    def _write_temp_file(self, content: str, suffix: str = ".txt") -> str:
        fd, path = tempfile.mkstemp(suffix=suffix)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        self.addCleanup(lambda: os.remove(path))
        return path

    def test_load_valid_txt_file(self) -> None:
        path = self._write_temp_file("Dies ist ein Testvertrag.")
        contract = load_contract_from_file(path)
        self.assertEqual(contract.originaltext, "Dies ist ein Testvertrag.")
        self.assertIsNone(contract.id)

    def test_nonexistent_file_raises(self) -> None:
        with self.assertRaises(UnreadableContractFileError):
            load_contract_from_file("/pfad/der/nicht/existiert.txt")

    def test_wrong_extension_raises(self) -> None:
        path = self._write_temp_file("Inhalt", suffix=".pdf")
        with self.assertRaises(UnreadableContractFileError):
            load_contract_from_file(path)

    def test_empty_file_raises(self) -> None:
        path = self._write_temp_file("   ")
        with self.assertRaises(UnreadableContractFileError):
            load_contract_from_file(path)


class TestLoadContractsFromFiles(unittest.TestCase):
    def test_partial_failure_does_not_abort_batch(self) -> None:
        fd, valid_path = tempfile.mkstemp(suffix=".txt")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write("Gültiger Vertragstext.")
        self.addCleanup(lambda: os.remove(valid_path))

        invalid_path = "/pfad/der/nicht/existiert.txt"

        contracts, errors = load_contracts_from_files([valid_path, invalid_path])
        self.assertEqual(len(contracts), 1)
        self.assertEqual(len(errors), 1)


if __name__ == "__main__":
    unittest.main()
