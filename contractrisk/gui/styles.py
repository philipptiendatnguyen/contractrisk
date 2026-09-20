"""
gui/styles.py
--------------
Zentrales Design-System der Anwendung. Bündelt Farben, Schriftarten,
Abstände und ttk-Style-Konfiguration an einer Stelle, damit ein
einheitlicher, professioneller Look entsteht und Theme-Wechsel
(dunkel/hell) zentral gesteuert werden können.

Design-Prinzipien dieser Überarbeitung:
- EIN Abstands-Raster (8px-Vielfache, siehe config.SPACE_*) statt frei
  gewählter Einzelwerte, damit Panels konsistent "atmen".
- Klare Farb-Hierarchie: bg_primary < bg_secondary < bg_elevated <
  bg_card < bg_hover < bg_pressed (jede Stufe etwas heller), damit
  Ebenen (Fenster / Sidebar / Karten / interaktive Zustände) auch ohne
  Schatten klar unterscheidbar sind.
- Ein einheitlicher Akzentton (`accent`) für alle primären Aktionen,
  ein zweiter, bewusst andersfarbiger Akzent (`fraud_accent`) NUR für
  Betrugs-/Scam-Funde, damit sich diese Risikoart visuell klar von
  gewöhnlichen Vertragsklausel-Risiken abhebt.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from contractrisk.config import (
    COLORS_DARK,
    COLORS_LIGHT,
    FONT_FAMILY_BODY,
    FONT_FAMILY_HEADING,
    FONT_FAMILY_MONO,
    FONT_SIZE_BODY,
    FONT_SIZE_DISPLAY,
    FONT_SIZE_SMALL,
    FONT_SIZE_SUBTITLE,
    FONT_SIZE_TINY,
    FONT_SIZE_TITLE,
    SPACE_MD,
    SPACE_SM,
    SPACE_XS,
)


class ThemeManager:
    """Verwaltet das aktuell aktive Farbschema (dunkel/hell) und
    konfiguriert die ttk-Styles entsprechend."""

    def __init__(self, root: tk.Tk, dark_mode: bool = True) -> None:
        self.root = root
        self.dark_mode = dark_mode
        self.style = ttk.Style(root)
        # "clam" lässt sich am zuverlässigsten umfärben (im Gegensatz zu
        # nativen Themes wie "vista"/"aqua")
        self.style.theme_use("clam")
        self._listeners: list = []
        self.apply_theme()

    @property
    def colors(self) -> dict:
        return COLORS_DARK if self.dark_mode else COLORS_LIGHT

    def on_theme_changed(self, callback) -> None:
        """Registriert einen Callback, der bei jedem Theme-Wechsel
        aufgerufen wird (z. B. um Canvas-basierte Custom-Widgets, die
        ttk-Styles nicht automatisch mitbekommen, neu zu zeichnen)."""
        self._listeners.append(callback)

    def toggle_theme(self) -> None:
        self.dark_mode = not self.dark_mode
        self.apply_theme()
        for callback in self._listeners:
            callback()

    def apply_theme(self) -> None:
        c = self.colors
        root = self.root
        style = self.style

        root.configure(bg=c["bg_primary"])

        # --- Basis-Container -------------------------------------------
        style.configure("TFrame", background=c["bg_primary"], borderwidth=0)
        style.configure("Card.TFrame", background=c["bg_card"], borderwidth=0, relief="flat")
        style.configure("Elevated.TFrame", background=c["bg_elevated"], borderwidth=0)
        style.configure("Sidebar.TFrame", background=c["bg_secondary"])
        style.configure("Header.TFrame", background=c["bg_secondary"])

        # --- Typografie ---------------------------------------------------
        style.configure(
            "TLabel", background=c["bg_primary"], foreground=c["text_primary"],
            font=(FONT_FAMILY_BODY, FONT_SIZE_BODY),
        )
        style.configure(
            "Card.TLabel", background=c["bg_card"], foreground=c["text_primary"],
            font=(FONT_FAMILY_BODY, FONT_SIZE_BODY),
        )
        style.configure(
            "Header.TLabel", background=c["bg_secondary"], foreground=c["text_primary"],
            font=(FONT_FAMILY_BODY, FONT_SIZE_BODY),
        )
        style.configure(
            "Display.TLabel", background=c["bg_secondary"], foreground=c["text_primary"],
            font=(FONT_FAMILY_HEADING, FONT_SIZE_DISPLAY, "bold"),
        )
        style.configure(
            "Title.TLabel", background=c["bg_primary"], foreground=c["text_primary"],
            font=(FONT_FAMILY_HEADING, FONT_SIZE_TITLE, "bold"),
        )
        style.configure(
            "CardTitle.TLabel", background=c["bg_card"], foreground=c["text_primary"],
            font=(FONT_FAMILY_HEADING, FONT_SIZE_TITLE, "bold"),
        )
        style.configure(
            "Subtitle.TLabel", background=c["bg_primary"], foreground=c["text_secondary"],
            font=(FONT_FAMILY_BODY, FONT_SIZE_SUBTITLE),
        )
        style.configure(
            "HeaderSubtitle.TLabel", background=c["bg_secondary"], foreground=c["text_secondary"],
            font=(FONT_FAMILY_BODY, FONT_SIZE_SMALL),
        )
        style.configure(
            "Muted.TLabel", background=c["bg_primary"], foreground=c["text_muted"],
            font=(FONT_FAMILY_BODY, FONT_SIZE_SMALL),
        )
        style.configure(
            "CardMuted.TLabel", background=c["bg_card"], foreground=c["text_secondary"],
            font=(FONT_FAMILY_BODY, FONT_SIZE_SMALL),
        )
        style.configure(
            "SidebarMuted.TLabel", background=c["bg_secondary"], foreground=c["text_muted"],
            font=(FONT_FAMILY_BODY, FONT_SIZE_SMALL),
        )
        style.configure(
            "SectionHeading.TLabel", background=c["bg_primary"], foreground=c["text_muted"],
            font=(FONT_FAMILY_BODY, FONT_SIZE_TINY, "bold"),
        )

        # --- Buttons --------------------------------------------------------
        style.configure(
            "TButton", background=c["accent"], foreground="#FFFFFF",
            font=(FONT_FAMILY_BODY, FONT_SIZE_BODY, "bold"),
            borderwidth=0, focusthickness=0, padding=(SPACE_MD, SPACE_SM),
        )
        style.map(
            "TButton",
            background=[("active", c["accent_hover"]), ("pressed", c["accent_hover"])],
        )
        style.configure(
            "Secondary.TButton", background=c["bg_hover"], foreground=c["text_primary"],
            font=(FONT_FAMILY_BODY, FONT_SIZE_BODY), borderwidth=0, padding=(SPACE_SM + 2, SPACE_XS + 2),
        )
        style.map(
            "Secondary.TButton",
            background=[("active", c["bg_pressed"]), ("pressed", c["bg_pressed"])],
        )
        style.configure(
            "Ghost.TButton", background=c["bg_secondary"], foreground=c["text_secondary"],
            font=(FONT_FAMILY_BODY, FONT_SIZE_SMALL), borderwidth=0, padding=(SPACE_SM, SPACE_XS),
        )
        style.map(
            "Ghost.TButton",
            background=[("active", c["bg_hover"])],
            foreground=[("active", c["text_primary"])],
        )
        style.configure(
            "Danger.TButton", background=c["severity_hoch"], foreground="#FFFFFF",
            font=(FONT_FAMILY_BODY, FONT_SIZE_BODY), borderwidth=0, padding=(SPACE_SM + 2, SPACE_XS + 2),
        )

        # --- Container-Widgets -----------------------------------------
        style.configure("TPanedwindow", background=c["bg_primary"])
        style.configure("TNotebook", background=c["bg_primary"], borderwidth=0)
        style.configure(
            "TNotebook.Tab", background=c["bg_secondary"], foreground=c["text_secondary"],
            padding=(SPACE_MD - 2, SPACE_SM - 2), font=(FONT_FAMILY_BODY, FONT_SIZE_BODY),
            borderwidth=0,
        )
        style.map(
            "TNotebook.Tab",
            background=[("selected", c["bg_card"])],
            foreground=[("selected", c["text_primary"]), ("!selected", c["text_muted"])],
        )
        style.configure(
            "Treeview", background=c["bg_card"], foreground=c["text_primary"],
            fieldbackground=c["bg_card"], borderwidth=0,
            font=(FONT_FAMILY_BODY, FONT_SIZE_BODY), rowheight=30,
        )
        style.configure(
            "Treeview.Heading", background=c["bg_secondary"], foreground=c["text_secondary"],
            font=(FONT_FAMILY_BODY, FONT_SIZE_SMALL, "bold"), borderwidth=0,
        )
        style.map(
            "Treeview",
            background=[("selected", c["accent_soft"])],
            foreground=[("selected", c["text_primary"])],
        )
        style.configure(
            "Vertical.TScrollbar", background=c["bg_secondary"], troughcolor=c["bg_primary"],
            borderwidth=0, arrowsize=12,
        )
        style.configure(
            "TEntry", fieldbackground=c["bg_hover"], foreground=c["text_primary"],
            insertcolor=c["text_primary"], borderwidth=1, bordercolor=c["border"],
            lightcolor=c["border"], darkcolor=c["border"], padding=SPACE_SM,
        )
        style.map(
            "TEntry",
            bordercolor=[("focus", c["accent"])],
            lightcolor=[("focus", c["accent"])],
            darkcolor=[("focus", c["accent"])],
        )
        style.configure(
            "TCombobox", fieldbackground=c["bg_hover"], foreground=c["text_primary"],
            background=c["bg_hover"], arrowcolor=c["text_secondary"], padding=SPACE_XS + 2,
        )
        style.configure(
            "TCheckbutton", background=c["bg_card"], foreground=c["text_primary"],
            font=(FONT_FAMILY_BODY, FONT_SIZE_BODY),
        )
        style.configure(
            "Horizontal.TProgressbar", background=c["accent"], troughcolor=c["bg_hover"],
            borderwidth=0, thickness=4,
        )

    def severity_color(self, severity: str) -> str:
        return self.colors.get(f"severity_{severity}", self.colors["text_primary"])

    def risk_level_color(self, level: str) -> str:
        return self.colors.get(f"severity_{level}", self.colors["text_primary"])

    def finding_type_color(self, typ: str) -> str:
        """Liefert den Akzentton für den Fundtyp: Betrugsmuster erhalten
        bewusst einen eigenen Farbton (violett), damit sie sich auf einen
        Blick von gewöhnlichen Vertragsklausel-Risiken abheben."""
        return self.colors["fraud_accent"] if typ == "betrug" else self.colors["accent"]


MONOSPACE_FONT = (FONT_FAMILY_MONO, FONT_SIZE_BODY)
HEADING_FONT = (FONT_FAMILY_HEADING, FONT_SIZE_SUBTITLE, "bold")
DISPLAY_FONT = (FONT_FAMILY_HEADING, FONT_SIZE_DISPLAY, "bold")
