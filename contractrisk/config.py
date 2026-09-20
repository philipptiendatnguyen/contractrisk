"""
config.py
---------
Zentrale Konfiguration des ContractRisk Scanners.

Alle "Magic Numbers", Pfade und Design-Parameter, die an mehreren Stellen
im Projekt benötigt werden, sind hier gebündelt. Dadurch müssen Werte wie
Schwellenwerte für kritische Fristen oder Farbcodes nur an EINER Stelle
gepflegt werden.
"""

from __future__ import annotations

import os

# ---------------------------------------------------------------------------
# Pfade
# ---------------------------------------------------------------------------

# Basisverzeichnis des Projekts (eine Ebene über diesem Paket)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DATA_DIR = os.path.join(BASE_DIR, "data")
RULES_FILE_PATH = os.path.join(DATA_DIR, "rules.json")
SAMPLE_CONTRACT_PATH = os.path.join(DATA_DIR, "sample_contract.txt")

# SQLite-Datenbankdatei liegt im Datenverzeichnis
DATABASE_PATH = os.path.join(DATA_DIR, "contractrisk.db")

# Zielverzeichnis für Exporte (Reports, Zeitleisten-PNGs)
EXPORT_DIR = os.path.join(BASE_DIR, "exports")

# ---------------------------------------------------------------------------
# Dokumenten-Import: unterstützte und bekannte, aber nicht unterstützte
# Dateiformate
# ---------------------------------------------------------------------------

# Formate, die technisch ausgelesen werden können (Endung -> Kurzbezeichnung
# für Logs/Statusmeldungen). Die eigentliche Extraktionslogik liegt in
# io_utils/document_parsers.py.
SUPPORTED_DOCUMENT_EXTENSIONS = {
    ".txt": "Textdatei",
    ".csv": "CSV-Tabelle",
    ".pdf": "PDF-Dokument",
    ".docx": "Word-Dokument (docx)",
    ".xlsx": "Excel-Tabelle (xlsx)",
    ".pptx": "PowerPoint-Präsentation (pptx)",
    ".odt": "OpenDocument-Text (odt)",
    ".rtf": "Rich-Text-Format (rtf)",
}

# Formate, die zwar erkannt, aber (in diesem Environment oder grundsätzlich)
# nicht zuverlässig ausgelesen werden können. Jede Endung ist mit einer für
# den Nutzer verständlichen Erklärung inkl. Handlungsempfehlung hinterlegt.
KNOWN_UNSUPPORTED_EXTENSIONS = {
    ".doc": (
        "Das alte, binäre Word-Format (.doc) kann nicht zuverlässig automatisiert "
        "ausgelesen werden. Bitte öffnen Sie die Datei in Word und speichern Sie "
        "sie als .docx oder .txt, um sie zu importieren."
    ),
    ".xls": (
        "Das alte, binäre Excel-Format (.xls) wird derzeit nicht unterstützt. "
        "Bitte öffnen Sie die Datei in Excel und speichern Sie sie als .xlsx "
        "oder exportieren Sie sie als .csv."
    ),
    ".ppt": (
        "Das alte, binäre PowerPoint-Format (.ppt) wird derzeit nicht unterstützt. "
        "Bitte speichern Sie die Präsentation als .pptx."
    ),
    ".pages": (
        "Apple-Pages-Dateien (.pages) werden nicht unterstützt. Bitte exportieren "
        "Sie das Dokument in Pages als .docx oder .pdf."
    ),
    ".key": (
        "Apple-Keynote-Dateien (.key) werden nicht unterstützt. Bitte exportieren "
        "Sie die Präsentation in Keynote als .pptx oder .pdf."
    ),
    ".numbers": (
        "Apple-Numbers-Dateien (.numbers) werden nicht unterstützt. Bitte "
        "exportieren Sie die Tabelle in Numbers als .xlsx oder .csv."
    ),
    ".html": (
        "HTML-Dateien werden derzeit nicht unterstützt. Bitte speichern Sie den "
        "Inhalt als .txt oder .pdf und importieren Sie diese Datei."
    ),
    ".htm": (
        "HTML-Dateien werden derzeit nicht unterstützt. Bitte speichern Sie den "
        "Inhalt als .txt oder .pdf und importieren Sie diese Datei."
    ),
}

# ---------------------------------------------------------------------------
# Risiko-Scoring
# ---------------------------------------------------------------------------

# Gewichtungsfaktoren je Schweregrad. Werden zur Berechnung des
# Gesamt-Risiko-Scores (0-100) verwendet, siehe analysis/risk_scoring.py
SEVERITY_WEIGHTS = {
    "niedrig": 1,
    "mittel": 3,
    "hoch": 6,
}

# Gewichtungsfaktoren je Konfidenzstufe eines Fundes. Ein Fund, dessen
# Kontext auf eine mögliche Verneinung oder Einschränkung hindeutet
# (z. B. "KEINE automatische Verlängerung"), fließt mit reduziertem
# Gewicht in den Score ein, wird aber weiterhin transparent angezeigt und
# nicht stillschweigend unterdrückt (siehe rule_engine._confidence_for_match).
CONFIDENCE_WEIGHTS = {
    "hoch": 1.0,
    "mittel": 0.6,
    "niedrig": 0.3,
}

# Obergrenze, ab der ein Score auf 100 gekappt wird (verhindert, dass sehr
# lange Verträge mit vielen Treffern den Score unrealistisch sprengen)
MAX_RAW_SCORE_FOR_NORMALIZATION = 40

# Schwellenwerte zur Einteilung des Gesamt-Scores in Ampel-Kategorien
RISK_LEVEL_THRESHOLDS = {
    "niedrig": (0, 33),
    "mittel": (34, 66),
    "hoch": (67, 100),
}

# ---------------------------------------------------------------------------
# Fristen-Prognose
# ---------------------------------------------------------------------------

# Anzahl Tage, ab der eine bevorstehende Frist als "kritisch" (rote Warnung)
# markiert wird
CRITICAL_DEADLINE_WARNING_DAYS = 60

# Anzahl Tage, ab der eine Frist als "bald" (gelbe Warnung) markiert wird
UPCOMING_DEADLINE_WARNING_DAYS = 120

# ---------------------------------------------------------------------------
# Kontextanalyse (Verneinungserkennung, Widerspruchsprüfung)
# ---------------------------------------------------------------------------

# Anzahl Zeichen VOR einem Regel-Treffer, die auf Verneinungswörter
# ("nicht", "kein" ...) untersucht werden, um Fehlalarme zu reduzieren
# (siehe analysis/rule_engine._confidence_for_match).
NEGATION_LOOKBEHIND_CHARS = 45

# ---------------------------------------------------------------------------
# Klassifikation von Regeln/Funden: Vertragsklausel vs. Betrugsmuster
# ---------------------------------------------------------------------------

# Jede Regel wird als "vertragsklausel" (juristisch/wirtschaftlich riskante,
# aber grundsätzlich legale Klausel) oder "betrug" (Muster, das typisch für
# Betrugs-/Scam-Versuche ist) klassifiziert. Diese Trennung ermöglicht zwei
# getrennt ausgewiesene Scores (siehe analysis/risk_scoring.split_scores),
# statt beide Risikoarten unscharf in einer einzigen Zahl zu vermischen.
FINDING_TYPES = ("vertragsklausel", "betrug")
FINDING_TYPE_LABELS = {
    "vertragsklausel": "Vertragsrisiko",
    "betrug": "Betrugs-/Scam-Indikator",
}

# Ab wie vielen GLEICHZEITIG im selben Dokument gefundenen, unterschiedlichen
# Betrugs-Kategorien wird ein zusätzlicher, aggregierter "Mehrfachindikator"-
# Fund erzeugt (siehe analysis/fraud_pattern_analyzer.py). Das Zusammentreffen
# mehrerer UNABHÄNGIGER Betrugsmuster ist ein anerkannt starkes Warnsignal.
MIN_COMBINED_FRAUD_INDICATORS = 2

# ---------------------------------------------------------------------------
# GUI / Design-System
# ---------------------------------------------------------------------------

APP_TITLE = "ContractRisk Scanner"
APP_TAGLINE = "Regelbasierte Vertrags- und Betrugsrisiko-Analyse – 100 % lokal"
APP_MIN_WIDTH = 1280
APP_MIN_HEIGHT = 800

SIDEBAR_WIDTH = 300
HEADER_HEIGHT = 64

# Abstands-Skala (8px-Grid) für ein konsistentes, "atmendes" Layout über
# alle Panels hinweg - ersetzt willkürlich gewählte Einzelwerte.
SPACE_XXS = 2
SPACE_XS = 4
SPACE_SM = 8
SPACE_MD = 16
SPACE_LG = 24
SPACE_XL = 32
SPACE_XXL = 48

# Radius-Konvention für abgerundete Canvas-Elemente (Badges, Buttons, Karten)
RADIUS_SM = 6
RADIUS_MD = 10
RADIUS_LG = 16

# Farbpalette (dunkles Theme als Standard). Gegenüber einer reinen
# Zweck-Palette wurde bewusst ein zusätzlicher, kühlerer Akzentton
# ("accent_soft") sowie feiner abgestufte Oberflächen ("bg_elevated",
# "bg_hover") ergänzt, damit Karten, Header und interaktive Elemente sich
# klar, aber dezent voneinander abheben (Material-/Fluent-inspiriert,
# ohne fremde Assets).
COLORS_DARK = {
    "bg_primary": "#0B0D14",
    "bg_secondary": "#12141E",
    "bg_elevated": "#181B27",
    "bg_card": "#1B1F2D",
    "bg_hover": "#242939",
    "bg_pressed": "#2C324A",
    "border": "#272C3E",
    "border_strong": "#363C55",
    "text_primary": "#EEF0F7",
    "text_secondary": "#A2A9C3",
    "text_muted": "#6D7290",
    "accent": "#5B8CFF",
    "accent_hover": "#7AA0FF",
    "accent_soft": "#26314F",
    "severity_niedrig": "#34D399",
    "severity_mittel": "#FBBF24",
    "severity_hoch": "#F5606B",
    "fraud_accent": "#C77DFF",
}

COLORS_LIGHT = {
    "bg_primary": "#F4F5F9",
    "bg_secondary": "#FFFFFF",
    "bg_elevated": "#FFFFFF",
    "bg_card": "#FFFFFF",
    "bg_hover": "#EEF0F8",
    "bg_pressed": "#E3E7F5",
    "border": "#E0E3EE",
    "border_strong": "#C7CCDE",
    "text_primary": "#1A1D2A",
    "text_secondary": "#4E546C",
    "text_muted": "#868CA3",
    "accent": "#3563E9",
    "accent_hover": "#2450D6",
    "accent_soft": "#E7ECFD",
    "severity_niedrig": "#16A164",
    "severity_mittel": "#B07A05",
    "severity_hoch": "#D6394A",
    "fraud_accent": "#8B3FD1",
}

FONT_FAMILY_HEADING = "Segoe UI Semibold"
FONT_FAMILY_BODY = "Segoe UI"
FONT_FAMILY_MONO = "Consolas"

FONT_SIZE_DISPLAY = 20
FONT_SIZE_TITLE = 16
FONT_SIZE_SUBTITLE = 12
FONT_SIZE_BODY = 10
FONT_SIZE_SMALL = 9
FONT_SIZE_TINY = 8

# Format-Icons (Unicode-Glyphen statt externer Bilddateien - funktioniert
# ohne zusätzliche Assets plattformübergreifend in tkinter)
FORMAT_ICONS = {
    ".pdf": "📕", ".docx": "📄", ".txt": "📃", ".csv": "📊",
    ".xlsx": "📊", ".pptx": "📽️", ".odt": "📄", ".rtf": "📄",
}

# ---------------------------------------------------------------------------
# Sonstiges
# ---------------------------------------------------------------------------

APP_VERSION = "1.0.0"
DISCLAIMER_TEXT = (
    "Hinweis: Dieses Tool automatisiert eine erste Orientierung anhand "
    "regelbasierter Texterkennung und ersetzt KEINE rechtliche Beratung. "
    "Alle Ergebnisse sollten von einer fachkundigen Person geprüft werden."
)

LOG_FILE_PATH = os.path.join(BASE_DIR, "contractrisk.log")
