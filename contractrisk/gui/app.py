"""
gui/app.py
------------
Hauptfenster der Anwendung. Orchestriert die einzelnen GUI-Panels und
verbindet sie mit der Analyse- und Datenbankschicht.

Wichtig: Diese Datei enthält bewusst KEINE eigene Business-Logik
(Textscan, Scoring, Fristenberechnung) - sie ruft ausschließlich
Funktionen aus `analysis/`, `domain/` und `database/` auf.
"""

from __future__ import annotations

import queue
import threading
import tkinter as tk
from datetime import date, datetime
from tkinter import filedialog, messagebox, simpledialog, ttk
from typing import Optional

from contractrisk.analysis import (
    consistency_checker,
    deadline_forecaster,
    fraud_pattern_analyzer,
    risk_scoring,
    rule_engine,
)
from contractrisk.config import (
    APP_MIN_HEIGHT,
    APP_MIN_WIDTH,
    APP_TAGLINE,
    APP_TITLE,
    APP_VERSION,
    DISCLAIMER_TEXT,
    FINDING_TYPE_LABELS,
    SUPPORTED_DOCUMENT_EXTENSIONS,
)
from contractrisk.database.db_manager import DatabaseManager
from contractrisk.domain.models import Contract, RiskFinding
from contractrisk.gui.contract_list_panel import ContractListPanel
from contractrisk.gui.rule_editor_panel import RuleEditorPanel
from contractrisk.gui.styles import ThemeManager
from contractrisk.gui.text_view_panel import TextViewPanel
from contractrisk.gui.timeline_panel import TimelinePanel
from contractrisk.gui.widgets import CollapsiblePanel, FadeStatusBar, RoundedButton, ScoreGauge
from contractrisk.io_utils import report_writer, text_loader
from contractrisk.utils.exceptions import (
    ContractRiskError,
    DatabaseError,
    InvalidRuleConfigError,
    ReportExportError,
    UnreadableContractFileError,
)
from contractrisk.utils.logger import get_logger

logger = get_logger(__name__)


class ContractRiskApp:
    """Kapselt das Hauptfenster (`tk.Tk`) und die gesamte GUI-Orchestrierung."""

    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title(f"{APP_TITLE} v{APP_VERSION}")
        self.root.geometry(f"{APP_MIN_WIDTH}x{APP_MIN_HEIGHT}")
        self.root.minsize(APP_MIN_WIDTH, APP_MIN_HEIGHT)

        self.theme = ThemeManager(self.root, dark_mode=True)

        self.db_manager = DatabaseManager()
        self._scan_result_queue: "queue.Queue" = queue.Queue()

        try:
            self.rules = rule_engine.load_rules()
        except InvalidRuleConfigError as exc:
            messagebox.showerror("Fehler in der Regelbibliothek", str(exc))
            self.rules = []

        self.contracts: list[Contract] = []
        self.selected_contract: Optional[Contract] = None

        self._build_menu()
        self._build_layout()
        self._bind_shortcuts()
        self._load_contracts_from_database()

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ------------------------------------------------------------------
    # Layout-Aufbau
    # ------------------------------------------------------------------

    def _build_menu(self) -> None:
        menu_bar = tk.Menu(self.root)

        file_menu = tk.Menu(menu_bar, tearoff=0)
        file_menu.add_command(label="Vertrag importieren...   Strg+O", command=self._on_import_clicked)
        file_menu.add_command(label="Report exportieren...   Strg+E", command=self._on_export_report_clicked)
        file_menu.add_separator()
        file_menu.add_command(label="Beenden", command=self._on_close)
        menu_bar.add_cascade(label="Datei", menu=file_menu)

        view_menu = tk.Menu(menu_bar, tearoff=0)
        view_menu.add_command(label="Theme umschalten (hell/dunkel)", command=self._on_toggle_theme)
        view_menu.add_command(label="Regel-Editor ein-/ausblenden", command=self._toggle_detail_panel)
        menu_bar.add_cascade(label="Ansicht", menu=view_menu)

        help_menu = tk.Menu(menu_bar, tearoff=0)
        help_menu.add_command(label="Über ContractRisk Scanner", command=self._show_about_dialog)
        menu_bar.add_cascade(label="Hilfe", menu=help_menu)

        self.root.config(menu=menu_bar)

    def _build_layout(self) -> None:
        main_container = ttk.Frame(self.root, style="TFrame")
        main_container.pack(fill="both", expand=True)

        self._build_header_bar(main_container)

        content_area = ttk.Frame(main_container, style="TFrame")
        content_area.pack(fill="both", expand=True, side="top")

        # Sidebar links
        self.contract_list_panel = ContractListPanel(
            content_area, self.theme,
            on_import_clicked=self._on_import_clicked,
            on_contract_selected=self._on_contract_selected,
            on_contract_deleted=self._on_contract_deleted,
        )
        self.contract_list_panel.pack(side="left", fill="y")

        # Mittlere Spalte: Risiko-Übersicht (oben) + PanedWindow mit
        # Textansicht und Zeitleiste
        center_column = ttk.Frame(content_area, style="TFrame")
        center_column.pack(side="left", fill="both", expand=True)

        self._build_risk_overview(center_column)

        center_paned = ttk.PanedWindow(center_column, orient="vertical")
        center_paned.pack(fill="both", expand=True)

        self.text_view_panel = TextViewPanel(
            center_paned, self.theme, on_finding_clicked=self._on_finding_clicked,
        )
        center_paned.add(self.text_view_panel, weight=3)

        self.timeline_panel = TimelinePanel(center_paned, self.theme)
        center_paned.add(self.timeline_panel, weight=1)

        # Rechtes, ein-/ausblendbares Detailpanel
        self.detail_panel_container = CollapsiblePanel(content_area, target_width=340)
        self.detail_panel_container.pack(side="right", fill="y")
        self._build_detail_panel_content()

        # Statusleiste
        self.status_bar = FadeStatusBar(main_container, self.theme)
        self.status_bar.pack(side="bottom", fill="x")
        self.status_bar.set_info(DISCLAIMER_TEXT)

    def _build_header_bar(self, parent: ttk.Frame) -> None:
        """Obere App-Leiste mit Branding, Tagline und Theme-Umschalter -
        macht die Anwendung auf den ersten Blick als seriöses,
        eigenständiges Werkzeug erkennbar (statt einer reinen
        Formularsammlung)."""
        header = ttk.Frame(parent, style="Header.TFrame")
        header.pack(fill="x", side="top")

        inner = ttk.Frame(header, style="Header.TFrame")
        inner.pack(fill="x", padx=24, pady=14)

        branding = ttk.Frame(inner, style="Header.TFrame")
        branding.pack(side="left")

        title_row = ttk.Frame(branding, style="Header.TFrame")
        title_row.pack(anchor="w")
        ttk.Label(title_row, text="🛡️", style="Header.TLabel", font=("Segoe UI", 16)).pack(side="left")
        ttk.Label(
            title_row, text=APP_TITLE, style="Header.TLabel",
            font=("Segoe UI Semibold", 15, "bold"),
        ).pack(side="left", padx=(6, 0))

        ttk.Label(branding, text=APP_TAGLINE, style="HeaderSubtitle.TLabel").pack(anchor="w")

        actions = ttk.Frame(inner, style="Header.TFrame")
        actions.pack(side="right")

        self._theme_toggle_button = RoundedButton(
            actions, self.theme, text="Helles Design", icon="☀️",
            command=self._on_toggle_theme, variant="secondary",
            font=("Segoe UI", 9, "bold"), padding_x=12, padding_y=7,
            canvas_bg=self.theme.colors["bg_secondary"],
        )
        self._theme_toggle_button.pack(side="right")
        self._update_theme_toggle_label()

    def _build_risk_overview(self, parent: ttk.Frame) -> None:
        """Zeigt zwei getrennte Score-Gauges für den aktuell ausgewählten
        Vertrag: Vertragsrisiko (Klauseln) und Betrugs-/Scam-Risiko. Die
        Trennung macht auf einen Blick klar, dass es sich um zwei
        unterschiedliche Risikoarten handelt (siehe
        analysis/risk_scoring.split_scores)."""
        self._risk_overview_frame = ttk.Frame(parent, style="Card.TFrame")
        self._risk_overview_frame.pack(fill="x", padx=24, pady=(20, 0))

        inner = ttk.Frame(self._risk_overview_frame, style="Card.TFrame")
        inner.pack(fill="x", padx=20, pady=16)

        self._contract_score_gauge = ScoreGauge(inner, self.theme, title="VERTRAGSRISIKO", width=300)
        self._contract_score_gauge.pack(side="left", fill="x", expand=True, padx=(0, 24))

        self._fraud_score_gauge = ScoreGauge(inner, self.theme, title="🚩 BETRUGS-/SCAM-RISIKO", width=300)
        self._fraud_score_gauge.pack(side="left", fill="x", expand=True)

        # Vor der ersten Vertragsauswahl ist die Übersicht ausgeblendet,
        # damit keine bedeutungslosen "0"-Werte angezeigt werden.
        self._risk_overview_frame.pack_forget()

    def _update_theme_toggle_label(self) -> None:
        if self.theme.dark_mode:
            self._theme_toggle_button.set_text("Helles Design")
        else:
            self._theme_toggle_button.set_text("Dunkles Design")

    def _build_detail_panel_content(self) -> None:
        container = self.detail_panel_container

        self._detail_notebook = ttk.Notebook(container)
        self._detail_notebook.pack(fill="both", expand=True, padx=8, pady=8)

        # Tab 1: Klausel-Detailansicht
        self._finding_detail_frame = ttk.Frame(self._detail_notebook, style="Card.TFrame")
        self._detail_notebook.add(self._finding_detail_frame, text="Klausel-Details")
        self._build_finding_detail_tab()

        # Tab 2: Regel-Editor
        self.rule_editor_panel = RuleEditorPanel(
            self._detail_notebook, self.theme, self.rules,
            on_rules_changed=self._on_rules_changed,
        )
        self._detail_notebook.add(self.rule_editor_panel, text="Regel-Editor")

    def _build_finding_detail_tab(self) -> None:
        frame = self._finding_detail_frame
        ttk.Label(frame, text="Klausel-Details", style="Card.TLabel",
                  font=("Segoe UI", 12, "bold")).pack(anchor="w", padx=12, pady=(12, 6))

        self._detail_category_label = ttk.Label(frame, text="Kategorie: -", style="Card.TLabel",
                                                  wraplength=300, justify="left")
        self._detail_category_label.pack(anchor="w", padx=12, pady=2)

        self._detail_type_label = ttk.Label(frame, text="Typ: -", style="Card.TLabel")
        self._detail_type_label.pack(anchor="w", padx=12, pady=2)

        self._detail_severity_label = ttk.Label(frame, text="Schweregrad: -", style="Card.TLabel")
        self._detail_severity_label.pack(anchor="w", padx=12, pady=2)

        self._detail_confidence_label = ttk.Label(frame, text="Konfidenz: -", style="Card.TLabel")
        self._detail_confidence_label.pack(anchor="w", padx=12, pady=2)

        ttk.Label(frame, text="Erklärung:", style="Card.TLabel",
                  font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=12, pady=(10, 2))
        self._detail_explanation_label = ttk.Label(
            frame, text="Klicken Sie im Text auf eine markierte Stelle, um Details zu sehen.",
            style="Card.TLabel", wraplength=300, justify="left",
        )
        self._detail_explanation_label.pack(anchor="w", padx=12, pady=2)

        ttk.Label(frame, text="Begründung dieses konkreten Fundes:", style="Card.TLabel",
                  font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=12, pady=(10, 2))
        self._detail_reasoning_label = ttk.Label(
            frame, text="-", style="Card.TLabel", wraplength=300, justify="left",
            foreground=self.theme.colors["text_secondary"],
        )
        self._detail_reasoning_label.pack(anchor="w", padx=12, pady=2)

        ttk.Label(frame, text="Fundstelle im Dokument:", style="Card.TLabel",
                  font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=12, pady=(10, 2))
        self._detail_context_label = ttk.Label(
            frame, text="-", style="Card.TLabel", wraplength=300, justify="left",
            foreground=self.theme.colors["text_secondary"],
        )
        self._detail_context_label.pack(anchor="w", padx=12, pady=2)

    def _bind_shortcuts(self) -> None:
        self.root.bind("<Control-o>", lambda e: self._on_import_clicked())
        self.root.bind("<Control-e>", lambda e: self._on_export_report_clicked())

    # ------------------------------------------------------------------
    # Vertrags-Import & Scan
    # ------------------------------------------------------------------

    def _on_import_clicked(self) -> None:
        # Kombinierter Filter über alle unterstützten Formate zuerst, damit
        # der Nutzer im Standardfall nicht manuell umschalten muss; darunter
        # ein Filter je Einzelformat sowie "Alle Dateien" als Fallback (z. B.
        # falls die Endung fehlt oder unüblich groß-/kleingeschrieben ist).
        all_supported_pattern = [f"*{ext}" for ext in SUPPORTED_DOCUMENT_EXTENSIONS]
        filetypes = [("Alle unterstützten Dokumente", " ".join(all_supported_pattern))]
        filetypes += [
            (f"{label} (*{ext})", f"*{ext}")
            for ext, label in sorted(SUPPORTED_DOCUMENT_EXTENSIONS.items())
        ]
        filetypes.append(("Alle Dateien", "*.*"))

        file_paths = filedialog.askopenfilenames(
            title="Vertragsdateien auswählen",
            filetypes=filetypes,
        )
        if not file_paths:
            return

        contract_start = self._ask_for_contract_start_date()

        loaded_contracts, load_errors = text_loader.load_contracts_from_files(list(file_paths))

        if load_errors:
            messagebox.showwarning(
                "Import teilweise fehlgeschlagen",
                "Folgende Dateien konnten nicht importiert werden:\n\n" + "\n\n".join(load_errors),
            )

        if not loaded_contracts:
            return

        for contract in loaded_contracts:
            contract.vertragsbeginn = contract_start

        self.status_bar.show_message(f"Scanne {len(loaded_contracts)} Vertrag/Verträge...", kind="info")
        self._run_scan_in_background(loaded_contracts)

    def _ask_for_contract_start_date(self) -> Optional[date]:
        """Fragt den Nutzer nach einem Vertragsstart-/Stichtag, der für die
        Fristenberechnung benötigt wird. Ein leeres Feld bedeutet: keine
        konkrete Datumsberechnung, nur Erkennung der Formulierungen."""
        answer = simpledialog.askstring(
            "Vertragsstart / Stichtag",
            "Bitte Vertragsbeginn im Format TT.MM.JJJJ angeben\n"
            "(leer lassen, falls unbekannt - Fristen werden dann nur erkannt,\n"
            "aber nicht in konkrete Termine umgerechnet):",
            parent=self.root,
        )
        if not answer:
            return None
        try:
            return datetime.strptime(answer.strip(), "%d.%m.%Y").date()
        except ValueError:
            messagebox.showwarning(
                "Ungültiges Datum",
                "Das Datum konnte nicht interpretiert werden - es wird ohne "
                "Stichtag fortgefahren.",
            )
            return None

    def _run_scan_in_background(self, contracts: list[Contract]) -> None:
        """Startet den Textscan in einem Hintergrund-Thread, damit die GUI
        währenddessen nicht einfriert. Ergebnisse werden sicher über eine
        Queue an den Main-Thread zurückgegeben."""

        def worker() -> None:
            try:
                for contract in contracts:
                    rule_findings = rule_engine.scan_contract_text(contract.originaltext, self.rules)
                    contradiction_findings = consistency_checker.detect_contradictions(
                        contract.originaltext
                    )
                    preliminary_findings = rule_findings + contradiction_findings
                    combo_findings = fraud_pattern_analyzer.detect_combined_fraud_signals(
                        preliminary_findings
                    )
                    # Alle drei Analyseergebnisse werden zusammengeführt und
                    # chronologisch nach Position im Text sortiert, damit
                    # sie in der markierten Textansicht und im Report in
                    # einer nachvollziehbaren Reihenfolge erscheinen.
                    combined_findings = sorted(
                        preliminary_findings + combo_findings, key=lambda f: f.start_index
                    )
                    contract.findings = combined_findings
                    contract.risk_score = risk_scoring.calculate_risk_score(combined_findings)
                    contract.risk_level = risk_scoring.determine_risk_level(contract.risk_score)
                    contract.vertrags_risiko_score, contract.betrugs_risiko_score = (
                        risk_scoring.split_scores(combined_findings)
                    )
                    contract.deadlines = deadline_forecaster.detect_deadlines(
                        contract.originaltext, contract.vertragsbeginn,
                    )
                self._scan_result_queue.put(("success", contracts))
            except ContractRiskError as exc:
                self._scan_result_queue.put(("error", str(exc)))
            except Exception as exc:  # letzte Sicherheitsnetz-Ebene für die GUI
                logger.exception("Unerwarteter Fehler beim Scan")
                self._scan_result_queue.put(("error", f"Unerwarteter Fehler: {exc}"))

        self.status_bar.start_progress()
        threading.Thread(target=worker, daemon=True).start()
        self.root.after(100, self._poll_scan_queue)

    def _poll_scan_queue(self) -> None:
        try:
            status, payload = self._scan_result_queue.get_nowait()
        except queue.Empty:
            self.root.after(100, self._poll_scan_queue)
            return

        self.status_bar.stop_progress()

        if status == "error":
            self.status_bar.show_message(f"Fehler beim Scan: {payload}", kind="error")
            messagebox.showerror("Fehler beim Scan", payload)
            return

        contracts: list[Contract] = payload
        for contract in contracts:
            try:
                contract.id = self.db_manager.save_contract(contract)
            except DatabaseError as exc:
                messagebox.showerror("Datenbankfehler", str(exc))

        self.status_bar.show_message(
            f"{len(contracts)} Vertrag/Verträge erfolgreich gescannt und gespeichert.",
            kind="success",
        )
        self._load_contracts_from_database()

    # ------------------------------------------------------------------
    # Vertragsübersicht / Auswahl
    # ------------------------------------------------------------------

    def _load_contracts_from_database(self) -> None:
        try:
            self.contracts = self.db_manager.load_all_contracts()
        except DatabaseError as exc:
            messagebox.showerror("Datenbankfehler", str(exc))
            self.contracts = []

        self.contract_list_panel.set_contracts(self.contracts)

        if self.contracts and self.selected_contract is None:
            self._on_contract_selected(self.contracts[0])

    def _on_contract_selected(self, contract: Contract) -> None:
        self.selected_contract = contract
        self.text_view_panel.show_contract(contract)
        self.timeline_panel.show_contract(contract)
        self._update_risk_overview(contract)
        format_info = f"{contract.quellformat}  |  " if contract.quellformat else ""
        self.status_bar.set_info(
            f"{contract.dateiname}  |  {format_info}{contract.anzahl_woerter} Wörter  |  "
            f"{contract.anzahl_klauseln} Auffälligkeit(en) gefunden"
        )

    def _update_risk_overview(self, contract: Contract) -> None:
        if not self._risk_overview_frame.winfo_ismapped():
            self._risk_overview_frame.pack(fill="x", padx=24, pady=(20, 0))

        contract_level = risk_scoring.determine_risk_level(contract.vertrags_risiko_score)
        fraud_level = risk_scoring.determine_risk_level(contract.betrugs_risiko_score)

        self._contract_score_gauge.set_value(
            contract.vertrags_risiko_score, self.theme.risk_level_color(contract_level),
        )
        self._fraud_score_gauge.set_value(
            contract.betrugs_risiko_score, self.theme.risk_level_color(fraud_level),
        )

    def _on_contract_deleted(self, contract: Contract) -> None:
        if contract.id is None:
            return
        confirmed = messagebox.askyesno(
            "Vertrag löschen", f"Vertrag '{contract.dateiname}' wirklich löschen?"
        )
        if not confirmed:
            return
        try:
            self.db_manager.delete_contract(contract.id)
        except DatabaseError as exc:
            messagebox.showerror("Datenbankfehler", str(exc))
            return

        if self.selected_contract is contract:
            self.selected_contract = None
        self._load_contracts_from_database()
        self.status_bar.show_message(f"Vertrag '{contract.dateiname}' gelöscht.", kind="info")

    # ------------------------------------------------------------------
    # Detail-/Regel-Editor-Panel
    # ------------------------------------------------------------------

    def _on_finding_clicked(self, finding: RiskFinding) -> None:
        self._detail_notebook.select(self._finding_detail_frame)
        if not self.detail_panel_container.is_expanded:
            self.detail_panel_container.expand()

        self._detail_category_label.configure(text=f"Kategorie: {finding.kategorie}")

        type_label = FINDING_TYPE_LABELS.get(finding.typ, finding.typ)
        type_icon = "🚩 " if finding.typ == "betrug" else ""
        self._detail_type_label.configure(
            text=f"Typ: {type_icon}{type_label}",
            foreground=self.theme.finding_type_color(finding.typ),
        )

        self._detail_severity_label.configure(
            text=f"Schweregrad: {finding.schweregrad.upper()}",
            foreground=self.theme.severity_color(finding.schweregrad),
        )

        confidence_display = {
            "hoch": "Hoch (eindeutiger Treffer)",
            "mittel": "Mittel (Kontext prüfen)",
            "niedrig": "Niedrig (möglicherweise Fehlalarm - bitte prüfen)",
        }.get(finding.confidence, finding.confidence)
        confidence_color = {
            "hoch": self.theme.colors["severity_hoch"] if finding.schweregrad == "hoch" else self.theme.colors["text_primary"],
            "mittel": self.theme.colors["severity_mittel"],
            "niedrig": self.theme.colors["text_muted"],
        }.get(finding.confidence, self.theme.colors["text_primary"])
        self._detail_confidence_label.configure(
            text=f"Konfidenz: {confidence_display}", foreground=confidence_color,
        )

        self._detail_explanation_label.configure(text=finding.erklaerung)
        self._detail_reasoning_label.configure(text=finding.begruendung)
        self._detail_context_label.configure(text=f"„{finding.fundstelle_text}“")

        self.text_view_panel.scroll_to_finding(finding)

    def _toggle_detail_panel(self) -> None:
        self.detail_panel_container.toggle()

    def _on_rules_changed(self, updated_rules) -> None:
        self.rules = updated_rules
        self.status_bar.show_message("Regelbibliothek gespeichert.", kind="success")

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    def _on_export_report_clicked(self) -> None:
        if self.selected_contract is None:
            messagebox.showinfo("Kein Vertrag ausgewählt", "Bitte zuerst einen Vertrag auswählen.")
            return

        target_path = filedialog.asksaveasfilename(
            title="Report speichern unter",
            defaultextension=".txt",
            filetypes=[("Textdatei", "*.txt")],
            initialfile=f"report_{self.selected_contract.dateiname}",
        )
        if not target_path:
            return

        try:
            saved_path = report_writer.export_report(self.selected_contract, target_path)
        except ReportExportError as exc:
            messagebox.showerror("Fehler beim Export", str(exc))
            return

        self.status_bar.show_message(f"Report exportiert: {saved_path}", kind="success")

    # ------------------------------------------------------------------
    # Theme, About, Beenden
    # ------------------------------------------------------------------

    def _on_toggle_theme(self) -> None:
        self.theme.toggle_theme()
        self._update_theme_toggle_label()
        self._theme_toggle_button.refresh_theme(canvas_bg=self.theme.colors["bg_secondary"])
        self.contract_list_panel.refresh_theme()
        self._contract_score_gauge.refresh_theme()
        self._fraud_score_gauge.refresh_theme()
        if self.selected_contract is not None:
            self.text_view_panel.show_contract(self.selected_contract)
            self.timeline_panel.show_contract(self.selected_contract)
            self._update_risk_overview(self.selected_contract)

    def _show_about_dialog(self) -> None:
        messagebox.showinfo(
            "Über ContractRisk Scanner",
            f"ContractRisk Scanner v{APP_VERSION}\n\n"
            "Regelbasierte Analyse von Vertragstexten auf riskante Klauseln "
            "und kritische Fristen.\n\n" + DISCLAIMER_TEXT,
        )

    def _on_close(self) -> None:
        if self.rule_editor_panel.has_unsaved_changes():
            confirmed = messagebox.askyesno(
                "Ungespeicherte Änderungen",
                "Im Regel-Editor gibt es ungespeicherte Änderungen. "
                "Trotzdem beenden?",
            )
            if not confirmed:
                return
        self.root.destroy()

    def run(self) -> None:
        self.root.mainloop()
