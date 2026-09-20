"""
gui/text_view_panel.py
------------------------
Zeigt den Volltext des ausgewählten Vertrags in einem scrollbaren
Text-Widget an, mit farblich hervorgehobenen Risikostellen. Ein Klick
bzw. Hover auf eine Markierung löst einen Callback aus, der z. B. das
Detail-Panel mit der passenden Erklärung befüllt.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable, Optional

from contractrisk.domain.models import Contract, RiskFinding
from contractrisk.gui.styles import MONOSPACE_FONT, ThemeManager
from contractrisk.gui.widgets import blend_hex_colors


class TextViewPanel(ttk.Frame):
    """Zentrales Panel mit dem markierten Vertragstext."""

    def __init__(self, parent, theme: ThemeManager,
                 on_finding_clicked: Callable[[RiskFinding], None], **kwargs) -> None:
        super().__init__(parent, style="TFrame", **kwargs)
        self._theme = theme
        self._on_finding_clicked = on_finding_clicked
        self._current_contract: Optional[Contract] = None
        self._tag_to_finding: dict[str, RiskFinding] = {}

        self._build_layout()

    def _build_layout(self) -> None:
        header = ttk.Frame(self, style="TFrame")
        header.pack(fill="x", padx=24, pady=(20, 8))

        title_row = ttk.Frame(header, style="TFrame")
        title_row.pack(fill="x")
        self._title_label = ttk.Label(title_row, text="Kein Vertrag ausgewählt", style="Title.TLabel")
        self._title_label.pack(side="left")

        self._meta_label = ttk.Label(header, text="", style="Subtitle.TLabel")
        self._meta_label.pack(fill="x", pady=(4, 0))

        text_container = ttk.Frame(self, style="TFrame")
        text_container.pack(fill="both", expand=True, padx=24, pady=(0, 16))

        scrollbar = ttk.Scrollbar(text_container, orient="vertical")
        scrollbar.pack(side="right", fill="y")

        self._text_widget = tk.Text(
            text_container, wrap="word", font=MONOSPACE_FONT,
            bg=self._theme.colors["bg_card"], fg=self._theme.colors["text_primary"],
            insertbackground=self._theme.colors["text_primary"],
            relief="flat", padx=16, pady=16, borderwidth=0,
            yscrollcommand=scrollbar.set, state="disabled", cursor="arrow",
        )
        self._text_widget.pack(side="left", fill="both", expand=True)
        scrollbar.configure(command=self._text_widget.yview)

        placeholder = (
            "Wählen Sie links einen Vertrag aus oder importieren Sie einen "
            "neuen Vertrag, um die markierte Textansicht zu sehen."
        )
        self._set_text(placeholder, findings=[])

    def show_contract(self, contract: Contract) -> None:
        self._current_contract = contract
        self._title_label.configure(text=contract.dateiname)

        meta_parts = [f"{contract.anzahl_woerter} Wörter", f"{contract.anzahl_klauseln} Auffälligkeit(en)"]
        if contract.anzahl_betrugsindikatoren:
            meta_parts.append(f"🚩 {contract.anzahl_betrugsindikatoren} Betrugsindikator(en)")
        self._meta_label.configure(text="  ·  ".join(meta_parts))

        self._set_text(contract.originaltext, contract.findings)

    def _set_text(self, text: str, findings: list[RiskFinding]) -> None:
        self._text_widget.configure(state="normal")
        self._text_widget.delete("1.0", "end")
        self._text_widget.insert("1.0", text)

        # Alle bisherigen Tags entfernen
        for tag in self._tag_to_finding:
            self._text_widget.tag_delete(tag)
        self._tag_to_finding.clear()

        for i, finding in enumerate(findings):
            tag_name = f"finding_{i}"
            start_pos = self._char_index_to_tk_index(text, finding.start_index)
            end_pos = self._char_index_to_tk_index(text, finding.end_index)

            color = self._theme.severity_color(finding.schweregrad)
            # Betrugs-/Scam-Funde erhalten einen dezenten violetten
            # Unterton (fraud_accent), damit sie sich auf einen Blick von
            # gewöhnlichen Vertragsklausel-Risiken unterscheiden lassen,
            # OHNE die Schweregrad-Farbcodierung (rot/gelb/grün) zu verlieren.
            if finding.typ == "betrug":
                color = blend_hex_colors(color, self._theme.colors["fraud_accent"], ratio=0.35)
            # Konfidenz beeinflusst, wie kräftig die Markierung erscheint:
            # ein eindeutiger ("hoch") Treffer sticht klar hervor, ein
            # unsicherer ("niedrig", z. B. durch Verneinung im Kontext
            # relativiert) wird nur dezent angedeutet - so bleibt auf einen
            # Blick erkennbar, welche Funde besonders vertrauenswürdig sind,
            # ohne die unsicheren Funde zu verstecken.
            blend_ratio = {"hoch": 0.72, "mittel": 0.82, "niedrig": 0.90}.get(
                finding.confidence, 0.75
            )
            self._text_widget.tag_configure(
                tag_name, background=self._blend_with_card_bg(color, ratio=blend_ratio),
                foreground=self._theme.colors["text_primary"],
                underline=(finding.confidence != "niedrig"),
            )
            self._text_widget.tag_add(tag_name, start_pos, end_pos)
            self._text_widget.tag_bind(
                tag_name, "<Button-1>",
                lambda e, f=finding: self._on_finding_clicked(f),
            )
            self._text_widget.tag_bind(
                tag_name, "<Enter>",
                lambda e, t=tag_name, c=color: self._on_tag_hover(t, c, entering=True),
            )
            self._text_widget.tag_bind(
                tag_name, "<Leave>",
                lambda e, t=tag_name, c=color, r=blend_ratio: self._on_tag_hover(t, c, entering=False, blend_ratio=r),
            )
            self._text_widget.tag_bind(
                tag_name, "<Motion>",
                lambda e: self._text_widget.configure(cursor="hand2"),
            )

            self._tag_to_finding[tag_name] = finding

        self._text_widget.configure(state="disabled")

    def _on_tag_hover(self, tag_name: str, base_color: str, entering: bool, blend_ratio: float = 0.75) -> None:
        """Leichtes Aufhellen der Markierung bei Hover, wie in den
        UX-Anforderungen gefordert."""
        if entering:
            self._text_widget.tag_configure(tag_name, background=base_color)
        else:
            self._text_widget.tag_configure(
                tag_name, background=self._blend_with_card_bg(base_color, ratio=blend_ratio)
            )

    def _blend_with_card_bg(self, color: str, ratio: float = 0.75) -> str:
        """Mischt die Schweregrad-Farbe mit dem Karten-Hintergrund im
        Verhältnis `ratio` (höherer Wert = dezenter/heller), damit die
        Hervorhebung je nach Konfidenzstufe unterschiedlich kräftig wirkt."""
        card_bg = self._theme.colors["bg_card"]

        def to_rgb(hex_color: str) -> tuple[int, int, int]:
            hex_color = hex_color.lstrip("#")
            return tuple(int(hex_color[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]

        r1, g1, b1 = to_rgb(color)
        r2, g2, b2 = to_rgb(card_bg)
        r = round(r1 * (1 - ratio) + r2 * ratio)
        g = round(g1 * (1 - ratio) + g2 * ratio)
        b = round(b1 * (1 - ratio) + b2 * ratio)
        return f"#{r:02x}{g:02x}{b:02x}"

    @staticmethod
    def _char_index_to_tk_index(text: str, char_index: int) -> str:
        """Wandelt einen reinen Zeichenindex (wie in RiskFinding
        gespeichert) in eine tkinter-Text-Index-Notation ('Zeile.Spalte')
        um."""
        # Zähle Zeilenumbrüche bis zum gesuchten Index
        preceding_text = text[:char_index]
        line_number = preceding_text.count("\n") + 1
        last_newline_pos = preceding_text.rfind("\n")
        column = char_index - (last_newline_pos + 1) if last_newline_pos != -1 else char_index
        return f"{line_number}.{column}"

    def scroll_to_finding(self, finding: RiskFinding) -> None:
        """Scrollt sanft zur Textstelle der übergebenen Klausel (wird vom
        Detail-Panel aufgerufen, wenn der Nutzer dort auf einen Treffer
        klickt)."""
        if self._current_contract is None:
            return
        index = self._char_index_to_tk_index(self._current_contract.originaltext, finding.start_index)
        self._text_widget.see(index)
