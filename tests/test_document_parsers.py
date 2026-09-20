"""
tests/test_document_parsers.py
----------------------------------
Unit-Tests für die formatspezifische Textextraktion (PDF, DOCX, XLSX,
PPTX, CSV, ODT, RTF) sowie für die Behandlung nicht unterstützter Formate
über den zentralen Import-Einstieg (text_loader).
"""

from __future__ import annotations

import os
import tempfile
import unittest

from contractrisk.io_utils import document_parsers, text_loader
from contractrisk.utils.exceptions import UnreadableContractFileError, UnsupportedFileFormatError


class TestParseCsv(unittest.TestCase):
    def _write_temp(self, content: str, suffix: str) -> str:
        fd, path = tempfile.mkstemp(suffix=suffix)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        self.addCleanup(lambda: os.remove(path))
        return path

    def test_parses_semicolon_separated_csv(self) -> None:
        path = self._write_temp("Position;Betrag\nGrundgebühr;49,90 EUR\n", suffix=".csv")
        text = document_parsers.parse_csv(path)
        self.assertIn("Grundgebühr", text)
        self.assertIn("49,90 EUR", text)

    def test_empty_csv_raises(self) -> None:
        path = self._write_temp("   ", suffix=".csv")
        with self.assertRaises(UnreadableContractFileError):
            document_parsers.parse_csv(path)


class TestParseDocx(unittest.TestCase):
    def test_extracts_paragraphs_and_tables(self) -> None:
        import docx

        fd, path = tempfile.mkstemp(suffix=".docx")
        os.close(fd)
        os.remove(path)  # python-docx erzeugt die Datei selbst
        self.addCleanup(lambda: os.path.exists(path) and os.remove(path))

        document = docx.Document()
        document.add_paragraph("Dies ist ein Testvertrag mit automatischer Verlängerung.")
        table = document.add_table(rows=1, cols=2)
        table.rows[0].cells[0].text = "Kündigungsfrist"
        table.rows[0].cells[1].text = "3 Monate"
        document.save(path)

        text = document_parsers.parse_docx(path)
        self.assertIn("automatischer Verlängerung", text)
        self.assertIn("Kündigungsfrist", text)
        self.assertIn("3 Monate", text)

    def test_invalid_docx_raises(self) -> None:
        fd, path = tempfile.mkstemp(suffix=".docx")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write("Das ist kein gültiges docx.")
        self.addCleanup(lambda: os.remove(path))
        with self.assertRaises(UnreadableContractFileError):
            document_parsers.parse_docx(path)


class TestParseXlsx(unittest.TestCase):
    def test_extracts_sheet_content(self) -> None:
        import openpyxl

        fd, path = tempfile.mkstemp(suffix=".xlsx")
        os.close(fd)
        os.remove(path)
        self.addCleanup(lambda: os.path.exists(path) and os.remove(path))

        workbook = openpyxl.Workbook()
        sheet = workbook.active
        sheet.title = "Preisliste"
        sheet.append(["Leistung", "Preis"])
        sheet.append(["Grundgebühr", "49,90 EUR"])
        workbook.save(path)

        text = document_parsers.parse_xlsx(path)
        self.assertIn("Preisliste", text)
        self.assertIn("Grundgebühr", text)

    def test_empty_workbook_raises(self) -> None:
        import openpyxl

        fd, path = tempfile.mkstemp(suffix=".xlsx")
        os.close(fd)
        os.remove(path)
        self.addCleanup(lambda: os.path.exists(path) and os.remove(path))

        workbook = openpyxl.Workbook()
        workbook.save(path)

        with self.assertRaises(UnreadableContractFileError):
            document_parsers.parse_xlsx(path)


class TestParsePptx(unittest.TestCase):
    def test_extracts_slide_text(self) -> None:
        from pptx import Presentation

        fd, path = tempfile.mkstemp(suffix=".pptx")
        os.close(fd)
        os.remove(path)
        self.addCleanup(lambda: os.path.exists(path) and os.remove(path))

        presentation = Presentation()
        slide_layout = presentation.slide_layouts[1]
        slide = presentation.slides.add_slide(slide_layout)
        slide.shapes.title.text = "Vertragsübersicht"
        presentation.save(path)

        text = document_parsers.parse_pptx(path)
        self.assertIn("Folie 1", text)
        self.assertIn("Vertragsübersicht", text)


class TestParseRtf(unittest.TestCase):
    def test_strips_control_words(self) -> None:
        fd, path = tempfile.mkstemp(suffix=".rtf")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(r"{\rtf1\ansi\deff0 {\b Kündigungsfrist:} drei Monate\par}")
        self.addCleanup(lambda: os.remove(path))

        text = document_parsers.parse_rtf(path)
        self.assertIn("Kündigungsfrist", text)
        self.assertIn("drei Monate", text)
        self.assertNotIn("\\b", text)


class TestUnsupportedFormats(unittest.TestCase):
    def _write_temp(self, suffix: str) -> str:
        fd, path = tempfile.mkstemp(suffix=suffix)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write("Inhalt")
        self.addCleanup(lambda: os.remove(path))
        return path

    def test_doc_format_gives_clear_message(self) -> None:
        path = self._write_temp(".doc")
        with self.assertRaises(UnsupportedFileFormatError) as ctx:
            text_loader.load_contract_from_file(path)
        self.assertIn("docx", str(ctx.exception).lower())

    def test_unknown_format_lists_supported_extensions(self) -> None:
        path = self._write_temp(".xyz")
        with self.assertRaises(UnsupportedFileFormatError) as ctx:
            text_loader.load_contract_from_file(path)
        self.assertIn(".pdf", str(ctx.exception))

    def test_unsupported_error_is_subclass_of_unreadable(self) -> None:
        # Bestehender Fehlerbehandlungscode, der auf UnreadableContractFileError
        # prüft, muss auch UnsupportedFileFormatError abfangen.
        self.assertTrue(issubclass(UnsupportedFileFormatError, UnreadableContractFileError))


if __name__ == "__main__":
    unittest.main()
