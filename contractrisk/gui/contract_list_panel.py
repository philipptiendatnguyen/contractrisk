"""
gui/contract_list_panel.py
-----------------------------
Linke Sidebar: Liste aller importierten Verträge mit Risiko-Score-Badge,
Format-Icon, Betrugsindikator-Kennzeichnung und nächstem kritischem
Termin. Bietet außerdem eine Live-Suche (nach Dateiname) und eine
Sortierauswahl. Enthält keine Business-Logik - ruft ausschließlich
übergebene Callbacks auf, wenn der Nutzer einen Vertrag auswählt, löscht
oder einen neuen importiert.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable, Optional

from contractrisk.config import FORMAT_ICONS, SIDEBAR_WIDTH
from contractrisk.domain.models import Contract
from contractrisk.gui.styles import ThemeManager
from contractrisk.gui.widgets import RoundedBadge, RoundedButton

_SORT_OPTIONS = ("Neueste zuerst", "Höchstes Risiko zuerst", "Alphabetisch (A-Z)")
_DEFAULT_FORMAT_ICON = "📃"


class ContractListPanel(ttk.Frame):
    """Zeigt die Liste importierter Verträge in der linken Sidebar an."""

    def __init__(
        self,
        parent,
        theme: ThemeManager,
        on_import_clicked: Callable[[], None],
        on_contract_selected: Callable[[Contract], None],
        on_contract_deleted: Callable[[Contract], None],
        **kwargs,
    ) -> None:
        super().__init__(parent, style="Sidebar.TFrame", width=SIDEBAR_WIDTH, **kwargs)
        self.pack_propagate(False)

        self._theme = theme
        self._on_import_clicked = on_import_clicked
        self._on_contract_selected = on_contract_selected
        self._on_contract_deleted = on_contract_deleted

        self._contracts: list[Contract] = []
        self._selected_contract_id: Optional[int] = None
        self._row_widgets: dict[int, tk.Frame] = {}

        self._search_var = tk.StringVar()
        self._search_var.trace_add("write", lambda *_: self._render_list())
        self._sort_var = tk.StringVar(value=_SORT_OPTIONS[0])
        self._sort_var.trace_add("write", lambda *_: self._render_list())

        self._build_layout()

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def _build_layout(self) -> None:
        header = ttk.Frame(self, style="Sidebar.TFrame")
        header.pack(fill="x", padx=16, pady=(16, 12))

        title_label = ttk.Label(header, text="Verträge", style="Header.TLabel",
                                 font=("Segoe UI Semibold", 15, "bold"))
        title_label.pack(side="left")

        self._count_label = ttk.Label(header, text="", style="HeaderSubtitle.TLabel")
        self._count_label.pack(side="right")

        import_button = RoundedButton(
            self, self._theme, text="Vertrag importieren", icon="＋",
            command=self._on_import_clicked, variant="primary",
            canvas_bg=self._theme.colors["bg_secondary"],
        )
        import_button.pack(fill="x", padx=16, pady=(0, 12))
        self._import_button = import_button

        # Suche + Sortierung
        controls = ttk.Frame(self, style="Sidebar.TFrame")
        controls.pack(fill="x", padx=16, pady=(0, 10))

        search_entry = ttk.Entry(controls, textvariable=self._search_var)
        search_entry.insert(0, "")
        search_entry.pack(fill="x")
        self._add_placeholder(search_entry, "🔍 Verträge durchsuchen …")

        sort_combo = ttk.Combobox(
            controls, textvariable=self._sort_var, values=_SORT_OPTIONS,
            state="readonly",
        )
        sort_combo.pack(fill="x", pady=(6, 0))

        # Scrollbarer Container für die Vertragsliste
        list_container = ttk.Frame(self, style="Sidebar.TFrame")
        list_container.pack(fill="both", expand=True, padx=8)

        self._canvas = tk.Canvas(
            list_container, highlightthickness=0, bd=0,
            bg=self._theme.colors["bg_secondary"],
        )
        scrollbar = ttk.Scrollbar(list_container, orient="vertical", command=self._canvas.yview)
        self._canvas.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side="right", fill="y")
        self._canvas.pack(side="left", fill="both", expand=True)

        self._list_frame = ttk.Frame(self._canvas, style="Sidebar.TFrame")
        self._canvas_window = self._canvas.create_window((0, 0), window=self._list_frame, anchor="nw")

        self._list_frame.bind(
            "<Configure>",
            lambda e: self._canvas.configure(scrollregion=self._canvas.bbox("all")),
        )
        self._canvas.bind(
            "<Configure>",
            lambda e: self._canvas.itemconfig(self._canvas_window, width=e.width),
        )
        # Mausrad-Unterstützung, damit die Liste ohne Scrollbar-Ziehen scrollt
        self._canvas.bind("<Enter>", lambda e: self._canvas.bind_all("<MouseWheel>", self._on_mousewheel))
        self._canvas.bind("<Leave>", lambda e: self._canvas.unbind_all("<MouseWheel>"))

    @staticmethod
    def _add_placeholder(entry: ttk.Entry, placeholder: str) -> None:
        """Einfacher Platzhaltertext für ein Such-Entry (tkinter hat kein
        natives placeholder-Attribut)."""
        entry.insert(0, placeholder)
        entry.configure(foreground="#8890A6")

        def on_focus_in(event):
            if entry.get() == placeholder:
                entry.delete(0, "end")
                entry.configure(foreground="")

        def on_focus_out(event):
            if not entry.get():
                entry.insert(0, placeholder)
                entry.configure(foreground="#8890A6")

        entry.bind("<FocusIn>", on_focus_in)
        entry.bind("<FocusOut>", on_focus_out)
        entry.configure(cursor="xterm")
        # Damit die Live-Suche den Platzhaltertext nicht als Suchbegriff
        # missversteht, wird er beim Auswerten in _render_list ignoriert.
        entry._is_placeholder_text = lambda: entry.get() == placeholder  # type: ignore[attr-defined]

    def _on_mousewheel(self, event) -> None:
        self._canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    # ------------------------------------------------------------------
    # Datenfluss
    # ------------------------------------------------------------------

    def set_contracts(self, contracts: list[Contract]) -> None:
        """Aktualisiert die angezeigte Liste (z. B. nach Import oder
        erneutem Laden aus der Datenbank)."""
        self._contracts = contracts
        self._render_list()

    def refresh_theme(self) -> None:
        """Zeichnet Canvas-basierte Elemente (Import-Button, Kartenliste)
        nach einem Theme-Wechsel mit den neuen Farben neu."""
        self._import_button.refresh_theme(canvas_bg=self._theme.colors["bg_secondary"])
        self._canvas.configure(bg=self._theme.colors["bg_secondary"])
        self._render_list()

    def _get_search_query(self) -> str:
        text = self._search_var.get().strip().lower()
        if text.startswith("🔍"):  # Platzhaltertext wurde nicht überschrieben
            return ""
        return text

    def _filtered_and_sorted_contracts(self) -> list[Contract]:
        query = self._get_search_query()
        contracts = self._contracts
        if query:
            contracts = [c for c in contracts if query in c.dateiname.lower()]

        sort_choice = self._sort_var.get()
        if sort_choice == "Höchstes Risiko zuerst":
            contracts = sorted(contracts, key=lambda c: c.risk_score, reverse=True)
        elif sort_choice == "Alphabetisch (A-Z)":
            contracts = sorted(contracts, key=lambda c: c.dateiname.lower())
        else:  # "Neueste zuerst" - Datenbankreihenfolge (bereits absteigend nach Import) beibehalten
            contracts = sorted(contracts, key=lambda c: c.importiert_am, reverse=True)
        return contracts

    def _render_list(self) -> None:
        for child in self._list_frame.winfo_children():
            child.destroy()
        self._row_widgets.clear()

        contracts = self._filtered_and_sorted_contracts()
        self._count_label.configure(
            text=f"{len(contracts)}" if contracts else ""
        )

        if not self._contracts:
            self._show_empty_state(
                "📂", "Noch keine Verträge importiert",
                "Importieren Sie eine Datei, um mit der Risikoanalyse zu beginnen.",
            )
            return

        if not contracts:
            self._show_empty_state(
                "🔍", "Keine Treffer",
                "Kein Vertrag entspricht Ihrer Suche.",
            )
            return

        for contract in contracts:
            self._create_contract_row(contract)

    def _show_empty_state(self, icon: str, title: str, subtitle: str) -> None:
        container = ttk.Frame(self._list_frame, style="Sidebar.TFrame")
        container.pack(fill="x", pady=32, padx=16)
        ttk.Label(container, text=icon, style="SidebarMuted.TLabel", font=("Segoe UI", 28)).pack()
        ttk.Label(container, text=title, style="Header.TLabel", font=("Segoe UI", 10, "bold")).pack(pady=(8, 2))
        ttk.Label(
            container, text=subtitle, style="SidebarMuted.TLabel",
            wraplength=SIDEBAR_WIDTH - 48, justify="center",
        ).pack()

    def _create_contract_row(self, contract: Contract) -> None:
        is_selected = contract.id == self._selected_contract_id
        c = self._theme.colors
        base_bg = c["accent_soft"] if is_selected else c["bg_card"]

        # Plain tk.Frame (statt ttk) für per-Instanz-Hintergrundfarbe, damit
        # Auswahl- und Hover-Zustand sich wirklich sichtbar unterscheiden
        # (ttk-Styles gelten sonst global für ALLE Zeilen gleichzeitig).
        row = tk.Frame(self._list_frame, bg=base_bg, cursor="hand2", highlightthickness=0)
        row.pack(fill="x", pady=(0, 6), padx=8)

        # Linker Akzentstreifen zeigt die aktuelle Auswahl klar an
        accent_bar = tk.Frame(row, bg=c["accent"] if is_selected else base_bg, width=3)
        accent_bar.pack(side="left", fill="y")

        content = tk.Frame(row, bg=base_bg)
        content.pack(side="left", fill="both", expand=True, padx=(9, 10), pady=9)

        header_row = tk.Frame(content, bg=base_bg)
        header_row.pack(fill="x")

        format_icon = FORMAT_ICONS.get(self._extension_of(contract.dateiname), _DEFAULT_FORMAT_ICON)
        name_label = tk.Label(
            header_row, text=f"{format_icon} {self._truncate(contract.dateiname, 20)}",
            bg=base_bg, fg=c["text_primary"], font=("Segoe UI", 10, "bold"), anchor="w",
        )
        name_label.pack(side="left", fill="x", expand=True)

        badge_frame = tk.Frame(header_row, bg=base_bg)
        badge_frame.pack(side="right")

        if contract.anzahl_betrugsindikatoren > 0:
            fraud_flag = tk.Label(
                badge_frame, text="🚩", bg=base_bg, font=("Segoe UI", 10),
            )
            fraud_flag.pack(side="left", padx=(0, 4))

        badge_color = self._theme.risk_level_color(contract.risk_level)
        badge = RoundedBadge(
            badge_frame, text=f"{contract.risk_score:.0f}", bg_color=badge_color,
            padding_x=8, padding_y=2, font=("Segoe UI", 8, "bold"), canvas_bg=base_bg,
        )
        badge.pack(side="left")

        info_parts = [f"{contract.anzahl_klauseln} Auffälligkeit(en)"]
        if contract.anzahl_betrugsindikatoren:
            info_parts.append(f"{contract.anzahl_betrugsindikatoren} Betrugsindikator(en)")
        info_label = tk.Label(
            content, text=" · ".join(info_parts), bg=base_bg, fg=c["text_secondary"],
            font=("Segoe UI", 9), anchor="w",
        )
        info_label.pack(fill="x", pady=(3, 0))

        next_deadline = contract.naechster_kritischer_termin
        deadline_text = (
            f"⏱ Nächster Termin: {next_deadline.strftime('%d.%m.%Y')}"
            if next_deadline else "Keine anstehende Frist erkannt"
        )
        deadline_label = tk.Label(
            content, text=deadline_text, bg=base_bg, fg=c["text_muted"],
            font=("Segoe UI", 8), anchor="w",
        )
        deadline_label.pack(fill="x", pady=(2, 0))

        clickable_widgets = (row, accent_bar, content, header_row, name_label, info_label, deadline_label)
        for widget in clickable_widgets:
            widget.bind("<Button-1>", lambda e, c_=contract: self._handle_select(c_))
            widget.bind("<Enter>", lambda e, r=row, ab=accent_bar, ct=content, sel=is_selected:
                        self._set_row_hover(r, ab, ct, sel, True))
            widget.bind("<Leave>", lambda e, r=row, ab=accent_bar, ct=content, sel=is_selected:
                        self._set_row_hover(r, ab, ct, sel, False))

        row.bind("<Button-3>", lambda e, c_=contract: self._on_contract_deleted(c_))

        if contract.id is not None:
            self._row_widgets[contract.id] = row

    def _set_row_hover(self, row: tk.Frame, accent_bar: tk.Frame, content: tk.Frame,
                        is_selected: bool, hovering: bool) -> None:
        c = self._theme.colors
        if is_selected:
            bg = c["accent_soft"]
        else:
            bg = c["bg_hover"] if hovering else c["bg_card"]

        row.configure(bg=bg)
        content.configure(bg=bg)
        accent_bar.configure(bg=c["accent"] if is_selected else bg)
        for child in content.winfo_children():
            self._recolor_children(child, bg)

    def _recolor_children(self, widget, bg: str) -> None:
        try:
            widget.configure(bg=bg)
        except tk.TclError:
            pass
        for child in widget.winfo_children():
            self._recolor_children(child, bg)

    def _handle_select(self, contract: Contract) -> None:
        self._selected_contract_id = contract.id
        self._render_list()
        self._on_contract_selected(contract)

    @staticmethod
    def _extension_of(filename: str) -> str:
        import os
        return os.path.splitext(filename)[1].lower()

    @staticmethod
    def _truncate(text: str, max_length: int) -> str:
        return text if len(text) <= max_length else text[: max_length - 1] + "…"
