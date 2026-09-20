"""
io_utils/report_writer.py
---------------------------
Erzeugt einen strukturierten, menschenlesbaren Risiko-Report als
Textdatei für einen einzelnen Vertrag.
"""

from __future__ import annotations

import os
from datetime import date, datetime

from contractrisk.config import DISCLAIMER_TEXT, EXPORT_DIR, FINDING_TYPE_LABELS
from contractrisk.domain.models import Contract
from contractrisk.utils.exceptions import ReportExportError
from contractrisk.utils.logger import get_logger

logger = get_logger(__name__)

_SEPARATOR = "=" * 72


def _format_date(d: date | None) -> str:
    return d.strftime("%d.%m.%Y") if d else "nicht automatisch erkannt"


_CONFIDENCE_LABELS = {
    "hoch": "Hoch (eindeutiger Treffer)",
    "mittel": "Mittel (Kontext prüfen)",
    "niedrig": "Niedrig (möglicher Fehlalarm - bitte manuell prüfen)",
}


def _format_finding_block(index: int, finding) -> list[str]:
    type_label = FINDING_TYPE_LABELS.get(finding.typ, finding.typ)
    return [
        "",
        f"[{index}] Kategorie:    {finding.kategorie}  ({type_label})",
        f"    Schweregrad:  {finding.schweregrad.upper()}",
        f"    Konfidenz:    {_CONFIDENCE_LABELS.get(finding.confidence, finding.confidence)}",
        f"    Erklärung:    {finding.erklaerung}",
        f"    Begründung:   {finding.begruendung}",
        f"    Fundstelle:   \"{finding.fundstelle_text}\"",
    ]


def build_report_text(contract: Contract) -> str:
    """Baut den vollständigen Report-Inhalt als String zusammen."""
    lines: list[str] = []
    append = lines.append

    append(_SEPARATOR)
    append(f"RISIKO-REPORT: {contract.dateiname}")
    append(_SEPARATOR)
    append("")
    append(f"Importiert am:            {contract.importiert_am.strftime('%d.%m.%Y %H:%M')}")
    if contract.quellformat:
        append(f"Quellformat:              {contract.quellformat}")
    append(f"Wortanzahl:               {contract.anzahl_woerter}")
    append("")
    append(f"Vertragsrisiko-Score:     {contract.vertrags_risiko_score:.1f} / 100")
    append(f"Betrugs-/Scam-Score:      {contract.betrugs_risiko_score:.1f} / 100")
    append(f"Gesamt-Risiko-Score:      {contract.risk_score:.1f} / 100  ({contract.risk_level.upper()})")
    append(f"Anzahl Auffälligkeiten:   {contract.anzahl_klauseln}"
           f" (davon {contract.anzahl_betrugsindikatoren} Betrugsindikator(en))")
    append("")
    append(
        "Hinweis: Vertragsrisiko und Betrugs-/Scam-Risiko werden bewusst "
        "getrennt ausgewiesen, da es sich um unterschiedliche Risikoarten "
        "handelt (siehe Abschnitt unten)."
    )
    append("")

    # Findings werden nach Konfidenz gruppiert dargestellt: zuerst die
    # eindeutigen ("hoch") und mittleren Treffer, danach separat die
    # Treffer mit niedriger Konfidenz - damit auf den ersten Blick klar
    # ist, welche Befunde besonders belastbar sind und welche eine
    # manuelle Prüfung erfordern (keine unbegründete Gleichsetzung aller
    # Funde).
    confirmed_findings = [f for f in contract.findings if f.confidence in ("hoch", "mittel")]
    uncertain_findings = [f for f in contract.findings if f.confidence == "niedrig"]

    append("-" * 72)
    append("ERKANNTE RISIKEN, BETRUGSMUSTER UND AUFFÄLLIGKEITEN")
    append("-" * 72)
    if not confirmed_findings:
        append("Keine Auffälligkeiten mit hoher oder mittlerer Konfidenz gefunden.")
    else:
        for i, finding in enumerate(confirmed_findings, start=1):
            lines.extend(_format_finding_block(i, finding))

    if uncertain_findings:
        append("")
        append("-" * 72)
        append("UNKLARE BEFUNDE (niedrige Konfidenz - bitte manuell prüfen)")
        append("-" * 72)
        append(
            "Die folgenden Textstellen entsprechen zwar einem Risikomuster, der "
            "unmittelbare Kontext (z. B. eine erkannte Verneinung) deutet aber "
            "darauf hin, dass es sich möglicherweise NICHT um ein tatsächliches "
            "Risiko handelt. Diese Funde werden aus Transparenzgründen "
            "angezeigt, aber nur mit reduziertem Gewicht in den Risiko-Score "
            "einbezogen."
        )
        for i, finding in enumerate(uncertain_findings, start=1):
            lines.extend(_format_finding_block(i, finding))

    append("")
    append("-" * 72)
    append("FRISTEN-PROGNOSE")
    append("-" * 72)
    if not contract.deadlines:
        append("Keine Fristformulierungen im Text erkannt.")
    else:
        for deadline in contract.deadlines:
            append("")
            append(f"Bezeichnung:  {deadline.bezeichnung}")
            append(f"Datum:        {_format_date(deadline.datum)}")
            append(f"Quelle:       \"{deadline.quelle_text}\"")
            if deadline.hinweis:
                append(f"Hinweis:      {deadline.hinweis}")

    append("")
    append(_SEPARATOR)
    append(DISCLAIMER_TEXT)
    append(
        "Alle oben genannten Befunde basieren auf regelbasierter Muster- und "
        "Kontexterkennung und stellen KEINE juristische oder betriebswirtschaftliche "
        "Bewertung dar. Jeder Befund ist mit der konkreten Textstelle sowie einer "
        "nachvollziehbaren Begründung belegt; unklare Fälle sind ausdrücklich als "
        "solche gekennzeichnet."
    )
    append(_SEPARATOR)
    append("")
    append(f"Report erstellt am {datetime.now().strftime('%d.%m.%Y %H:%M')} mit ContractRisk Scanner.")

    return "\n".join(lines)


def export_report(contract: Contract, target_path: str | None = None) -> str:
    """Schreibt den Report in eine Textdatei und liefert den finalen Pfad.

    Wird kein `target_path` übergeben, wird die Datei automatisch im
    Export-Verzeichnis abgelegt. Validiert den Zielpfad, um versehentliches
    Überschreiben außerhalb des vorgesehenen Verzeichnisses zu vermeiden.
    """
    if target_path is None:
        os.makedirs(EXPORT_DIR, exist_ok=True)
        safe_name = os.path.splitext(contract.dateiname)[0]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        target_path = os.path.join(EXPORT_DIR, f"report_{safe_name}_{timestamp}.txt")

    target_path = os.path.abspath(target_path)

    try:
        os.makedirs(os.path.dirname(target_path), exist_ok=True)
        with open(target_path, "w", encoding="utf-8") as f:
            f.write(build_report_text(contract))
    except OSError as exc:
        raise ReportExportError(f"Report konnte nicht geschrieben werden: {exc}") from exc

    logger.info("Report exportiert: %s", target_path)
    return target_path
