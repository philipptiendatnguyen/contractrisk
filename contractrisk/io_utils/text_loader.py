"""
io_utils/text_loader.py
------------------------
Import und Validierung von Vertragsdateien in verschiedensten gängigen
Dokumentformaten (siehe `config.SUPPORTED_DOCUMENT_EXTENSIONS`): .txt,
.csv, .pdf, .docx, .xlsx, .pptx, .odt und .rtf.

Diese Schicht kapselt sämtlichen Dateisystemzugriff und die
formatspezifische Extraktion (delegiert an `io_utils/document_parsers.py`),
damit die restliche Anwendung ausschließlich mit sauberem Text arbeitet
und sich nicht um Encoding- oder Formatdetails kümmern muss.

Formate, die zwar erkannt, aber technisch nicht zuverlässig ausgelesen
werden können (z. B. das alte .doc-Binärformat), führen zu einer klaren,
für den Nutzer verständlichen Fehlermeldung inkl. Handlungsempfehlung -
statt eines rohen Tracebacks oder eines stillen Fehlschlags.
"""

from __future__ import annotations

import os
from datetime import datetime

from contractrisk.config import KNOWN_UNSUPPORTED_EXTENSIONS, SUPPORTED_DOCUMENT_EXTENSIONS
from contractrisk.domain.models import Contract
from contractrisk.io_utils.document_parsers import PARSERS
from contractrisk.utils.exceptions import UnreadableContractFileError, UnsupportedFileFormatError
from contractrisk.utils.logger import get_logger

logger = get_logger(__name__)


def _validate_path_and_extension(file_path: str) -> str:
    """Prüft, dass der Pfad existiert, eine reguläre Datei ist und liefert
    die (kleingeschriebene) Dateiendung zurück. Wirft eine verständliche
    Fehlermeldung für nicht existierende, unbekannte oder bekanntermaßen
    nicht unterstützte Formate."""
    if not os.path.isfile(file_path):
        raise UnreadableContractFileError(
            f"Die Datei '{file_path}' existiert nicht oder ist keine reguläre Datei."
        )

    _, extension = os.path.splitext(file_path)
    extension = extension.lower()

    if extension in KNOWN_UNSUPPORTED_EXTENSIONS:
        raise UnsupportedFileFormatError(
            f"Das Dateiformat '{extension}' wird erkannt, kann aber technisch "
            f"nicht importiert werden: {KNOWN_UNSUPPORTED_EXTENSIONS[extension]}"
        )

    if extension not in SUPPORTED_DOCUMENT_EXTENSIONS:
        supported_list = ", ".join(sorted(SUPPORTED_DOCUMENT_EXTENSIONS))
        raise UnsupportedFileFormatError(
            f"Das Dateiformat '{extension or '(ohne Endung)'}' wird nicht "
            f"unterstützt. Unterstützte Formate: {supported_list}."
        )

    return extension


def load_contract_from_file(file_path: str) -> Contract:
    """Lädt eine einzelne Vertragsdatei - in einem der unterstützten
    Formate - und liefert ein befülltes `Contract`-Objekt (noch ohne
    Scan-Ergebnisse, ohne DB-ID)."""
    extension = _validate_path_and_extension(file_path)

    parser = PARSERS[extension]
    try:
        extracted_text = parser(file_path)
    except UnreadableContractFileError:
        raise
    except Exception as exc:  # Sicherheitsnetz gegen unerwartete Bibliotheksfehler
        raise UnreadableContractFileError(
            f"Die Datei '{file_path}' konnte nicht verarbeitet werden: {exc}"
        ) from exc

    cleaned_text = extracted_text.strip()
    if not cleaned_text:
        raise UnreadableContractFileError(
            f"Die Datei '{file_path}' enthält keinen verwertbaren Text."
        )

    dateiname = os.path.basename(file_path)
    format_label = SUPPORTED_DOCUMENT_EXTENSIONS[extension]
    logger.info(
        "Vertrag geladen: %s (%s, %d Zeichen)", dateiname, format_label, len(cleaned_text)
    )

    return Contract(
        id=None,
        dateiname=dateiname,
        originaltext=cleaned_text,
        importiert_am=datetime.now(),
        quellformat=format_label,
    )


def load_contracts_from_files(file_paths: list[str]) -> tuple[list[Contract], list[str]]:
    """Lädt mehrere Vertragsdateien, ggf. in unterschiedlichen Formaten.

    Gibt ein Tupel zurück: (erfolgreich geladene Verträge, Fehlermeldungen
    für Dateien, die nicht geladen werden konnten). So bricht ein einzelner
    fehlerhafter oder nicht unterstützter Import nicht den gesamten Batch ab.
    """
    contracts: list[Contract] = []
    errors: list[str] = []

    for path in file_paths:
        try:
            contracts.append(load_contract_from_file(path))
        except UnreadableContractFileError as exc:
            logger.warning("Import fehlgeschlagen für %s: %s", path, exc)
            errors.append(f"{os.path.basename(path)}: {exc}")

    return contracts, errors
