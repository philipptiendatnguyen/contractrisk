"""
tests/test_rule_engine.py
----------------------------
Unit-Tests für das Laden der Regelbibliothek und den Textscan.
"""

from __future__ import annotations

import json
import os
import tempfile
import unittest

from contractrisk.analysis.rule_engine import load_rules, scan_contract_text
from contractrisk.domain.models import Rule
from contractrisk.utils.exceptions import InvalidRuleConfigError


class TestLoadRules(unittest.TestCase):
    def _write_temp_rules_file(self, content: dict) -> str:
        fd, path = tempfile.mkstemp(suffix=".json")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(content, f)
        self.addCleanup(lambda: os.remove(path))
        return path

    def test_load_valid_rules(self) -> None:
        path = self._write_temp_rules_file({
            "rules": [
                {
                    "id": "test_rule",
                    "kategorie": "Testkategorie",
                    "schweregrad": "hoch",
                    "beschreibung": "Testbeschreibung",
                    "muster": ["Testmuster"],
                    "aktiv": True,
                }
            ]
        })
        rules = load_rules(path)
        self.assertEqual(len(rules), 1)
        self.assertEqual(rules[0].id, "test_rule")

    def test_missing_field_raises(self) -> None:
        path = self._write_temp_rules_file({
            "rules": [{"id": "x", "kategorie": "y", "schweregrad": "hoch", "muster": ["a"]}]
        })
        with self.assertRaises(InvalidRuleConfigError):
            load_rules(path)

    def test_invalid_severity_raises(self) -> None:
        path = self._write_temp_rules_file({
            "rules": [{
                "id": "x", "kategorie": "y", "schweregrad": "kritisch",
                "beschreibung": "z", "muster": ["a"],
            }]
        })
        with self.assertRaises(InvalidRuleConfigError):
            load_rules(path)

    def test_invalid_regex_raises(self) -> None:
        path = self._write_temp_rules_file({
            "rules": [{
                "id": "x", "kategorie": "y", "schweregrad": "hoch",
                "beschreibung": "z", "muster": ["(unclosed"],
            }]
        })
        with self.assertRaises(InvalidRuleConfigError):
            load_rules(path)

    def test_missing_file_raises(self) -> None:
        with self.assertRaises(InvalidRuleConfigError):
            load_rules("/pfad/der/nicht/existiert.json")

    def test_invalid_json_raises(self) -> None:
        fd, path = tempfile.mkstemp(suffix=".json")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write("{ kein gueltiges json")
        self.addCleanup(lambda: os.remove(path))
        with self.assertRaises(InvalidRuleConfigError):
            load_rules(path)


class TestScanContractText(unittest.TestCase):
    def setUp(self) -> None:
        self.rule = Rule(
            id="auto_renewal",
            kategorie="Automatische Verlängerung",
            schweregrad="hoch",
            beschreibung="Testbeschreibung",
            muster=[r"verl(ä|ae)ngert sich automatisch"],
        )

    def test_finds_matching_clause(self) -> None:
        text = "Der Vertrag verlängert sich automatisch um 12 Monate."
        findings = scan_contract_text(text, [self.rule])
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].kategorie, "Automatische Verlängerung")

    def test_no_match_returns_empty_list(self) -> None:
        text = "Dies ist ein völlig unauffälliger Vertragstext."
        findings = scan_contract_text(text, [self.rule])
        self.assertEqual(findings, [])

    def test_inactive_rule_is_ignored(self) -> None:
        inactive_rule = Rule(
            id="inactive", kategorie="X", schweregrad="hoch",
            beschreibung="Y", muster=["verlängert"], aktiv=False,
        )
        text = "Der Vertrag verlängert sich."
        findings = scan_contract_text(text, [inactive_rule])
        self.assertEqual(findings, [])

    def test_multiple_matches_of_same_rule(self) -> None:
        rule = Rule(
            id="haftung", kategorie="Haftungsausschluss", schweregrad="mittel",
            beschreibung="Y", muster=["Haftung ist ausgeschlossen"],
        )
        text = (
            "Für Schäden A: Haftung ist ausgeschlossen. "
            "Für Schäden B: Haftung ist ausgeschlossen."
        )
        findings = scan_contract_text(text, [rule])
        self.assertEqual(len(findings), 2)


class TestConfidenceAssessment(unittest.TestCase):
    """Prüft die kontextbezogene Konfidenzbewertung (Reduzierung von
    Fehlalarmen durch Verneinungs-/Ermessens-Erkennung)."""

    def setUp(self) -> None:
        self.rule = Rule(
            id="auto_renewal", kategorie="Automatische Verlängerung",
            schweregrad="hoch", beschreibung="Testbeschreibung",
            muster=[r"verl(ä|ae)ngert sich .{0,20}automatisch"],
        )

    def test_negation_reduces_confidence_to_niedrig(self) -> None:
        text = "Es besteht keine Klausel: verlängert sich automatisch um 12 Monate."
        findings = scan_contract_text(text, [self.rule])
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].confidence, "niedrig")
        self.assertIn("Verneinung", findings[0].begruendung)

    def test_plain_match_has_high_confidence(self) -> None:
        text = "Der Vertrag verlängert sich automatisch um 12 Monate."
        findings = scan_contract_text(text, [self.rule])
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].confidence, "hoch")

    def test_hedge_word_reduces_confidence_to_mittel(self) -> None:
        text = "Es kann sein, dass verlängert sich automatisch dieser Vertrag."
        findings = scan_contract_text(text, [self.rule])
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].confidence, "mittel")

    def test_every_finding_has_nonempty_begruendung(self) -> None:
        text = "Der Vertrag verlängert sich automatisch um 12 Monate."
        findings = scan_contract_text(text, [self.rule])
        self.assertTrue(findings[0].begruendung.strip())


if __name__ == "__main__":
    unittest.main()
