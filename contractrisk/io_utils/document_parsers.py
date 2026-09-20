"""
io_utils/document_parsers.py
--------------------------------
Format-spezifische Textextraktion für den Dokumenten-Import.

Jede Funktion in diesem Modul nimmt einen Dateipfad entgegen und liefert
den extrahierten Inhalt als einfachen, durchsuchbaren Text-String zurück -
unabhängig davon, ob die Quelle ein Fließtext (Word/PDF), eine Tabelle
(Excel/CSV) oder eine Präsentation (PowerPoint) war. Dadurch kann die
gesamte nachgelagerte Analyse (Regel-Engine, Fristen-Erkennung,
Widerspruchsprüfung) unverändert auf reinem Text arbeiten, unabhängig vom
ursprünglichen Dateiformat.

Tabellarische/strukturierte Formate (CSV, XLSX, PPTX) werden dabei bewusst
in eine LESBARE Textrepräsentation überführt (Zeilen/Zellen bzw.
Folieninhalte werden mit Trennzeichen und Abschnittsüberschriften
zusammengefügt), statt nur "roh" aneinandergereiht zu werden - so bleiben
z. B. Preistabellen oder Foliennotizen für die Regel-Engine durchsuchbar
und für den Menschen im markierten Textfenster nachvollziehbar.

Jede Funktion wirft bei technischen Problemen (defekte/verschlüsselte
Datei, leeres Dokument, fehlender Text) eine `UnreadableContractFileError`
mit einer für den Nutzer verständlichen Fehlermeldung - nie ein rohes
Traceback der zugrunde liegenden Bibliothek.
"""

from __future__ import annotations

import csv
import io
import re

from contractrisk.utils.exceptions import UnreadableContractFileError
from contractrisk.utils.logger import get_logger

logger = get_logger(__name__)

_CANDIDATE_ENCODINGS = ("utf-8", "utf-8-sig", "cp1252", "latin-1")


def _read_raw_bytes(file_path: str) -> bytes:
    try:
        with open(file_path, "rb") as f:
            return f.read()
    except OSError as exc:
        raise UnreadableContractFileError(f"Datei konnte nicht gelesen werden: {exc}") from exc


def _decode_with_fallback(raw_bytes: bytes, file_path: str) -> str:
    last_error: Exception | None = None
    for encoding in _CANDIDATE_ENCODINGS:
        try:
            return raw_bytes.decode(encoding)
        except (UnicodeDecodeError, UnicodeError) as exc:
            last_error = exc
            continue
    raise UnreadableContractFileError(
        f"Die Datei '{file_path}' konnte mit keinem der unterstützten "
        f"Encodings gelesen werden ({', '.join(_CANDIDATE_ENCODINGS)})."
    ) from last_error


# ---------------------------------------------------------------------------
# Reine Textdateien
# ---------------------------------------------------------------------------

def parse_txt(file_path: str) -> str:
    """Liest eine .txt-Datei robust ein, auch bei unbekanntem Encoding
    (typisch bei Verträgen, die aus Word/PDF kopiert wurden)."""
    return _decode_with_fallback(_read_raw_bytes(file_path), file_path)


# ---------------------------------------------------------------------------
# CSV
# ---------------------------------------------------------------------------

def parse_csv(file_path: str) -> str:
    """Liest eine CSV-Datei ein und wandelt sie in eine lesbare
    Textrepräsentation um (eine Zeile pro Datensatz, Spalten durch " | "
    getrennt), damit Regel-Engine und Fristenerkennung auf tabellarischen
    Inhalten (z. B. Preislisten, Zahlungspläne) genauso arbeiten können
    wie auf Fließtext."""
    raw_text = _decode_with_fallback(_read_raw_bytes(file_path), file_path)

    if not raw_text.strip():
        raise UnreadableContractFileError(f"Die CSV-Datei '{file_path}' ist leer.")

    try:
        dialect = csv.Sniffer().sniff(raw_text[:4096], delimiters=";,\t|")
    except csv.Error:
        dialect = csv.excel  # Fallback: Standard-Komma-Trennung

    try:
        reader = csv.reader(io.StringIO(raw_text), dialect)
        rows = [row for row in reader if any(cell.strip() for cell in row)]
    except csv.Error as exc:
        raise UnreadableContractFileError(
            f"Die CSV-Datei '{file_path}' konnte nicht als Tabelle interpretiert werden: {exc}"
        ) from exc

    if not rows:
        raise UnreadableContractFileError(f"Die CSV-Datei '{file_path}' enthält keine verwertbaren Daten.")

    lines = [" | ".join(cell.strip() for cell in row) for row in rows]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# PDF
# ---------------------------------------------------------------------------

def parse_pdf(file_path: str) -> str:
    """Extrahiert den Text aller Seiten eines PDF-Dokuments."""
    try:
        from pypdf import PdfReader
        from pypdf.errors import PdfReadError
    except ImportError as exc:
        raise UnreadableContractFileError(
            "Für den PDF-Import wird die Bibliothek 'pypdf' benötigt. Bitte "
            "'pip install -r requirements.txt' ausführen."
        ) from exc

    try:
        reader = PdfReader(file_path)
    except PdfReadError as exc:
        raise UnreadableContractFileError(
            f"Die PDF-Datei '{file_path}' ist beschädigt oder kein gültiges PDF: {exc}"
        ) from exc
    except FileNotFoundError as exc:
        raise UnreadableContractFileError(f"Die Datei '{file_path}' wurde nicht gefunden.") from exc

    if reader.is_encrypted:
        # Manche PDFs lassen sich mit leerem Passwort trotzdem entschlüsseln
        # (reiner "Restriktions"-Schutz ohne echtes Kennwort)
        try:
            reader.decrypt("")
        except Exception:
            pass

    if reader.is_encrypted:
        raise UnreadableContractFileError(
            f"Die PDF-Datei '{file_path}' ist passwortgeschützt und kann nicht "
            "automatisch gelesen werden. Bitte entfernen Sie den Kennwortschutz "
            "und importieren Sie die Datei erneut."
        )

    page_texts: list[str] = []
    for page_number, page in enumerate(reader.pages, start=1):
        try:
            page_text = page.extract_text() or ""
        except Exception as exc:  # pypdf kann bei defekten Seiten diverse Fehler werfen
            logger.warning("Seite %d von '%s' konnte nicht gelesen werden: %s", page_number, file_path, exc)
            page_text = ""
        if page_text.strip():
            page_texts.append(page_text.strip())

    combined_text = "\n\n".join(page_texts).strip()

    if not combined_text:
        ocr_text, ocr_status = _try_ocr_fallback(file_path)
        if ocr_text:
            logger.info("PDF '%s' enthielt keinen eingebetteten Text - per OCR gelesen.", file_path)
            return ocr_text
        raise UnreadableContractFileError(
            f"Aus der PDF-Datei '{file_path}' konnte kein eingebetteter Text extrahiert "
            f"werden - vermutlich handelt es sich um ein gescanntes Dokument. {ocr_status} "
            "Alternativ können Sie eine textbasierte PDF-Version oder eine .txt-Abschrift importieren."
        )

    return combined_text


def _try_ocr_fallback(file_path: str) -> tuple[str | None, str]:
    """Optionaler OCR-Fallback für gescannte PDFs ohne eingebettete
    Textebene (z. B. abfotografierte oder eingescannte Schreiben).

    Diese Funktion ist bewusst so geschrieben, dass sie bei fehlenden
    optionalen Abhängigkeiten (pytesseract, pdf2image) oder einer
    fehlenden System-Installation von Tesseract/Poppler NICHT abstürzt,
    sondern sauber `(None, <Erklärung>)` zurückgibt - der Aufrufer zeigt
    dann die reguläre, verständliche Fehlermeldung an. OCR ist damit ein
    optionales Extra, kein hartes Erfordernis der Anwendung (siehe
    requirements.txt).

    Rückgabe: (erkannter_text_oder_None, status_meldung_fuer_nutzer)
    """
    try:
        import pytesseract
        from pdf2image import convert_from_path
    except ImportError:
        return None, (
            "Optionale OCR-Unterstützung ist nicht installiert "
            "('pip install pytesseract pdf2image', zusätzlich wird die "
            "Systemsoftware Tesseract OCR und Poppler benötigt)."
        )

    try:
        images = convert_from_path(file_path, dpi=300)
    except Exception as exc:
        return None, f"OCR-Versuch fehlgeschlagen (PDF konnte nicht gerastert werden: {exc})."

    recognized_pages: list[str] = []
    for page_number, image in enumerate(images, start=1):
        try:
            page_text = pytesseract.image_to_string(image, lang="eng+deu")
        except Exception:
            try:
                # Fallback, falls das deutsche Sprachpaket lokal nicht
                # installiert ist (nur "eng" ist bei vielen
                # Standardinstallationen vorhanden).
                page_text = pytesseract.image_to_string(image, lang="eng")
            except Exception as exc:
                logger.warning("OCR fehlgeschlagen für Seite %d von '%s': %s", page_number, file_path, exc)
                page_text = ""
        if page_text.strip():
            recognized_pages.append(page_text.strip())

    combined = "\n\n".join(recognized_pages).strip()
    if not combined:
        return None, "OCR wurde versucht, konnte aber keinen Text erkennen."
    return combined, "Text wurde per OCR erkannt."


# ---------------------------------------------------------------------------
# Word (.docx)
# ---------------------------------------------------------------------------

def parse_docx(file_path: str) -> str:
    """Extrahiert Fließtext-Absätze UND Tabelleninhalte aus einem
    Word-Dokument (.docx)."""
    try:
        import docx  # python-docx
    except ImportError as exc:
        raise UnreadableContractFileError(
            "Für den Word-Import (.docx) wird die Bibliothek 'python-docx' "
            "benötigt. Bitte 'pip install -r requirements.txt' ausführen."
        ) from exc

    try:
        document = docx.Document(file_path)
    except Exception as exc:
        raise UnreadableContractFileError(
            f"Die Word-Datei '{file_path}' ist beschädigt oder kein gültiges .docx: {exc}"
        ) from exc

    parts: list[str] = []
    for paragraph in document.paragraphs:
        if paragraph.text.strip():
            parts.append(paragraph.text.strip())

    for table in document.tables:
        for row in table.rows:
            cell_texts = [cell.text.strip() for cell in row.cells if cell.text.strip()]
            if cell_texts:
                parts.append(" | ".join(cell_texts))

    combined_text = "\n".join(parts).strip()
    if not combined_text:
        raise UnreadableContractFileError(
            f"Die Word-Datei '{file_path}' enthält keinen extrahierbaren Text."
        )
    return combined_text


# ---------------------------------------------------------------------------
# Excel (.xlsx)
# ---------------------------------------------------------------------------

def parse_xlsx(file_path: str) -> str:
    """Extrahiert alle Arbeitsblätter einer Excel-Datei (.xlsx) als
    lesbaren Text (ein Abschnitt pro Blatt, Zeilen mit ' | ' getrennt)."""
    try:
        import openpyxl
    except ImportError as exc:
        raise UnreadableContractFileError(
            "Für den Excel-Import (.xlsx) wird die Bibliothek 'openpyxl' "
            "benötigt. Bitte 'pip install -r requirements.txt' ausführen."
        ) from exc

    try:
        workbook = openpyxl.load_workbook(file_path, data_only=True, read_only=True)
    except Exception as exc:
        raise UnreadableContractFileError(
            f"Die Excel-Datei '{file_path}' ist beschädigt oder kein gültiges .xlsx: {exc}"
        ) from exc

    sections: list[str] = []
    for sheet in workbook.worksheets:
        sheet_lines: list[str] = []
        for row in sheet.iter_rows(values_only=True):
            cell_texts = [str(cell).strip() for cell in row if cell is not None and str(cell).strip()]
            if cell_texts:
                sheet_lines.append(" | ".join(cell_texts))
        if sheet_lines:
            sections.append(f"=== Tabellenblatt: {sheet.title} ===\n" + "\n".join(sheet_lines))

    combined_text = "\n\n".join(sections).strip()
    if not combined_text:
        raise UnreadableContractFileError(
            f"Die Excel-Datei '{file_path}' enthält keine verwertbaren Daten."
        )
    return combined_text


# ---------------------------------------------------------------------------
# PowerPoint (.pptx)
# ---------------------------------------------------------------------------

def parse_pptx(file_path: str) -> str:
    """Extrahiert alle Textinhalte (inkl. Sprechernotizen) einer
    PowerPoint-Präsentation (.pptx), gruppiert nach Folie."""
    try:
        from pptx import Presentation
    except ImportError as exc:
        raise UnreadableContractFileError(
            "Für den PowerPoint-Import (.pptx) wird die Bibliothek "
            "'python-pptx' benötigt. Bitte 'pip install -r requirements.txt' ausführen."
        ) from exc

    try:
        presentation = Presentation(file_path)
    except Exception as exc:
        raise UnreadableContractFileError(
            f"Die PowerPoint-Datei '{file_path}' ist beschädigt oder kein gültiges .pptx: {exc}"
        ) from exc

    sections: list[str] = []
    for slide_number, slide in enumerate(presentation.slides, start=1):
        slide_lines: list[str] = []
        for shape in slide.shapes:
            if shape.has_text_frame and shape.text_frame.text.strip():
                slide_lines.append(shape.text_frame.text.strip())
            if shape.has_table:
                for row in shape.table.rows:
                    cell_texts = [cell.text.strip() for cell in row.cells if cell.text.strip()]
                    if cell_texts:
                        slide_lines.append(" | ".join(cell_texts))

        if slide.has_notes_slide and slide.notes_slide.notes_text_frame.text.strip():
            slide_lines.append("Notizen: " + slide.notes_slide.notes_text_frame.text.strip())

        if slide_lines:
            sections.append(f"=== Folie {slide_number} ===\n" + "\n".join(slide_lines))

    combined_text = "\n\n".join(sections).strip()
    if not combined_text:
        raise UnreadableContractFileError(
            f"Die PowerPoint-Datei '{file_path}' enthält keinen extrahierbaren Text."
        )
    return combined_text


# ---------------------------------------------------------------------------
# OpenDocument-Text (.odt)
# ---------------------------------------------------------------------------

def parse_odt(file_path: str) -> str:
    """Extrahiert den Fließtext aus einer OpenDocument-Textdatei (.odt)."""
    try:
        from odf.opendocument import load as load_odf
        from odf.text import P as OdfParagraph
        from odf.teletype import extractText
    except ImportError as exc:
        raise UnreadableContractFileError(
            "Für den Import von OpenDocument-Dateien (.odt) wird die "
            "Bibliothek 'odfpy' benötigt. Bitte 'pip install -r requirements.txt' ausführen."
        ) from exc

    try:
        document = load_odf(file_path)
    except Exception as exc:
        raise UnreadableContractFileError(
            f"Die ODT-Datei '{file_path}' ist beschädigt oder kein gültiges .odt: {exc}"
        ) from exc

    paragraphs = document.getElementsByType(OdfParagraph)
    parts = [extractText(p).strip() for p in paragraphs if extractText(p).strip()]

    combined_text = "\n".join(parts).strip()
    if not combined_text:
        raise UnreadableContractFileError(
            f"Die ODT-Datei '{file_path}' enthält keinen extrahierbaren Text."
        )
    return combined_text


# ---------------------------------------------------------------------------
# Rich Text Format (.rtf) - einfache, abhängigkeitsfreie Extraktion
# ---------------------------------------------------------------------------

_RTF_CONTROL_WORD = re.compile(r"\\[a-zA-Z]+-?\d* ?")
_RTF_HEX_ESCAPE = re.compile(r"\\'[0-9a-fA-F]{2}")
_RTF_GROUP_MARKERS = re.compile(r"[{}]")
_RTF_UNICODE_ESCAPE = re.compile(r"\\u(-?\d+)\??")


def parse_rtf(file_path: str) -> str:
    """Extrahiert Klartext aus einer RTF-Datei mittels eines einfachen,
    abhängigkeitsfreien Regex-Strippers.

    RTF ist grundsätzlich ein textbasiertes Format mit Steuercodes
    (Kontrollwörtern, geschweiften Klammern für Gruppen). Diese Funktion
    entfernt die gängigsten Steuercodes und liefert den verbleibenden
    Klartext. Bei sehr komplex formatierten RTF-Dateien (verschachtelte
    Objekte, eingebettete Bilder) kann die Extraktion unvollständig sein -
    dies wird im Ergebnis nicht verschleiert, sondern die Anwendung weist
    in diesem Fall (kein extrahierbarer Text) auf eine manuelle
    Konvertierung als Alternative hin.
    """
    raw_text = _decode_with_fallback(_read_raw_bytes(file_path), file_path)

    if "\\rtf1" not in raw_text[:200]:
        logger.warning("Datei '%s' trägt die Endung .rtf, enthält aber keinen RTF-Header.", file_path)

    text = _RTF_UNICODE_ESCAPE.sub(" ", raw_text)
    text = _RTF_HEX_ESCAPE.sub("", text)
    text = _RTF_CONTROL_WORD.sub("", text)
    text = _RTF_GROUP_MARKERS.sub("", text)
    text = text.replace("\\par", "\n").replace("\\line", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    combined_text = text.strip()

    if not combined_text:
        raise UnreadableContractFileError(
            f"Aus der RTF-Datei '{file_path}' konnte kein Text extrahiert werden. "
            "Bitte exportieren Sie das Dokument alternativ als .docx oder .txt."
        )
    return combined_text


# ---------------------------------------------------------------------------
# Zentrale Zuordnung: Dateiendung -> Extraktionsfunktion
# ---------------------------------------------------------------------------

PARSERS = {
    ".txt": parse_txt,
    ".csv": parse_csv,
    ".pdf": parse_pdf,
    ".docx": parse_docx,
    ".xlsx": parse_xlsx,
    ".pptx": parse_pptx,
    ".odt": parse_odt,
    ".rtf": parse_rtf,
}
