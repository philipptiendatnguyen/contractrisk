"""
analysis/consistency_checker.py
-----------------------------------
Erkennt Widersprüche innerhalb eines Vertragstexts: wird ein zentraler
Wert (z. B. eine Kündigungsfrist, eine Laufzeit oder ein monatlicher
Preis) an mehreren Stellen im Text mit UNTERSCHIEDLICHEN Werten genannt,
ist das ein starkes, gut belegbares Indiz für eine unklare oder
widersprüchliche Vertragsgestaltung - unabhängig von einzelnen
Schlagwörtern.

Diese Prüfung ergänzt die musterbasierte Regel-Engine (rule_engine.py)
um eine Analyseform, die eine einzelne Regel strukturell nicht leisten
kann: den Vergleich mehrerer Fundstellen im gesamten Dokument
untereinander.

Jeder gefundene Widerspruch wird als `RiskFinding` mit Konfidenz "mittel"
zurückgegeben (nicht "hoch"), weil zwei unterschiedliche Zahlenwerte für
denselben Begriff zwar auffällig, aber nicht zwangsläufig fehlerhaft
sind (z. B. könnten sich unterschiedliche Fristen auf unterschiedliche
Vertragsteile beziehen) - die Fundstelle wird transparent mit beiden
Textausschnitten belegt, damit sich der Nutzer selbst ein Bild machen kann.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from contractrisk.domain.models import RiskFinding
from contractrisk.utils.logger import get_logger

logger = get_logger(__name__)

_UNIT_NORMALIZATION = {
    "tag": 1, "tage": 1, "tagen": 1,
    "woche": 7, "wochen": 7,
    "monat": 30, "monate": 30, "monaten": 30,
    "jahr": 365, "jahre": 365, "jahren": 365,
}


@dataclass
class _NumericMention:
    raw_text: str
    normalized_days: float
    start_index: int
    end_index: int


@dataclass
class _ConsistencyTerm:
    """Definiert einen im Vertrag üblicherweise nur EINMAL sinnvoll
    vorkommenden Wert, der auf widersprüchliche Wiederholungen geprüft
    wird."""

    bezeichnung: str
    kategorie: str
    pattern: re.Pattern
    is_currency: bool = False


_CONSISTENCY_TERMS = [
    _ConsistencyTerm(
        bezeichnung="Kündigungsfrist",
        kategorie="Widersprüchliche Kündigungsfrist",
        pattern=re.compile(
            r"K(ü|ue)ndigungsfrist\s+von\s+(?P<amount>\d+|[a-zäöüß]+)\s+"
            r"(?P<unit>Tag[en]*|Woche[n]?|Monat[en]*|Jahr[en]*)",
            re.IGNORECASE,
        ),
    ),
    _ConsistencyTerm(
        bezeichnung="Vertragslaufzeit",
        kategorie="Widersprüchliche Laufzeitangabe",
        pattern=re.compile(
            r"(Mindestvertragslaufzeit|Vertragslaufzeit)\s+von\s+"
            r"(?P<amount>\d+|[a-zäöüß]+)\s+(?P<unit>Monat[en]*|Jahr[en]*)",
            re.IGNORECASE,
        ),
    ),
    _ConsistencyTerm(
        bezeichnung="Monatliche Gebühr",
        kategorie="Widersprüchliche Preisangabe",
        pattern=re.compile(
            r"(monatliche[n]?\s+(Nutzungsgeb(ü|ue)hr|Geb(ü|ue)hr|Preis|Betrag))"
            r"\s+betr(ä|ae)gt\s+(?P<amount>[\d.,]+)\s*(EUR|€|Euro)",
            re.IGNORECASE,
        ),
        is_currency=True,
    ),
]

_WORD_TO_NUMBER = {
    "ein": 1, "eine": 1, "einem": 1, "einen": 1,
    "zwei": 2, "drei": 3, "vier": 4, "fünf": 5, "funf": 5,
    "sechs": 6, "sieben": 7, "acht": 8, "neun": 9, "zehn": 10,
    "elf": 11, "zwölf": 12, "zwolf": 12,
}


def _parse_amount(raw: str) -> float | None:
    raw = raw.strip().lower().replace(".", "").replace(",", ".")
    try:
        return float(raw)
    except ValueError:
        return _WORD_TO_NUMBER.get(raw)


def _normalize_days(amount: float, unit: str) -> float:
    unit_lower = unit.lower()
    for key, factor in _UNIT_NORMALIZATION.items():
        if unit_lower.startswith(key):
            return amount * factor
    return amount


def _find_mentions(text: str, term: _ConsistencyTerm) -> list[_NumericMention]:
    mentions: list[_NumericMention] = []
    for match in term.pattern.finditer(text):
        amount = _parse_amount(match.group("amount"))
        if amount is None:
            continue

        if term.is_currency:
            normalized_value = amount  # Beträge werden direkt verglichen (in EUR)
        else:
            unit = match.group("unit")
            normalized_value = _normalize_days(amount, unit)

        mentions.append(
            _NumericMention(
                raw_text=match.group(0),
                normalized_days=normalized_value,
                start_index=match.start(),
                end_index=match.end(),
            )
        )
    return mentions


def detect_contradictions(text: str) -> list[RiskFinding]:
    """Prüft zentrale, wiederkehrende Vertragsangaben (Kündigungsfrist,
    Laufzeit, monatliche Gebühr) auf widersprüchliche Mehrfachnennungen
    im Dokument und liefert entsprechende `RiskFinding`-Objekte."""
    findings: list[RiskFinding] = []

    for term in _CONSISTENCY_TERMS:
        mentions = _find_mentions(text, term)
        if len(mentions) < 2:
            continue

        first_mention = mentions[0]
        for later_mention in mentions[1:]:
            # Toleranz: identische oder sehr ähnliche Werte (z. B. Rundungs-
            # differenzen bei Beträgen) gelten nicht als Widerspruch.
            values_differ = (
                abs(later_mention.normalized_days - first_mention.normalized_days)
                > max(first_mention.normalized_days * 0.01, 0.01)
            )
            if not values_differ:
                continue

            findings.append(
                RiskFinding(
                    rule_id=f"consistency_{term.bezeichnung.lower().replace(' ', '_')}",
                    kategorie=term.kategorie,
                    schweregrad="hoch",
                    erklaerung=(
                        f"Der Begriff „{term.bezeichnung}“ wird im Dokument mit "
                        f"unterschiedlichen Werten genannt. Dies kann auf einen "
                        f"echten Widerspruch, eine veraltete Textpassage oder "
                        f"bewusst unterschiedliche Regelungen für verschiedene "
                        f"Vertragsteile hindeuten - eine manuelle Prüfung wird "
                        f"empfohlen."
                    ),
                    fundstelle_text=f"„{first_mention.raw_text}“ ⟷ „{later_mention.raw_text}“",
                    start_index=later_mention.start_index,
                    end_index=later_mention.end_index,
                    confidence="mittel",
                    begruendung=(
                        f"An einer früheren Textstelle wurde „{first_mention.raw_text}“ "
                        f"genannt, hier hingegen „{later_mention.raw_text}“ - beide "
                        f"Angaben beziehen sich auf denselben Begriff „{term.bezeichnung}“, "
                        f"unterscheiden sich aber im Wert. Konfidenz ist bewusst auf "
                        f"„mittel“ gesetzt, da unterschiedliche Regelungen im Einzelfall "
                        f"auch beabsichtigt sein können."
                    ),
                )
            )

    if findings:
        logger.info("Widerspruchsprüfung: %d mögliche(r) Widerspruch/Widersprüche gefunden", len(findings))
    return findings
