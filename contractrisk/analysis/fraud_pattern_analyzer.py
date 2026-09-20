"""
analysis/fraud_pattern_analyzer.py
--------------------------------------
Kombinationsanalyse für Betrugs-/Scam-Indikatoren.

Ein einzelnes verdächtiges Merkmal (z. B. künstliche Dringlichkeit) kommt
auch in legitimen, nur unhöflich formulierten Texten vor und ist für sich
allein kein verlässlicher Betrugsbeweis. Treten jedoch MEHRERE, inhaltlich
UNABHÄNGIGE Betrugsmuster im selben Dokument gemeinsam auf (z. B.
künstlicher Zeitdruck UND eine ungewöhnliche Zahlungsmethode UND eine
Vorabgebühr), ist das ein anerkannt starkes, gut belegbares Warnsignal -
diese Kombinationslogik wird von klassischen Betrugspräventions-
Checklisten (z. B. Verbraucherzentralen, BSI) genau so verwendet.

Diese Prüfung erzeugt daher einen zusätzlichen, klar erklärten
"Mehrfachindikator"-Fund, WENN UND NUR WENN mindestens
`config.MIN_COMBINED_FRAUD_INDICATORS` unterschiedliche Betrugs-Regeln
(nicht nur mehrere Treffer derselben Regel) im Dokument angeschlagen
haben. Die Begründung listet transparent auf, welche Kategorien
zusammengetroffen sind - es wird keine unbegründete "KI-Einschätzung"
vorgetäuscht, sondern eine nachvollziehbare, zählbare Kombinationsregel
angewendet.
"""

from __future__ import annotations

from contractrisk.config import MIN_COMBINED_FRAUD_INDICATORS
from contractrisk.domain.models import RiskFinding
from contractrisk.utils.logger import get_logger

logger = get_logger(__name__)


def detect_combined_fraud_signals(findings: list[RiskFinding]) -> list[RiskFinding]:
    """Prüft, ob mehrere unterschiedliche Betrugsmuster gleichzeitig im
    Dokument gefunden wurden, und liefert bei Bedarf einen zusätzlichen,
    aggregierten `RiskFinding` mit hoher Konfidenz zurück (sonst eine
    leere Liste - es wird nichts erzwungen)."""
    fraud_findings = [f for f in findings if f.typ == "betrug"]
    if not fraud_findings:
        return []

    # Nach KATEGORIE gruppieren (nicht nach rule_id), damit zwei Treffer
    # derselben Regel nicht fälschlich als "zwei unabhängige Indikatoren"
    # gezählt werden.
    categories_involved: dict[str, RiskFinding] = {}
    for finding in fraud_findings:
        categories_involved.setdefault(finding.kategorie, finding)

    if len(categories_involved) < MIN_COMBINED_FRAUD_INDICATORS:
        return []

    category_names = sorted(categories_involved.keys())
    first_finding = min(fraud_findings, key=lambda f: f.start_index)

    combined_finding = RiskFinding(
        rule_id="combined_fraud_signal",
        kategorie="Mehrere gleichzeitige Betrugsindikatoren",
        schweregrad="hoch",
        erklaerung=(
            f"Im Dokument wurden {len(categories_involved)} inhaltlich "
            f"unabhängige Betrugs-/Scam-Muster gleichzeitig gefunden: "
            f"{', '.join(category_names)}. Das gemeinsame Auftreten mehrerer "
            f"unabhängiger Warnsignale gilt als deutlich stärkeres Indiz für "
            f"einen Betrugsversuch als ein einzelnes Muster allein."
        ),
        fundstelle_text=first_finding.fundstelle_text,
        start_index=first_finding.start_index,
        end_index=first_finding.end_index,
        confidence="hoch",
        begruendung=(
            f"Diese Einstufung basiert auf einer nachvollziehbaren Zählregel: "
            f"{len(categories_involved)} verschiedene, im Dokument tatsächlich "
            f"gefundene Betrugskategorien ({', '.join(category_names)}) treten "
            f"gemeinsam auf. Jede einzelne Kategorie ist an ihrer eigenen "
            f"Fundstelle im Dokument separat belegt und nachprüfbar."
        ),
        typ="betrug",
    )

    logger.info(
        "Kombinationsanalyse: %d unabhängige Betrugsindikatoren gemeinsam gefunden (%s)",
        len(categories_involved), ", ".join(category_names),
    )
    return [combined_finding]
