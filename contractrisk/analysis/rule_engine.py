"""
analysis/rule_engine.py
------------------------
Kern der regelbasierten Textanalyse.

Wichtiges Architekturprinzip: Diese Datei enthält KEINE hartkodierten
Klausel-Beispiele. Sämtliche Muster stammen ausschließlich aus der
Konfigurationsdatei `data/rules.json` und werden zur Laufzeit geladen.
Das erlaubt es, die Regelbibliothek zu erweitern, ohne Code zu ändern.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

from contractrisk.config import NEGATION_LOOKBEHIND_CHARS, RULES_FILE_PATH
from contractrisk.domain.models import Rule, RiskFinding
from contractrisk.utils.exceptions import InvalidRuleConfigError
from contractrisk.utils.logger import get_logger

logger = get_logger(__name__)

_REQUIRED_RULE_FIELDS = {"id", "kategorie", "schweregrad", "beschreibung", "muster"}
_VALID_SEVERITIES = {"niedrig", "mittel", "hoch"}

# ---------------------------------------------------------------------------
# Kontextbezogene Konfidenzbewertung (Reduzierung von Fehlalarmen)
# ---------------------------------------------------------------------------
#
# Ein reiner Keyword-/Regex-Treffer sagt noch nichts darüber aus, ob eine
# Formulierung im konkreten Satz tatsächlich ein Risiko darstellt. Zwei
# einfache, transparente Heuristiken schätzen daher den unmittelbaren
# Kontext VOR dem eigentlichen Treffer ein:
#
# 1. Verneinungswörter ("nicht", "kein" ...) kurz vor dem Treffer deuten
#    darauf hin, dass die riskante Formulierung im Satz gerade AUSGE-
#    SCHLOSSEN wird (z. B. "Es besteht KEINE automatische Verlängerung").
#    Solche Treffer werden nicht verworfen (das wäre eine unbegründete
#    Unterdrückung), sondern mit reduzierter Konfidenz "niedrig" markiert
#    und im Report/GUI transparent als prüfungsbedürftig gekennzeichnet.
#
# 2. Ermessens-/Unsicherheitswörter ("kann", "gegebenenfalls" ...) deuten
#    auf einen Spielraum hin, der die Tragweite der Klausel unklar macht -
#    solche Treffer erhalten Konfidenz "mittel".
#
# Beide Heuristiken sind bewusst einfach und werden im Ergebnis offen als
# Heuristik benannt (siehe RiskFinding.begruendung) - es wird keine
# unbegründete Sicherheit vorgetäuscht.
_NEGATION_MARKERS = (
    "nicht", "kein", "keine", "keinen", "keiner", "keines",
    "niemals", "zu keinem zeitpunkt", "ohne dass", "es sei denn",
    "ausgenommen", "ausgeschlossen ist eine",
)
_HEDGE_MARKERS = (
    "kann", "könnte", "unter umständen", "gegebenenfalls",
    "im einzelfall", "nach ermessen", "vorbehaltlich", "ggf.",
)


def _assess_match_confidence(text: str, match_start: int) -> tuple[str, str]:
    """Untersucht den Text unmittelbar VOR einem Regel-Treffer auf
    Verneinungs- oder Ermessens-Marker und liefert (Konfidenzstufe,
    erklärender Zusatzhinweis)."""
    window_start = max(0, match_start - NEGATION_LOOKBEHIND_CHARS)
    preceding_text = text[window_start:match_start].lower()

    for marker in _NEGATION_MARKERS:
        if re.search(rf"(?<!\w){re.escape(marker)}(?!\w)", preceding_text):
            return (
                "niedrig",
                f" Hinweis zur Konfidenz: Im Satz vor dieser Textstelle wurde das "
                f"Wort „{marker}“ gefunden, das häufig eine Verneinung oder "
                f"Einschränkung ausdrückt. Die Einstufung als Risiko ist daher "
                f"unsicher und sollte manuell geprüft werden.",
            )

    for marker in _HEDGE_MARKERS:
        if re.search(rf"(?<!\w){re.escape(marker)}(?!\w)", preceding_text):
            return (
                "mittel",
                f" Hinweis zur Konfidenz: Die Formulierung „{marker}“ im Kontext "
                f"deutet auf einen Ermessens- oder Unsicherheitsspielraum hin - "
                f"die tatsächliche Tragweite hängt vom Einzelfall ab.",
            )

    return "hoch", ""


@dataclass
class _CompiledRule:
    """Eine Regel mit bereits kompilierten Regex-Mustern (Performance:
    Muster werden einmal beim Laden kompiliert statt bei jedem Scan neu
    geparst)."""

    rule: Rule
    compiled_patterns: list[re.Pattern]


def _validate_raw_rule(raw_rule: dict, index: int) -> None:
    missing = _REQUIRED_RULE_FIELDS - raw_rule.keys()
    if missing:
        raise InvalidRuleConfigError(
            f"Regel #{index} fehlen Pflichtfelder: {', '.join(sorted(missing))}."
        )

    if raw_rule["schweregrad"] not in _VALID_SEVERITIES:
        raise InvalidRuleConfigError(
            f"Regel '{raw_rule.get('id', index)}' hat einen ungültigen "
            f"Schweregrad '{raw_rule['schweregrad']}'. Erlaubt: "
            f"{', '.join(sorted(_VALID_SEVERITIES))}."
        )

    if not isinstance(raw_rule["muster"], list) or not raw_rule["muster"]:
        raise InvalidRuleConfigError(
            f"Regel '{raw_rule['id']}' benötigt mindestens ein Muster in 'muster'."
        )


def load_rules(rules_file_path: str = RULES_FILE_PATH) -> list[Rule]:
    """Lädt und validiert die Regelbibliothek aus der JSON-Datei.

    Wirft `InvalidRuleConfigError` mit einer präzisen Fehlermeldung, wenn
    die Datei fehlt, kein gültiges JSON enthält oder einzelne Regeln
    fehlerhaft sind (z. B. ungültige Regex).
    """
    try:
        with open(rules_file_path, "r", encoding="utf-8") as f:
            raw_data = json.load(f)
    except FileNotFoundError as exc:
        raise InvalidRuleConfigError(
            f"Regeldatei nicht gefunden: '{rules_file_path}'."
        ) from exc
    except json.JSONDecodeError as exc:
        raise InvalidRuleConfigError(
            f"Regeldatei enthält kein gültiges JSON: {exc}"
        ) from exc

    raw_rules = raw_data.get("rules")
    if not isinstance(raw_rules, list) or not raw_rules:
        raise InvalidRuleConfigError(
            "Regeldatei muss ein nicht-leeres Feld 'rules' (Liste) enthalten."
        )

    rules: list[Rule] = []
    for index, raw_rule in enumerate(raw_rules):
        _validate_raw_rule(raw_rule, index)

        # Jedes Regex-Muster wird auf Kompilierbarkeit geprüft. Fehlerhafte
        # Muster führen zu einer klaren Fehlermeldung statt zu einem Absturz.
        for pattern in raw_rule["muster"]:
            try:
                re.compile(pattern, flags=re.IGNORECASE | re.DOTALL)
            except re.error as exc:
                raise InvalidRuleConfigError(
                    f"Regel '{raw_rule['id']}' enthält ein ungültiges "
                    f"Regex-Muster '{pattern}': {exc}"
                ) from exc

        rules.append(
            Rule(
                id=raw_rule["id"],
                kategorie=raw_rule["kategorie"],
                schweregrad=raw_rule["schweregrad"],
                beschreibung=raw_rule["beschreibung"],
                muster=raw_rule["muster"],
                aktiv=raw_rule.get("aktiv", True),
                typ=raw_rule.get("typ", "vertragsklausel"),
            )
        )

    logger.info("Regelbibliothek geladen: %d Regeln", len(rules))
    return rules


def _compile_rules(rules: list[Rule]) -> list[_CompiledRule]:
    """Kompiliert alle aktiven Regeln einmalig (Performance-Optimierung)."""
    compiled: list[_CompiledRule] = []
    for rule in rules:
        if not rule.aktiv:
            continue
        # re.DOTALL sorgt dafür, dass "." auch Zeilenumbrüche innerhalb
        # eines Satzes überbrückt (Verträge werden oft mit Zeilenumbrüchen
        # mitten im Satz kopiert/formatiert).
        patterns = [re.compile(p, flags=re.IGNORECASE | re.DOTALL) for p in rule.muster]
        compiled.append(_CompiledRule(rule=rule, compiled_patterns=patterns))
    return compiled


def _extract_sentence_context(text: str, match_start: int, match_end: int) -> str:
    """Erweitert den Treffer auf den umgebenden Satz/Absatz, damit der
    Nutzer die Klausel im Kontext sieht statt nur des nackten Schlagworts."""
    # Suche den vorherigen Satzanfang (nach '.', '!', '?' oder Zeilenumbruch)
    left_boundary = 0
    for sep_pos in range(match_start - 1, -1, -1):
        if text[sep_pos] in ".!?\n" and sep_pos < match_start - 1:
            left_boundary = sep_pos + 1
            break

    # Suche das nächste Satzende
    right_boundary = len(text)
    for sep_pos in range(match_end, len(text)):
        if text[sep_pos] in ".!?\n":
            right_boundary = sep_pos + 1
            break

    return text[left_boundary:right_boundary].strip()


def scan_contract_text(text: str, rules: list[Rule]) -> list[RiskFinding]:
    """Durchsucht den übergebenen Vertragstext anhand aller aktiven Regeln
    und liefert eine Liste von `RiskFinding`-Objekten.

    Pro Regel wird jeder Treffer einzeln erfasst (auch mehrere Treffer
    derselben Regel im selben Text), damit der Scoring-Algorithmus die
    tatsächliche Häufigkeit berücksichtigen kann.
    """
    compiled_rules = _compile_rules(rules)
    findings: list[RiskFinding] = []

    for compiled_rule in compiled_rules:
        rule = compiled_rule.rule
        # Sammelt bereits erfasste Textbereiche DIESER Regel, damit dieselbe
        # Klausel nicht mehrfach gezählt wird, nur weil mehrere Muster der
        # Regel denselben (oder einen überlappenden) Satzteil treffen.
        already_covered_spans: list[tuple[int, int]] = []

        for pattern in compiled_rule.compiled_patterns:
            for match in pattern.finditer(text):
                match_start, match_end = match.start(), match.end()

                overlaps_existing = any(
                    match_start < covered_end and match_end > covered_start
                    for covered_start, covered_end in already_covered_spans
                )
                if overlaps_existing:
                    continue

                already_covered_spans.append((match_start, match_end))
                context = _extract_sentence_context(text, match_start, match_end)
                confidence, confidence_hint = _assess_match_confidence(text, match_start)
                begruendung = (
                    f"Die Formulierung entspricht dem Muster der Kategorie "
                    f"„{rule.kategorie}“ (Regel: {rule.id})." + confidence_hint
                )
                findings.append(
                    RiskFinding(
                        rule_id=rule.id,
                        kategorie=rule.kategorie,
                        schweregrad=rule.schweregrad,
                        erklaerung=rule.beschreibung,
                        fundstelle_text=context,
                        start_index=match_start,
                        end_index=match_end,
                        confidence=confidence,
                        begruendung=begruendung,
                        typ=rule.typ,
                    )
                )

    findings.sort(key=lambda f: f.start_index)
    logger.info("Textscan abgeschlossen: %d Treffer gefunden", len(findings))
    return findings
