"""
domain/models.py
-----------------
Zentrale Datenklassen des ContractRisk Scanners.

Statt lose Dictionaries oder Tupel durch die Anwendung zu reichen,
verwenden wir typisierte `dataclasses`. Das macht den Code selbstdokumen-
tierend und verhindert Tippfehler bei Dictionary-Keys.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional


@dataclass
class Rule:
    """Eine einzelne Regel aus der Regelbibliothek (rules.json)."""

    id: str
    kategorie: str
    schweregrad: str  # "niedrig" | "mittel" | "hoch"
    beschreibung: str
    muster: list[str]  # rohe Regex-Strings, wie in der JSON-Datei hinterlegt
    aktiv: bool = True

    # Klassifiziert die Regel als "vertragsklausel" (rechtlich/wirtschaftlich
    # riskante, aber grundsätzlich legale Klausel) oder "betrug" (typisches
    # Betrugs-/Scam-Muster). Ermöglicht getrennte Scores statt einer
    # vermischten Gesamtzahl (siehe analysis/risk_scoring.split_scores).
    typ: str = "vertragsklausel"

    def __post_init__(self) -> None:
        if self.schweregrad not in ("niedrig", "mittel", "hoch"):
            raise ValueError(
                f"Ungültiger Schweregrad '{self.schweregrad}' in Regel '{self.id}'."
            )
        if self.typ not in ("vertragsklausel", "betrug"):
            raise ValueError(f"Ungültiger Typ '{self.typ}' in Regel '{self.id}'.")


@dataclass
class RiskFinding:
    """Ein einzelner Treffer des Textscans (eine Regel oder ein
    Analysemodul schlägt an einer bestimmten Textstelle an)."""

    rule_id: str
    kategorie: str
    schweregrad: str
    erklaerung: str
    fundstelle_text: str  # der Satz/Ausschnitt, in dem die Klausel gefunden wurde
    start_index: int  # Zeichenindex im Originaltext (für Hervorhebung)
    end_index: int

    # Konfidenzstufe des Fundes: "hoch" | "mittel" | "niedrig". Reduziert
    # sich z. B., wenn der Kontext auf eine Verneinung hindeutet ("KEINE
    # automatische Verlängerung") oder wenn ein Widerspruch nur möglich,
    # aber nicht sicher ist. Niedrige Konfidenz bedeutet NICHT, dass der
    # Fund entfernt wird - er bleibt sichtbar, fließt aber mit reduziertem
    # Gewicht in den Score ein (siehe config.CONFIDENCE_WEIGHTS).
    confidence: str = "hoch"

    # Nachvollziehbare, fundspezifische Begründung, WARUM dieser Treffer
    # als auffällig gilt (ergänzt die allgemeine Regel-Erklärung in
    # `erklaerung` um den konkreten Kontext dieses einzelnen Treffers).
    begruendung: str = ""

    # "vertragsklausel" | "betrug" - siehe Rule.typ
    typ: str = "vertragsklausel"

    def __post_init__(self) -> None:
        if self.confidence not in ("hoch", "mittel", "niedrig"):
            raise ValueError(f"Ungültige Konfidenzstufe '{self.confidence}'.")
        if self.typ not in ("vertragsklausel", "betrug"):
            raise ValueError(f"Ungültiger Typ '{self.typ}'.")
        if not self.begruendung:
            self.begruendung = (
                f"Die Formulierung an dieser Textstelle entspricht dem Muster "
                f"der Kategorie „{self.kategorie}“."
            )


@dataclass
class Deadline:
    """Eine erkannte oder berechnete Frist/ein kritischer Termin."""

    bezeichnung: str  # z. B. "Späteste Kündigung", "Automatische Verlängerung"
    datum: Optional[date]  # None, falls nicht eindeutig berechenbar
    quelle_text: str  # der Textausschnitt, aus dem die Frist abgeleitet wurde
    konnte_berechnet_werden: bool = True
    hinweis: str = ""  # z. B. "nicht automatisch erkannt" bei Unsicherheit


@dataclass
class Contract:
    """Ein importierter Vertrag inkl. Analyseergebnissen."""

    id: Optional[int]  # None, solange der Vertrag noch nicht in der DB liegt
    dateiname: str
    originaltext: str
    importiert_am: datetime
    vertragsbeginn: Optional[date] = None
    quellformat: str = ""  # z. B. "PDF-Dokument", "Word-Dokument (docx)"

    risk_score: float = 0.0
    risk_level: str = "niedrig"  # "niedrig" | "mittel" | "hoch"

    # Getrennte Scores nach Fundtyp (siehe Rule.typ): ermöglichen eine
    # präzisere Aussage als ein einzelner Gesamt-Score, da Vertragsklauseln
    # und Betrugsmuster unterschiedliche Risikoarten darstellen.
    vertrags_risiko_score: float = 0.0
    betrugs_risiko_score: float = 0.0

    findings: list[RiskFinding] = field(default_factory=list)
    deadlines: list[Deadline] = field(default_factory=list)

    @property
    def anzahl_woerter(self) -> int:
        return len(self.originaltext.split())

    @property
    def anzahl_klauseln(self) -> int:
        return len(self.findings)

    @property
    def anzahl_betrugsindikatoren(self) -> int:
        return len([f for f in self.findings if f.typ == "betrug"])

    @property
    def naechster_kritischer_termin(self) -> Optional[date]:
        """Liefert das nächste (chronologisch früheste) noch bevorstehende
        Datum aus allen erkannten Fristen, oder None."""
        heute = date.today()
        kommende = [
            d.datum for d in self.deadlines
            if d.datum is not None and d.datum >= heute
        ]
        return min(kommende) if kommende else None
