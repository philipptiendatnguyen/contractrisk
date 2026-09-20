"""
analysis/risk_scoring.py
-------------------------
Berechnung des Gesamt-Risiko-Scores eines Vertrags aus den gefundenen
Risikoklauseln (RiskFinding-Objekten).

Scoring-Formel (siehe `calculate_risk_score` für Details):
Jede gefundene Klausel trägt mit ihrem Schweregrad-Gewicht zum "rohen"
Score bei. Dieser rohe Score wird anschließend auf eine Skala von 0-100
normiert, damit Verträge unterschiedlicher Länge vergleichbar bleiben.
"""

from __future__ import annotations

from contractrisk.config import (
    CONFIDENCE_WEIGHTS,
    MAX_RAW_SCORE_FOR_NORMALIZATION,
    RISK_LEVEL_THRESHOLDS,
    SEVERITY_WEIGHTS,
)
from contractrisk.domain.models import RiskFinding
from contractrisk.utils.logger import get_logger

logger = get_logger(__name__)


def calculate_risk_score(findings: list[RiskFinding]) -> float:
    """Berechnet den normierten Gesamt-Risiko-Score (0-100) aus einer
    Liste von Treffern.

    Vorgehen:
    1. Für jeden Treffer wird das Gewicht seines Schweregrads mit dem
       Gewicht seiner Konfidenzstufe multipliziert (siehe
       `config.CONFIDENCE_WEIGHTS`) und aufsummiert (roher Score). Ein
       Treffer mit niedriger Konfidenz (z. B. durch eine erkannte
       Verneinung im Kontext) fließt dadurch deutlich schwächer in den
       Score ein als ein eindeutiger Treffer - er wird aber weiterhin
       angezeigt, nicht stillschweigend ignoriert.
    2. Der rohe Score wird auf `MAX_RAW_SCORE_FOR_NORMALIZATION` gedeckelt
       und linear auf den Bereich 0-100 skaliert.

    Ein Vertrag ohne Treffer erhält den Score 0.0.
    """
    if not findings:
        return 0.0

    raw_score = 0.0
    for finding in findings:
        severity_weight = SEVERITY_WEIGHTS.get(finding.schweregrad, 1)
        confidence_weight = CONFIDENCE_WEIGHTS.get(finding.confidence, 1.0)
        raw_score += severity_weight * confidence_weight

    raw_score = min(raw_score, MAX_RAW_SCORE_FOR_NORMALIZATION)
    normalized_score = (raw_score / MAX_RAW_SCORE_FOR_NORMALIZATION) * 100

    result = round(normalized_score, 1)
    logger.debug(
        "Risiko-Score berechnet: roh=%.1f -> normiert=%.1f (aus %d Treffern)",
        raw_score, result, len(findings),
    )
    return result


def determine_risk_level(score: float) -> str:
    """Ordnet einen numerischen Score einer Ampel-Kategorie
    ('niedrig' | 'mittel' | 'hoch') zu, basierend auf `RISK_LEVEL_THRESHOLDS`."""
    for level, (lower, upper) in RISK_LEVEL_THRESHOLDS.items():
        if lower <= score <= upper:
            return level
    # Fallback, sollte durch die Konfiguration eigentlich nie erreicht werden
    return "hoch"


def split_scores(findings: list[RiskFinding]) -> tuple[float, float]:
    """Berechnet ZWEI getrennte Scores statt einer vermischten Gesamtzahl:
    einen für Vertragsklausel-Risiken (rechtlich/wirtschaftlich riskante,
    aber grundsätzlich legale Klauseln) und einen für Betrugs-/Scam-
    Indikatoren. Diese Trennung ist präziser als ein einzelner Score, weil
    beide Risikoarten unterschiedliche Konsequenzen haben (eine ungünstige
    Klausel verhandelt man, einen Betrugsversuch bricht man ab) und sich
    ihre Aussagekraft sonst gegenseitig verwässern würde.

    Liefert (vertrags_risiko_score, betrugs_risiko_score), beide 0-100.
    """
    contract_findings = [f for f in findings if f.typ == "vertragsklausel"]
    fraud_findings = [f for f in findings if f.typ == "betrug"]
    return calculate_risk_score(contract_findings), calculate_risk_score(fraud_findings)


def summarize_findings_by_category(findings: list[RiskFinding]) -> dict[str, int]:
    """Liefert eine Übersicht, wie viele Treffer pro Kategorie gefunden
    wurden - nützlich für Report und Detailansicht."""
    summary: dict[str, int] = {}
    for finding in findings:
        summary[finding.kategorie] = summary.get(finding.kategorie, 0) + 1
    return dict(sorted(summary.items(), key=lambda item: item[1], reverse=True))
