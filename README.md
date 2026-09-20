# ContractRisk Scanner

**Regelbasierte Analyse von Vertragstexten auf riskante Klauseln – inklusive automatischer Fristen-Prognose.**

![Python](https://img.shields.io/badge/Python-3.11%2B-blue)
![License](https://img.shields.io/badge/License-MIT-green)
![Status](https://img.shields.io/badge/Status-Portfolio--Projekt-orange)

---

## Das Problem

Verträge enthalten oft unauffällig formulierte, aber folgenschwere Klauseln: automatische Verlängerungen, einseitige Kündigungsrechte des Anbieters oder versteckte Preisanpassungen. Gerade Selbstständige, kleine Unternehmen oder Privatpersonen lesen solche Klauseln häufig nur oberflächlich – mit dem Ergebnis, dass eine Kündigungsfrist verstreicht oder sich ein Vertrag ungewollt um ein weiteres Jahr verlängert. Ein automatisiertes Frühwarnsystem kann hier eine erste, schnelle Orientierung schaffen.

## Die Lösung

ContractRisk Scanner durchsucht importierte Vertragstexte anhand einer erweiterbaren, in JSON gepflegten Regelbibliothek (19 Kategorien) nach typischen Red-Flag-Formulierungen, verdächtigen Zahlungsbedingungen und Betrugsmustern, vergibt einen gewichteten **Risiko-Score (0–100)** und stellt die Ergebnisse in einer klar hervorgehobenen Textansicht dar. Eine **kontextbezogene Konfidenzbewertung** unterscheidet dabei eindeutige Treffer von unsicheren (z. B. durch eine erkannte Verneinung relativierten) Funden, und ein eigenes **Widerspruchsmodul** deckt auf, wenn zentrale Angaben wie Kündigungsfrist oder Preis im Dokument uneinheitlich genannt werden. Das **Prognose-Modul** geht einen Schritt weiter: Es erkennt Fristformulierungen im Text (z. B. „Kündigungsfrist von drei Monaten“) und rechnet sie – ausgehend von einem angegebenen Vertragsstart – in konkrete Kalendertermine um, dargestellt als visuelle Zeitleiste mit Warnfarben für bevorstehende kritische Termine. Der Import ist dabei nicht auf reine Textdateien beschränkt: PDF, Word, Excel, PowerPoint, OpenDocument, RTF und CSV werden ebenso unterstützt wie einfache `.txt`-Dateien.

> _Screenshot der markierten Textansicht hier einfügen: `docs/screenshot_textview.png`_

> _Screenshot der Fristen-Zeitleiste hier einfügen: `docs/screenshot_timeline.png`_

## Features

- **Multi-Format-Import**: `.txt`, `.csv`, `.pdf`, `.docx`, `.xlsx`, `.pptx`, `.odt`, `.rtf` – mehrere Dateien gleichzeitig, auch gemischte Formate in einem Import-Vorgang
- Klare, verständliche Fehlermeldungen bei nicht unterstützten Formaten (z. B. altes `.doc`/`.xls`) inkl. konkreter Handlungsempfehlung zur Konvertierung
- **Getrennte Risiko-Scores**: Vertragsklausel-Risiko und Betrugs-/Scam-Risiko werden als zwei eigenständige, animierte Score-Gauges dargestellt statt in einer einzigen, unscharfen Zahl vermischt zu werden
- **Zweisprachige Regelbibliothek (DE/EN)**: 45 Kategorien mit deutschen UND englischen Mustern – erkennt Scams unabhängig davon, in welcher Sprache der Vertrag verfasst ist
- **Optionaler OCR-Fallback**: Gescannte PDFs ohne eingebettete Textebene können bei installiertem Tesseract/Poppler automatisch per Texterkennung gelesen werden; ohne diese optionalen Pakete funktioniert die App unverändert mit einer klaren Fehlermeldung weiter
- **Kombinationsanalyse für Betrugsmuster**: Treten mehrere unabhängige Betrugsindikatoren gleichzeitig im selben Dokument auf (z. B. künstliche Dringlichkeit + verdächtige Zahlungsmethode + Aufforderung zu sensiblen Daten), erzeugt die Anwendung einen zusätzlichen, klar begründeten Warnhinweis – eine nachvollziehbare Zählregel, keine Black-Box-Einschätzung
- **Modernisiertes UI**: eigenständiges Design-System (verfeinerte Farbpalette, 8px-Abstandsraster, App-Header mit Branding), abgerundete Buttons/Badges/Score-Balken mit sanften Ease-Out-Animationen, Live-Suche & Sortierung in der Vertragsliste, Format-Icons, Fortschrittsanzeige während des Scans
- Konfigurierbare, code-unabhängige Regelbibliothek (JSON, 19 Kategorien) mit Kategorie, Schweregrad und Regex-Mustern
- **Erweiterte Risikoerkennung**: Vertragsklauseln (automatische Verlängerung, einseitige Kündigung, Haftungsausschluss, Abtretung, Vertragsstrafe u. a.) UND Betrugs-/Scam-Muster (verdächtige Zahlungsmethoden, Vorschussbetrug, künstliche Dringlichkeit, Aufforderung zu sensiblen Daten, unrealistische Renditeversprechen, Behörden-Drohkulissen)
- **Kontextbezogene Konfidenzbewertung** je Fund (hoch/mittel/niedrig): Verneinungen und Ermessensspielräume im Kontext reduzieren die Konfidenz eines Treffers, statt ihn stillschweigend zu verwerfen oder unbegründet als sicheres Risiko darzustellen
- **Widerspruchsprüfung**: erkennt, wenn zentrale Angaben (Kündigungsfrist, Laufzeit, Preis) im Dokument mit unterschiedlichen Werten genannt werden, und belegt dies mit beiden Fundstellen
- Gewichtetes Risiko-Scoring (0–100) mit Ampel-Einstufung, das Schweregrad UND Konfidenz berücksichtigt
- Fristen-Prognose: Erkennung von Kündigungsfristen und automatischen Verlängerungen, Umrechnung in konkrete Termine
- Visuelle Zeitleiste (matplotlib) mit Warnfarben bei bevorstehenden Terminen
- Farblich markierte, klickbare Textansicht mit Detailerklärung UND fundspezifischer Begründung je Auffälligkeit; die Markierungsstärke im Text spiegelt die Konfidenz wider
- Vertragsübersicht mit Risiko-Score-Badges, sortierbar
- Lokale SQLite-Persistenz aller Verträge, Funde und Fristen (mit automatischer Schema-Migration bei App-Updates)
- Integrierter Regel-Editor (Regeln ansehen, bearbeiten, aktivieren/deaktivieren, neu anlegen)
- Export als Textreport (getrennt nach bestätigten und unklaren Befunden) sowie PNG-Export der Zeitleiste
- Dunkles Theme (umschaltbar auf hell), sanfte Animationen, responsives Layout
- Hintergrund-Threading für den Textscan, damit die GUI nicht einfriert
- **100 % lokal**: keine Cloud-Anbindung, keine API-Keys, keine Übertragung sensibler Vertragsinhalte

## Unterstützte Dateiformate

| Format | Endung | Hinweis |
|---|---|---|
| Textdatei | `.txt` | direkt, mit automatischer Encoding-Erkennung |
| CSV-Tabelle | `.csv` | Trennzeichen wird automatisch erkannt (`,` `;` `\t` `\|`) |
| PDF-Dokument | `.pdf` | Text-PDFs; bei gescannten PDFs ohne OCR erfolgt ein klarer Hinweis |
| Word-Dokument | `.docx` | Fließtext UND Tabelleninhalte |
| Excel-Tabelle | `.xlsx` | alle Arbeitsblätter, zeilenweise als Text |
| PowerPoint | `.pptx` | Folieninhalte inkl. Tabellen und Sprechernotizen |
| OpenDocument-Text | `.odt` | Fließtext |
| Rich Text Format | `.rtf` | einfacher, abhängigkeitsfreier Extraktor |

**Nicht unterstützt** (mit klarer Fehlermeldung inkl. Konvertierungsempfehlung): das alte binäre `.doc`- und `.xls`-Format, `.ppt`, `.html`, sowie proprietäre Formate wie `.pages`/`.key`/`.numbers`. Für diese Formate gibt es keine zuverlässige, reine Python-Lösung ohne zusätzliche Systemabhängigkeiten – die Anwendung bricht den Import dieser Dateien kontrolliert ab und schlägt eine Konvertierung in ein unterstütztes Format vor, statt einen unklaren Fehler oder falsche Ergebnisse zu produzieren.

## Architektur

```
contractrisk/
├── main.py                     # Einstiegspunkt
├── data/
│   ├── rules.json               # Regelbibliothek (strikt von der Engine getrennt, 19 Kategorien)
│   └── sample_contract.txt      # Beispielvertrag mit eingebauten Risikoklauseln
├── contractrisk/
│   ├── config.py                 # Zentrale Konfiguration (inkl. unterstützte/nicht unterstützte Formate)
│   ├── database/db_manager.py    # SQLite CRUD + automatische Schema-Migration
│   ├── domain/models.py          # Datenklassen (Contract, Rule, RiskFinding, Deadline)
│   ├── analysis/
│   │   ├── rule_engine.py        # Lädt Regeln, führt Textscan aus, bewertet Konfidenz
│   │   ├── consistency_checker.py# Erkennt Widersprüche zwischen mehreren Fundstellen
│   │   ├── risk_scoring.py       # Berechnet den Gesamt-Risiko-Score (Schweregrad × Konfidenz)
│   │   └── deadline_forecaster.py# Erkennt & berechnet Fristen
│   ├── io_utils/
│   │   ├── text_loader.py        # Zentraler Import-Einstieg, Formaterkennung
│   │   ├── document_parsers.py   # Formatspezifische Textextraktion (PDF/DOCX/XLSX/PPTX/ODT/RTF/CSV)
│   │   └── report_writer.py      # Report-Export
│   ├── gui/                      # tkinter/ttk-Oberfläche (keine Business-Logik)
│   └── utils/                    # Exceptions, zentrales Logging
└── tests/                        # unittest-Tests je Kernmodul
    └── fixtures/                  # Reale Scam-Testfälle + legitime Vergleichsverträge (Regressionstests)
```

Zentrales Architekturprinzip: **Die Regelbibliothek ist strikt von der Scan-Engine getrennt.** `rule_engine.py` enthält keine hartkodierten Klausel-Beispiele, sondern lädt alle Muster zur Laufzeit aus `data/rules.json` – neue Regeltypen (auch neue Betrugs- oder Zahlungsmuster) lassen sich über den integrierten Regel-Editor oder direkt in der JSON-Datei hinzufügen, ohne den Code anzufassen. Analysen, die eine einzelne Regel strukturell nicht leisten kann (Vergleich mehrerer Fundstellen untereinander), sind als eigenständiges Modul (`consistency_checker.py`) umgesetzt.

## Installation

1. **Voraussetzungen:** Python 3.11 oder neuer, PyCharm (empfohlen).
2. Projektordner in PyCharm öffnen (`File → Open...`).
3. Virtuelle Umgebung anlegen und aktivieren:
   ```bash
   python -m venv venv
   # Windows:
   venv\Scripts\activate
   # macOS/Linux:
   source venv/bin/activate
   ```
4. Abhängigkeiten installieren (matplotlib fürs Chart sowie die Dokumenten-Parser für PDF/DOCX/XLSX/PPTX/ODT):
   ```bash
   pip install -r requirements.txt
   ```
5. Anwendung starten:
   ```bash
   python main.py
   ```
   In PyCharm: Rechtsklick auf `main.py` → **Run 'main'**.
6. **Schnelltest:** Über „Vertrag importieren“ die mitgelieferte `data/sample_contract.txt` auswählen und als Stichtag z. B. `01.01.2026` eingeben – die App zeigt sofort mehrere markierte Risikoklauseln sowie eine Fristen-Zeitleiste.
7. Tests ausführen:
   ```bash
   python -m unittest discover tests
   ```

## Erkenntnisse / Auswertung

Der mitgelieferte Beispielvertrag (`data/sample_contract.txt`) enthält bewusst Formulierungen aus allen 10 klassischen Vertragsklausel-Kategorien und wird von der Regel-Engine vollständig mit Konfidenz „hoch" erkannt (Score 100/100). Die kontextbezogene Konfidenzbewertung wurde gezielt gegen Verneinungs- und Ermessensformulierungen getestet (siehe `tests/test_rule_engine.py::TestConfidenceAssessment`) und reduziert in diesen Fällen nachweislich die Konfidenz, statt den Treffer zu unterdrücken.

### Diagnose & Verbesserung der Scam-Erkennung (dokumentierter Vorher/Nachher-Vergleich)

Bei einem gezielten Test mit vier realistischen Scam-Beispieldokumenten (zwei englischsprachige Fake-Investment-/Business-Verträge, ein deutscher Vertrag mit versteckten Fallen, ein gescanntes Betrugs-Schreiben) erkannte die ursprüngliche Regelbibliothek **0 von 4** Fällen zuverlässig. Ursachenanalyse und Behebung:

| # | Ursache des Erkennungsausfalls | Behebung |
|---|---|---|
| 1 | Alle Regex-Muster waren ausschließlich **deutschsprachig** – englische Verträge (2 von 4 Testfällen) erzeugten dadurch strukturell 0 Treffer, unabhängig vom Inhalt. | Jede bestehende Regel wurde um passende **englische Muster** ergänzt (bilinguale `muster`-Listen pro Regel). |
| 2 | Kategorien wie **Opt-Out-Kostenfallen** ("gilt als angenommen, sofern nicht binnen 48 Std. widersprochen wird"), **Isolationstaktik** ("kontaktieren Sie keine Bank/Behörde"), **nachträglich vom Anbieter bestimmter Gerichtsstand**, **Recovery-Scam-Vokabular** (escrow, Treuhand-Freigabe, "administrators") und **unwiderrufliche Einwilligung** existierten in der Regelbibliothek noch gar nicht. | **10 neue Regelkategorien** ergänzt (siehe Tabelle unten), gezielt aus der Analyse der eingereichten Testfälle abgeleitet. |
| 3 | Ein gescanntes PDF (Fotos/Scans von Betrugsschreiben) enthielt **keine eingebettete Textebene** – `pypdf` kann aus Bildern keinen Text extrahieren. | **Optionaler OCR-Fallback** ergänzt (`pytesseract` + `pdf2image`, gracefully degradierend ohne diese Pakete – siehe `document_parsers._try_ocr_fallback`). |
| 4 | Mehrere unabhängige Betrugsindikatoren im selben Dokument wurden nicht als verstärkendes Gesamtsignal gewertet. | Bereits vorhandene Kombinationsanalyse (`fraud_pattern_analyzer.py`) profitiert direkt von den neuen Kategorien und erzeugt jetzt in allen vier Testfällen einen zusätzlichen "Mehrere gleichzeitige Betrugsindikatoren"-Fund. |

**Ergebnis nach der Erweiterung** (siehe `tests/test_scam_detection.py`, reproduzierbar mit den mitgelieferten Fixtures in `tests/fixtures/`):

| Testfall | Vorher | Nachher |
|---|---|---|
| Englischer Fake-Business-Growth-Vertrag | 0 Treffer, Betrugs-Score 0 | 17 Treffer, Betrugs-Score 75/100 |
| Englisches Fake-Investment-Testdokument (PDF) | 0 Treffer, Betrugs-Score 0 | 19 Treffer, Betrugs-Score 100/100 |
| Deutscher Vertrag mit versteckten Fallen | 4 Treffer (nur Basis-Klauseln), Betrugs-Score 0 | 12 Treffer, Betrugs-Score 37,5/100, inkl. der zuvor unerkannten Opt-Out-Kostenfalle |
| Gescanntes Betrugsschreiben (Bild-PDF) | Import schlug fehl ("kein Text extrahierbar") | Per optionalem OCR lesbar, 15 Treffer, Betrugs-Score 100/100 |

**Kontrolle gegen Fehlalarme:** Dieselbe erweiterte Regelbibliothek wurde gegen drei unabhängig verfasste, garantiert legitime Verträge (deutscher Mietvertrag, englischer Beratervertrag, englisches Jobangebot) sowie den ursprünglichen Beispielvertrag getestet. In allen vier Fällen: **0 Betrugsmuster-Treffer** (siehe `tests/test_scam_detection.py::TestLegitimateContractsNotFlagged`). Ein zunächst zu generisches Muster (Schweigen-als-Zustimmung bei gewöhnlichen Preisanpassungsklauseln) wurde dabei identifiziert und gezielt verschärft, um ausschließlich echte Opt-Out-Kostenfallen zu erfassen.

### Neue Regelkategorien im Detail

| Kategorie | Typ | Schweregrad | Worauf sie reagiert |
|---|---|---|---|
| Automatische Kostenpflicht durch Schweigen (Opt-Out-Falle) | Betrug | hoch | Kostenpflichtige Zusatzleistung wird bei Nicht-Widerspruch innerhalb kurzer Frist automatisch aktiviert |
| Aufforderung, keine Dritten/Behörden/Banken zu kontaktieren | Betrug | hoch | Isolationstaktik – hält Empfänger davon ab, das Angebot unabhängig prüfen zu lassen |
| Gerichtsstand/Recht wird erst nach Vertragsschluss vom Anbieter bestimmt | Betrug | hoch | Anwendbares Recht bleibt beim Unterzeichnen bewusst offen |
| Recovery-Scam-Vokabular ("escrow", "administrators", "claims form" ...) | Betrug | hoch | Typische Begriffe aus Rückgewinnungsbetrug gegen frühere Betrugsopfer |
| Offshore-/Geheimhaltungsjurisdiktion | Betrug | mittel | Recht/Gerichtsstand in bekannten Briefkastenfirmen-Standorten |
| Künstliche Verknappung | Betrug | niedrig | "Nur noch X % verfügbar" als Kaufdruck-Taktik |
| Unwiderrufliche Einwilligung | Vertragsklausel | hoch | Datenschutzrechtlich unzulässige "kann nicht widerrufen werden"-Klausel |
| Beweislastumkehr zulasten des Kunden | Vertragsklausel | mittel | Kunde muss Sachverhalte beweisen, zu denen er kaum Zugang hat |
| Einseitige Vertragsänderung ohne Zustimmung | Vertragsklausel | hoch | Anbieter kann Leistungsumfang/Bedingungen jederzeit einseitig ändern |
| Kein Rückerstattungsanspruch | Vertragsklausel | mittel | Zahlungen sind unter allen Umständen von der Erstattung ausgeschlossen |

Insgesamt wuchs die Regelbibliothek von 19 auf **29 Kategorien**, jede davon jetzt mit deutschen UND englischen Mustern, wo im Testmaterial beide Sprachen relevant waren.

### Zweite Erweiterungsrunde: 14 weitere Sample-Verträge (Krypto, Gewinnspiel, Erbschaft, Job, Miete, Kredit, Tech-Support, Abo-Falle)

In einer zweiten Runde wurden 14 zusätzliche, vom Nutzer bereitgestellte Beispielverträge systematisch analysiert (jeweils deutsche/englische Fassungen von: Krypto-Investitionsbetrug, Gewinnbenachrichtigung, Spendenbetrug, Abo-Falle, Tech-Support-Erpressung, Kreditvorschussbetrug, Mietbetrug, Stellenbetrug, Erbschaftsbetrug). Ausgangslage: **11 von 14 Dokumenten erzeugten 0 Treffer**, die übrigen 3 nur je 1 Treffer.

**14 weitere Regelkategorien** wurden ergänzt, u. a.: unaufgeforderte Gewinn-/Erbschaftsbenachrichtigungen, unregulierte/prüfungsverweigernde Anlageplattformen, ausschließliche Kontaktaufnahme über Messenger-Apps (Telegram/WhatsApp), Eingeständnis fehlender Unternehmensregistrierung, Zahlung auf Privat-/Drittlandkonten, Datenerpressungs-Drohungen, vorgetäuschte Vireninfektionen mit Fernzugriffsanspruch, unrealistische Kreditkonditionen ohne Bonitätsprüfung, unrealistisch hohe Gehälter für minimalen Aufwand, unerreichbare Vermieter mit Zahlung vor Besichtigung, erschwerte Kündigungswege ins Ausland. Zusätzlich wurden 6 bestehende Regeln (u. a. `advance_fee_pattern`, `suspicious_payment_method`, `unrealistic_return_promise`, `urgency_pressure_language`, `isolation_from_third_parties`) um weitere deutsche und englische Formulierungsvarianten ergänzt.

**Ergebnis nach dieser Runde** (siehe `tests/test_scam_detection.py::TestAdditionalScamFixtures`, Fixtures in `tests/fixtures/scam_samples/`):

| Testfall | Treffer | Betrugs-Score |
|---|---|---|
| Krypto-Investitionsbetrug (DE/EN) | 9 / 8 | 100 / 97,5 |
| Gewinnbenachrichtigung (DE/EN) | 11 / 11 | 100 / 100 |
| Spendenbetrug (EN) | 8 | 100 |
| Tech-Support-Erpressung (DE/EN) | 5 / 6 | 75 / 90 |
| Kreditvorschussbetrug (DE/EN) | 6 / 6 | 51,8 / 67,5 |
| Mietbetrug (DE/EN) | 8 / 8 | 100 / 100 |
| Stellenbetrug (EN) | 6 | 52,5 |
| Erbschaftsbetrug (EN) | 10 | 100 |
| Abo-Falle (EN) | 5 | 7,5 (bewusst niedrig – siehe Einordnung unten) |

**Einordnung der Abo-Falle:** Dieser Fall (automatische 24-Monats-Verlängerung, erschwerte Kündigung per Auslandsbrief, unvollständiges Impressum) wird korrekt mit einem erhöhten **Vertragsklausel**-Score erkannt, bleibt beim **Betrugs**-Score aber bewusst niedrig. Begründung: Es handelt sich um ein aggressives, aber im Kern legales Geschäftsmodell ("Dark Pattern"), nicht um einen klassischen Betrugsversuch wie die übrigen Fälle - die getrennte Score-Darstellung (siehe oben) macht genau diesen Unterschied sichtbar, statt beides in einer Zahl zu vermischen.

**Erneute Fehlalarm-Kontrolle:** Zwei weitere, gezielt gegen die heikelsten neuen Regeln konstruierte legitime Verträge wurden ergänzt: ein Bankkredit mit Bonitätsprüfung, EU-Regulierung und einem WhatsApp-Kanal als einer von mehreren Kontaktwegen (testet `unrealistic_loan_terms` und `contact_only_via_messaging_app`) sowie ein Wohnungsangebot mit vor Ort besichtigender Vermieterin (testet `landlord_unavailable_payment_before_viewing`). Beide: **0 Betrugstreffer**. Die Regelbibliothek umfasst nun **45 Kategorien** (27 Betrugsmuster, 18 Vertragsklausel-Risiken).

## Technologien

| Bereich          | Technologie                       | Begründung |
|-------------------|-----------------------------------|------------|
| Sprache            | Python 3.11+                      | Standardbibliothek deckt den Großteil der Anforderungen ab |
| GUI                | tkinter / ttk                     | Kein zusätzliches Framework nötig, plattformunabhängig |
| Textanalyse        | `re`, `json`, `datetime`          | Keine externe NLP-Bibliothek notwendig |
| Dokumenten-Import  | `pypdf`, `python-docx`, `openpyxl`, `python-pptx`, `odfpy` | Je eine etablierte, reine Python-Bibliothek pro Format – kein Systemabhängigkeiten wie LibreOffice/Antiword |
| OCR-Fallback (optional) | `pytesseract`, `pdf2image` (+ System: Tesseract, Poppler) | Nur für gescannte PDFs ohne Textebene nötig; App funktioniert vollständig auch ohne diese Pakete |
| Persistenz         | `sqlite3`                          | Lokale, dateibasierte Datenbank ohne Serverbetrieb |
| Zeitleiste         | `matplotlib`                       | tkinter allein bietet keine praktikable Möglichkeit, eine beschriftete, professionell wirkende Zeitleiste zu zeichnen |
| Tests              | `unittest`                         | Standardbibliothek, keine zusätzliche Test-Abhängigkeit |

**Bewusst keine Cloud-KI/LLM-API:** Verträge enthalten häufig sensible geschäftliche oder personenbezogene Inhalte. Das Tool verarbeitet daher alles ausschließlich lokal – es werden keine Vertragstexte an externe Dienste übertragen. Die These des Projekts ist zudem, dass sich die relevantesten Red-Flag- und Betrugsmuster bereits mit regelbasierter Mustererkennung plus einfacher, transparenter Kontextanalyse (Verneinungserkennung, Widerspruchsprüfung, Kombinationsanalyse mehrerer Indikatoren) zuverlässig genug erfassen lassen, um als praktisches Frühwarnsystem zu dienen – ohne die Intransparenz eines Black-Box-KI-Modells.

## Roadmap

- Mehrsprachige Regelbibliothek (z. B. Englisch, Französisch)
- OCR-Unterstützung für gescannte PDFs ohne eingebetteten Text
- Optionales, rein lokal laufendes KI-Modell als Vergleichsbasis zur Regel-Engine

## Rechtlicher Hinweis

Dieses Projekt ist ein **technisches Demo- und Analyse-Tool** und stellt **keine Rechtsberatung** dar. Alle Ergebnisse sind automatisiert erzeugte Orientierungshilfen und ersetzen keine Prüfung durch eine fachkundige Person. Jeder Befund ist mit einer konkreten Textstelle und einer nachvollziehbaren Begründung belegt; unklare Fälle werden ausdrücklich mit reduzierter Konfidenz gekennzeichnet, statt eine unbegründete Sicherheit vorzutäuschen.

## Lizenz

Veröffentlicht unter der [MIT-Lizenz](LICENSE).

---

## LinkedIn-Post-Entwurf

> **These:** Riskante Vertragsklauseln und Betrugsmuster – automatische Verlängerungen, versteckte Kosten, Vorschussbetrug, künstliche Dringlichkeit – werden im Alltag oft übersehen, weil niemand Zeit hat, jeden Vertrag oder jede verdächtige Nachricht Zeile für Zeile zu prüfen.
>
> **Prozess:** Deshalb habe ich den **ContractRisk Scanner** gebaut: ein rein lokal laufendes Python-Tool, das Dokumente in gängigen Formaten (PDF, Word, Excel, PowerPoint, Text) anhand einer erweiterbaren Regelbibliothek scannt, Risiken UND Betrugsmuster erkennt, deren Konfidenz kontextbezogen bewertet (Verneinungen werden erkannt, nicht ignoriert) und – als Alleinstellungsmerkmal – eine **Fristen-Prognose** liefert: Kündigungsfristen und automatische Verlängerungen werden in konkrete Kalendertermine umgerechnet und als Zeitleiste visualisiert.
>
> **Resultat:** Eine funktionierende Desktop-Anwendung mit sauberer Schichtenarchitektur, Multi-Format-Import, SQLite-Persistenz, Hintergrund-Threading und einem eigenen Regel-Editor – bewusst ganz ohne Cloud-KI, da Dokumente sensible Inhalte enthalten können.
>
> Code & Doku auf GitHub: [Link einfügen]
>
> #Python #LegalTech #SoftwareEngineering #Portfolio
