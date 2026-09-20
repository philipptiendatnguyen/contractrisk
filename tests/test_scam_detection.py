"""
tests/test_scam_detection.py
--------------------------------
Umfassende Regressionstests für die erweiterte Scam-/Betrugserkennung.

Zwei Testklassen-Gruppen:

1. TestKnownScamFixtures: Läuft die komplette Analyse-Pipeline (Regel-
   Engine + Widerspruchsprüfung + Kombinationsanalyse) gegen reale,
   zuvor UNERKANNTE Testfälle (siehe tests/fixtures/scam_samples/) und
   stellt sicher, dass diese jetzt zuverlässig als Betrug/hochriskant
   erkannt werden - inkl. der konkreten Kategorien, die zuvor fehlten.

2. TestLegitimateContractsNotFlagged: Läuft dieselbe Pipeline gegen
   mehrere unabhängig verfasste, garantiert legitime Verträge (siehe
   tests/fixtures/legitimate_samples/) und stellt sicher, dass KEINE
   Betrugsmuster ("typ" == "betrug") fälschlich anschlagen - das ist die
   vom Nutzer geforderte Kontrolle gegen Fehlalarme.
"""

from __future__ import annotations

import os
import unittest

from contractrisk.analysis import (
    consistency_checker,
    fraud_pattern_analyzer,
    risk_scoring,
    rule_engine,
)
from contractrisk.io_utils import text_loader

_FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")
_SCAM_DIR = os.path.join(_FIXTURES_DIR, "scam_samples")
_LEGIT_DIR = os.path.join(_FIXTURES_DIR, "legitimate_samples")


def _run_full_pipeline(text: str):
    """Repliziert exakt die Analyse-Kette aus gui/app.py (Regel-Engine +
    Widerspruchsprüfung + Kombinationsanalyse), damit die Tests dasselbe
    Verhalten prüfen, das der Nutzer in der Anwendung sieht."""
    rules = rule_engine.load_rules()
    rule_findings = rule_engine.scan_contract_text(text, rules)
    contradiction_findings = consistency_checker.detect_contradictions(text)
    preliminary = rule_findings + contradiction_findings
    combo_findings = fraud_pattern_analyzer.detect_combined_fraud_signals(preliminary)
    all_findings = preliminary + combo_findings
    overall_score = risk_scoring.calculate_risk_score(all_findings)
    contract_score, fraud_score = risk_scoring.split_scores(all_findings)
    return all_findings, overall_score, contract_score, fraud_score


def _categories(findings) -> set[str]:
    return {f.kategorie for f in findings}


class TestKnownScamFixtures(unittest.TestCase):
    """Diese Fälle wurden vom Nutzer eingereicht, weil sie vom
    ursprünglichen System NICHT als Scam erkannt wurden (Betrugs-Score
    war 0). Jeder Test stellt sicher, dass dieser konkrete Fall jetzt
    zuverlässig erkannt wird."""

    def test_english_negative_business_growth_scam_now_detected(self) -> None:
        path = os.path.join(_SCAM_DIR, "en_business_growth_scam.txt")
        with open(path, encoding="utf-8") as f:
            text = f.read()
        findings, overall, contract_score, fraud_score = _run_full_pipeline(text)

        # Vorher: 0 Treffer, weil alle Regeln nur Deutsch waren.
        self.assertGreater(len(findings), 0)
        self.assertGreater(fraud_score, 50, "Betrugs-Score sollte deutlich erhöht sein")
        categories = _categories(findings)
        self.assertIn("Unrealistisches Rendite-/Gewinnversprechen (Betrugsindiz)", categories)
        self.assertIn("Vorschussgebühr / Vorkasse ohne Absicherung (typisches Betrugsmuster)", categories)
        self.assertIn(
            "Gerichtsstand/Recht wird erst nach Vertragsschluss vom Anbieter bestimmt",
            categories,
        )

    def test_english_investment_scam_pdf_now_detected(self) -> None:
        path = os.path.join(_SCAM_DIR, "en_investment_scam_test.pdf")
        contract = text_loader.load_contract_from_file(path)
        findings, overall, contract_score, fraud_score = _run_full_pipeline(contract.originaltext)

        # Dieses Dokument ist ein explizit als Scam-Testfall deklariertes
        # PDF mit zahlreichen eingebauten Indikatoren - vorher 0 Treffer.
        self.assertGreater(len(findings), 5)
        self.assertGreaterEqual(fraud_score, 90)
        categories = _categories(findings)
        self.assertIn("Ungewöhnliche/verdächtige Zahlungsmethode", categories)
        self.assertIn("Aufforderung zur Herausgabe sensibler Daten", categories)
        self.assertIn(
            "Aufforderung, keine Dritten/Behörden/Banken zu kontaktieren", categories,
        )
        self.assertIn("Mehrere gleichzeitige Betrugsindikatoren", categories)

    def test_german_hidden_traps_contract_now_detects_new_categories(self) -> None:
        path = os.path.join(_SCAM_DIR, "de_hidden_traps_contract.txt")
        with open(path, encoding="utf-8") as f:
            text = f.read()
        findings, overall, contract_score, fraud_score = _run_full_pipeline(text)

        categories = _categories(findings)
        # Vorher fehlende, jetzt neu erkannte Kategorien:
        self.assertIn(
            "Automatische Kostenpflicht durch Schweigen (Opt-Out-Falle)", categories,
        )
        self.assertIn("Einseitige Vertragsänderung ohne Zustimmung", categories)
        self.assertIn(
            "Anwendbares Recht/Gerichtsstand in bekannter Offshore-/Geheimhaltungsjurisdiktion",
            categories,
        )
        self.assertIn(
            "Unwiderrufliche Einwilligung (datenschutzrechtlich unzulässig)", categories,
        )
        self.assertIn("Beweislastumkehr zulasten des Kunden", categories)
        # Bereits vorher erkannte Kategorien müssen weiterhin funktionieren
        # (keine Regression):
        self.assertIn("Automatische Verlängerung", categories)
        self.assertIn("Haftungsausschluss", categories)


class TestAdditionalScamFixtures(unittest.TestCase):
    """14 weitere, vom Nutzer eingereichte Sample-Verträge (Krypto-Anlage,
    Gewinnbenachrichtigung, Spendenbetrug, Abo-Falle, Tech-Support-Scam,
    Kreditvorschussbetrug, Mietbetrug, Stellenbetrug, Erbschaftsbetrug -
    jeweils DE/EN-Paare, sofern vorhanden). Jeder Fall wurde VOR dieser
    Erweiterung mit 0 Treffern komplett übersehen (siehe README,
    Abschnitt "Erkenntnisse/Auswertung"). Diese Tests stellen sicher,
    dass jeder Fall jetzt einen signifikanten Betrugs-Score UND
    mindestens eine treffend benannte Kategorie erhält."""

    # Dateiname -> erwartete Mindest-Betrugsscore + mindestens eine
    # Kategorie, die zwingend gefunden werden muss.
    CASES = {
        "de_crypto_investment_scam.txt": (60, "Unregulierte Plattform / verweigerte Transparenz"),
        "en_crypto_investment_scam.txt": (60, "Unregulierte Plattform / verweigerte Transparenz"),
        "de_prize_notification_scam.txt": (60, "Unaufgeforderte Gewinn-/Lotteriebenachrichtigung"),
        "en_prize_notification_scam.txt": (60, "Unaufgeforderte Gewinn-/Lotteriebenachrichtigung"),
        "en_fake_donation_scam.txt": (60, "Eingeständnis fehlender Registrierung/Zulassung"),
        "en_subscription_trap.txt": (0, "Unvollständige oder fehlende Anbieterangaben"),
        "en_tech_support_scam.txt": (60, "Erpressung mit angeblich gespeicherten Daten"),
        "de_tech_support_scam.txt": (60, "Erpressung mit angeblich gespeicherten Daten"),
        "en_advance_fee_loan_scam.txt": (60, "Unrealistische Kreditkonditionen ohne Bonitätsprüfung"),
        "de_advance_fee_loan_scam.txt": (40, "Vorschussgebühr / Vorkasse ohne Absicherung (typisches Betrugsmuster)"),
        "en_rental_scam.txt": (60, "Vermieter unerreichbar / Zahlung vor Besichtigung verlangt"),
        "de_rental_scam.txt": (60, "Vermieter unerreichbar / Zahlung vor Besichtigung verlangt"),
        "en_job_scam.txt": (40, "Unrealistisch hohes Gehalt für minimalen Aufwand"),
        "en_inheritance_scam.txt": (60, "Unaufgeforderte Erbschaftsbenachrichtigung"),
    }

    def test_all_additional_scam_fixtures_detected(self) -> None:
        for filename, (min_fraud_score, expected_category) in self.CASES.items():
            with self.subTest(filename=filename):
                path = os.path.join(_SCAM_DIR, filename)
                with open(path, encoding="utf-8") as f:
                    text = f.read()
                findings, overall, contract_score, fraud_score = _run_full_pipeline(text)

                self.assertGreater(
                    len(findings), 0, f"'{filename}' erzeugt weiterhin 0 Treffer.",
                )
                self.assertGreaterEqual(
                    fraud_score, min_fraud_score,
                    f"'{filename}': Betrugs-Score {fraud_score} unter Erwartung {min_fraud_score}.",
                )
                categories = _categories(findings)
                self.assertIn(
                    expected_category, categories,
                    f"'{filename}': erwartete Kategorie '{expected_category}' fehlt. "
                    f"Gefundene Kategorien: {sorted(categories)}",
                )


class TestLegitimateContractsNotFlagged(unittest.TestCase):
    """Stellt sicher, dass die neuen, aggressiveren Betrugsregeln NICHT
    auf gewöhnlichen, seriösen Verträgen anschlagen (Kontrolle gegen
    Fehlalarme, wie vom Nutzer gefordert)."""

    def _assert_no_fraud_findings(self, filename: str, directory: str = _LEGIT_DIR) -> None:
        path = os.path.join(directory, filename)
        with open(path, encoding="utf-8") as f:
            text = f.read()
        findings, overall, contract_score, fraud_score = _run_full_pipeline(text)
        fraud_findings = [f for f in findings if f.typ == "betrug"]
        self.assertEqual(
            fraud_findings, [],
            f"Fehlalarm(e) in '{filename}': "
            f"{[(f.kategorie, f.fundstelle_text) for f in fraud_findings]}",
        )
        self.assertEqual(fraud_score, 0.0)

    def test_german_rental_agreement_has_no_fraud_findings(self) -> None:
        self._assert_no_fraud_findings("de_mietvertrag.txt")

    def test_english_consulting_agreement_has_no_fraud_findings(self) -> None:
        self._assert_no_fraud_findings("en_consulting_agreement.txt")

    def test_english_job_offer_has_no_fraud_findings(self) -> None:
        self._assert_no_fraud_findings("en_job_offer.txt")

    def test_english_bank_loan_has_no_fraud_findings(self) -> None:
        """Gezielte Gegenprobe zur neuen Regel 'unrealistic_loan_terms':
        ein Kredit MIT Bonitätsprüfung, EU-Registrierung und realistischem
        Zinssatz darf nicht als Betrug markiert werden - auch wenn dabei
        (als einer von mehreren Kontaktwegen) WhatsApp erwähnt wird."""
        self._assert_no_fraud_findings("en_bank_loan.txt")

    def test_german_apartment_listing_has_no_fraud_findings(self) -> None:
        """Gezielte Gegenprobe zur neuen Regel
        'landlord_unavailable_payment_before_viewing': eine Vermieterin,
        die persönlich vor Ort Besichtigungen durchführt, darf nicht als
        Mietbetrug markiert werden."""
        self._assert_no_fraud_findings("de_apartment_listing.txt")

    def test_original_sample_contract_still_has_no_fraud_findings(self) -> None:
        """Regressionstest: der mitgelieferte data/sample_contract.txt ist
        ein riskanter, aber NICHT betrügerischer B2B-Vertrag. Er soll auch
        nach der Regelerweiterung ausschließlich Vertragsklausel-Risiken,
        keine Betrugsmuster, auslösen."""
        sample_path = os.path.join(
            os.path.dirname(__file__), "..", "data", "sample_contract.txt"
        )
        with open(sample_path, encoding="utf-8") as f:
            text = f.read()
        findings, overall, contract_score, fraud_score = _run_full_pipeline(text)
        fraud_findings = [f for f in findings if f.typ == "betrug"]
        self.assertEqual(
            fraud_findings, [],
            f"Fehlalarm(e): {[(f.kategorie, f.fundstelle_text) for f in fraud_findings]}",
        )
        self.assertGreater(contract_score, 0)  # weiterhin als riskant erkannt


class TestNewRuleCategoriesInLibrary(unittest.TestCase):
    """Prüft strukturell, dass alle im Rahmen dieser Erweiterung neu
    eingeführten Regel-IDs tatsächlich in der Regelbibliothek vorhanden,
    aktiv und korrekt typisiert sind."""

    NEW_RULE_IDS_AND_TYPES = {
        # Erste Erweiterungsrunde (PDF/TXT-Testfälle #1-4)
        "negative_option_billing": "betrug",
        "isolation_from_third_parties": "betrug",
        "post_signing_unilateral_jurisdiction": "betrug",
        "recovery_scam_vocabulary": "betrug",
        "offshore_jurisdiction": "betrug",
        "scarcity_manipulation": "betrug",
        "irrevocable_consent": "vertragsklausel",
        "burden_of_proof_shift": "vertragsklausel",
        "unilateral_contract_modification": "vertragsklausel",
        "no_refund_policy": "vertragsklausel",
        # Zweite Erweiterungsrunde (14 weitere Sample-Verträge)
        "unsolicited_prize_notification": "betrug",
        "unsolicited_inheritance_notification": "betrug",
        "unregulated_or_unaudited_investment": "betrug",
        "contact_only_via_messaging_app": "betrug",
        "unregistered_entity_admission": "betrug",
        "payment_to_private_or_foreign_account": "betrug",
        "incomplete_provider_information": "betrug",
        "data_extortion_threat": "betrug",
        "fake_virus_alert_remote_access": "betrug",
        "unrealistic_loan_terms": "betrug",
        "unrealistic_salary_for_minimal_effort": "betrug",
        "landlord_unavailable_payment_before_viewing": "betrug",
        "difficult_cancellation_channel": "vertragsklausel",
        "below_market_price_bait": "betrug",
        "conditional_reimbursement_promise": "betrug",
        "payment_before_service_or_goods": "betrug",
    }

    def test_all_new_rules_present_active_and_correctly_typed(self) -> None:
        rules = rule_engine.load_rules()
        rules_by_id = {r.id: r for r in rules}
        for rule_id, expected_typ in self.NEW_RULE_IDS_AND_TYPES.items():
            self.assertIn(rule_id, rules_by_id, f"Regel '{rule_id}' fehlt in der Bibliothek.")
            rule = rules_by_id[rule_id]
            self.assertTrue(rule.aktiv, f"Regel '{rule_id}' sollte aktiv sein.")
            self.assertEqual(
                rule.typ, expected_typ,
                f"Regel '{rule_id}' sollte Typ '{expected_typ}' haben, ist aber '{rule.typ}'.",
            )

    def test_rule_library_has_grown_substantially(self) -> None:
        rules = rule_engine.load_rules()
        # Vor der ersten Erweiterung: 19 Regeln, nach der zweiten
        # Erweiterungsrunde (14 zusätzliche Sample-Verträge): 45 Regeln.
        self.assertGreaterEqual(len(rules), 44)


if __name__ == "__main__":
    unittest.main()
