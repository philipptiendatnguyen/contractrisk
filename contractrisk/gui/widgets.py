"""
gui/widgets.py
----------------
Wiederverwendbare, selbstgebaute UI-Komponenten, die es in Standard-tkinter
so nicht gibt: farbige Risiko-Badges und Buttons mit abgerundeten Ecken,
ein horizontaler "Score-Gauge" zur Risikodarstellung, eine Statusleiste
mit sanft ein-/ausblendenden Meldungen (inkl. Icon und optionaler
Fortschrittsanzeige) sowie ein Panel-Container, der sich animiert ein-
und ausblenden lässt.

Alle Animationen laufen über `tkinter.after()` mit einer Ease-Out-Kurve
(schnell am Anfang, sanft auslaufend) statt linearer Schritte - es wird
bewusst kein externes Animations-Framework verwendet.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable, Optional

from contractrisk.gui.styles import ThemeManager

_STATUS_ICONS = {"success": "✓", "error": "✕", "warning": "⚠", "info": "ℹ"}


def ease_out_cubic(t: float) -> float:
    """Easing-Funktion für flüssige, natürlich wirkende Animationen:
    startet schnell und läuft sanft aus (statt linear/abrupt zu stoppen).
    `t` liegt in [0, 1], das Ergebnis ebenso."""
    t = max(0.0, min(1.0, t))
    return 1 - (1 - t) ** 3


def blend_hex_colors(color_a: str, color_b: str, ratio: float) -> str:
    """Mischt zwei Hex-Farben (z. B. '#E74C3C') im Verhältnis `ratio`
    (0 = ganz color_a, 1 = ganz color_b)."""
    def to_rgb(hex_color: str) -> tuple[int, int, int]:
        hex_color = hex_color.lstrip("#")
        if len(hex_color) != 6:
            return (255, 255, 255)
        return tuple(int(hex_color[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]

    ra, ga, ba = to_rgb(color_a)
    rb, gb, bb = to_rgb(color_b)
    r = round(ra + (rb - ra) * ratio)
    g = round(ga + (gb - ga) * ratio)
    b = round(ba + (bb - ba) * ratio)
    return f"#{r:02x}{g:02x}{b:02x}"


def _resolve_parent_bg(parent, explicit_bg: str | None, fallback: str) -> str:
    """Ermittelt die Hintergrundfarbe für ein Canvas-basiertes Widget.

    Reihenfolge: (1) explizit übergebene Farbe, (2) tatsächliche
    Hintergrundfarbe des Parent-Widgets (funktioniert zuverlässig nur bei
    klassischen tk-Widgets, ttk-Widgets kennen die Option "background"
    i. d. R. nicht und werfen dabei einen TclError), (3) Fallback-Farbe.
    Explizit übergebene Farben haben IMMER Vorrang, damit der Aufrufer
    (der die tatsächliche ttk-Style-Hintergrundfarbe kennt) die Kontrolle
    behält - das ist der zuverlässigere Weg bei ttk-Parents.
    """
    if explicit_bg is not None:
        return explicit_bg
    try:
        return parent.cget("background")
    except tk.TclError:
        return fallback


class RoundedBadge(tk.Canvas):
    """Ein kleines, abgerundetes Label mit Hintergrundfarbe - z. B. für
    den Risiko-Score oder den Schweregrad einer Klausel. `ttk` selbst
    unterstützt keine abgerundeten Ecken, daher wird hier mit einem
    Canvas gearbeitet."""

    def __init__(self, parent, text: str, bg_color: str, fg_color: str = "#FFFFFF",
                 font=("Segoe UI", 9, "bold"), padding_x: int = 10, padding_y: int = 4,
                 canvas_bg: str | None = None, **kwargs) -> None:
        resolved_bg = _resolve_parent_bg(parent, canvas_bg, "#000000")
        super().__init__(parent, highlightthickness=0, bd=0, bg=resolved_bg, **kwargs)
        self._bg_color = bg_color
        self._fg_color = fg_color
        self._text = text
        self._font = font
        self._padding_x = padding_x
        self._padding_y = padding_y
        self._draw()

    def _draw(self) -> None:
        self.delete("all")
        text_id = self.create_text(
            0, 0, text=self._text, fill=self._fg_color, font=self._font, anchor="nw",
        )
        bbox = self.bbox(text_id)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]

        width = text_width + 2 * self._padding_x
        height = text_height + 2 * self._padding_y
        radius = height / 2

        self.configure(width=width, height=height)
        self.delete("all")
        _draw_rounded_rect(self, 0, 0, width, height, radius, fill=self._bg_color)
        self.create_text(
            width / 2, height / 2, text=self._text, fill=self._fg_color,
            font=self._font, anchor="center",
        )

    def update_text(self, text: str, bg_color: str | None = None) -> None:
        self._text = text
        if bg_color is not None:
            self._bg_color = bg_color
        self._draw()


class RoundedButton(tk.Canvas):
    """Ein anklickbarer Button mit abgerundeten Ecken, optionalem
    Icon-Präfix (Unicode-Glyphe) und sanftem Farbübergang bei Hover -
    für primäre Aktionen (z. B. "Importieren"), bei denen ein klassischer
    ttk-Button zu kantig/unauffällig wirkt.

    Varianten ("variant"): "primary" (Akzentfarbe, gefüllt), "secondary"
    (dezenter Hintergrund), "danger" (Warnfarbe).
    """

    _VARIANT_COLOR_KEYS = {
        "primary": ("accent", "accent_hover", "#FFFFFF"),
        "secondary": ("bg_hover", "bg_pressed", None),  # fg wird dynamisch gesetzt
        "danger": ("severity_hoch", "severity_hoch", "#FFFFFF"),
    }

    def __init__(self, parent, theme: ThemeManager, text: str,
                 command: Optional[Callable[[], None]] = None,
                 icon: str = "", variant: str = "primary",
                 font=("Segoe UI", 10, "bold"), padding_x: int = 18, padding_y: int = 10,
                 canvas_bg: str | None = None, **kwargs) -> None:
        resolved_bg = _resolve_parent_bg(parent, canvas_bg, theme.colors["bg_primary"])
        super().__init__(parent, highlightthickness=0, bd=0, bg=resolved_bg, cursor="hand2", **kwargs)
        self._theme = theme
        self._canvas_bg = resolved_bg
        self._text = text
        self._icon = icon
        self._command = command
        self._variant = variant
        self._font = font
        self._padding_x = padding_x
        self._padding_y = padding_y
        self._enabled = True
        self._hovering = False

        self.bind("<Button-1>", self._on_click)
        self.bind("<Enter>", lambda e: self._set_hover(True))
        self.bind("<Leave>", lambda e: self._set_hover(False))

        self._draw()

    def _resolve_colors(self) -> tuple[str, str]:
        base_key, hover_key, fixed_fg = self._VARIANT_COLOR_KEYS.get(
            self._variant, self._VARIANT_COLOR_KEYS["primary"]
        )
        c = self._theme.colors
        bg_color = c[hover_key] if self._hovering else c[base_key]
        fg_color = fixed_fg if fixed_fg else c["text_primary"]
        if not self._enabled:
            bg_color = c["bg_hover"]
            fg_color = c["text_muted"]
        return bg_color, fg_color

    def _draw(self) -> None:
        self.delete("all")
        bg_color, fg_color = self._resolve_colors()

        label_text = f"{self._icon}  {self._text}" if self._icon else self._text
        text_id = self.create_text(0, 0, text=label_text, font=self._font, anchor="nw")
        bbox = self.bbox(text_id)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        self.delete(text_id)

        width = text_width + 2 * self._padding_x
        height = text_height + 2 * self._padding_y
        radius = height / 2

        self.configure(width=width, height=height)
        _draw_rounded_rect(self, 0, 0, width, height, radius, fill=bg_color)
        self.create_text(
            width / 2, height / 2, text=label_text, fill=fg_color,
            font=self._font, anchor="center",
        )

    def _set_hover(self, hovering: bool) -> None:
        if not self._enabled or hovering == self._hovering:
            return
        self._hovering = hovering
        self._draw()

    def _on_click(self, event=None) -> None:
        if self._enabled and self._command:
            self._command()

    def set_enabled(self, enabled: bool) -> None:
        self._enabled = enabled
        self.configure(cursor="hand2" if enabled else "arrow")
        self._draw()

    def set_text(self, text: str) -> None:
        self._text = text
        self._draw()

    def refresh_theme(self, canvas_bg: str | None = None) -> None:
        """Neu zeichnen nach einem Theme-Wechsel (Farben ändern sich).
        Optional kann die neue Umgebungs-Hintergrundfarbe explizit
        übergeben werden (empfohlen bei ttk-Parents, siehe
        `_resolve_parent_bg`)."""
        self._canvas_bg = _resolve_parent_bg(self.master, canvas_bg, self._theme.colors["bg_primary"])
        self.configure(bg=self._canvas_bg)
        self._draw()


class ScoreGauge(ttk.Frame):
    """Horizontaler, abgerundeter Fortschrittsbalken zur Darstellung
    EINES Risiko-Scores (0-100) mit Titel, Zahlenwert und animiertem
    Einlauf beim Anzeigen - z. B. für "Vertragsrisiko" und
    "Betrugsrisiko" nebeneinander in der Risiko-Übersicht.
    """

    def __init__(self, parent, theme: ThemeManager, title: str, width: int = 220,
                 height: int = 10, **kwargs) -> None:
        super().__init__(parent, style="Card.TFrame", **kwargs)
        self._theme = theme
        self._width = width
        self._height = height
        self._current_value = 0.0
        self._target_value = 0.0
        self._animation_job: str | None = None
        self._fill_color = theme.colors["accent"]

        header = ttk.Frame(self, style="Card.TFrame")
        header.pack(fill="x")
        self._title_label = ttk.Label(header, text=title, style="CardMuted.TLabel")
        self._title_label.pack(side="left")
        self._value_label = ttk.Label(header, text="0", style="Card.TLabel", font=("Segoe UI", 11, "bold"))
        self._value_label.pack(side="right")

        self._canvas = tk.Canvas(
            self, width=width, height=height, highlightthickness=0, bd=0,
            bg=theme.colors["bg_card"],
        )
        self._canvas.pack(fill="x", pady=(4, 0))

        self._redraw_track()

    def _redraw_track(self) -> None:
        self._canvas.delete("track")
        _draw_rounded_rect(
            self._canvas, 0, 0, self._width, self._height, self._height / 2,
            fill=self._theme.colors["bg_hover"], tags="track",
        )
        self._canvas.tag_lower("track")

    def set_value(self, value: float, fill_color: str, animate: bool = True) -> None:
        """Setzt den angezeigten Wert (0-100). Bei `animate=True` läuft
        der Balken sanft von seinem aktuellen auf den neuen Wert."""
        value = max(0.0, min(100.0, value))
        self._fill_color = fill_color
        self._target_value = value

        if not animate:
            self._current_value = value
            self._render_fill()
            self._value_label.configure(text=f"{value:.0f}")
            return

        if self._animation_job is not None:
            self.after_cancel(self._animation_job)

        start_value = self._current_value
        start_time = self._now_ms()
        duration_ms = 450

        def tick():
            elapsed = self._now_ms() - start_time
            progress = ease_out_cubic(min(elapsed / duration_ms, 1.0))
            self._current_value = start_value + (self._target_value - start_value) * progress
            self._render_fill()
            self._value_label.configure(text=f"{self._current_value:.0f}")
            if progress < 1.0:
                self._animation_job = self.after(16, tick)
            else:
                self._animation_job = None

        tick()

    @staticmethod
    def _now_ms() -> int:
        import time
        return int(time.monotonic() * 1000)

    def _render_fill(self) -> None:
        self._canvas.delete("fill")
        fill_width = max(self._height, (self._current_value / 100.0) * self._width)
        if fill_width > 0:
            _draw_rounded_rect(
                self._canvas, 0, 0, fill_width, self._height, self._height / 2,
                fill=self._fill_color, tags="fill",
            )

    def refresh_theme(self) -> None:
        """Zeichnet Track- und Füllfarbe nach einem Theme-Wechsel neu
        (Canvas-Hintergründe werden von ttk-Styles nicht automatisch
        mitgezogen)."""
        self._canvas.configure(bg=self._theme.colors["bg_card"])
        self._redraw_track()
        self._render_fill()


class FadeStatusBar(ttk.Frame):
    """Statusleiste am unteren Fensterrand mit sanft ein-/ausblendenden,
    icon-codierten Erfolgs-/Fehlermeldungen, einem Dauer-Infotext
    (Wortanzahl etc.) sowie einer optionalen unbestimmten
    Fortschrittsanzeige (z. B. während des Hintergrund-Scans).

    Da klassisches tkinter keine echte Alpha-Transparenz für einzelne
    Widgets unterstützt, wird die "Fade"-Wirkung durch schrittweises
    Überblenden der Textfarbe zwischen Hintergrund- und Zielfarbe simuliert.
    """

    def __init__(self, parent, theme: ThemeManager, **kwargs) -> None:
        super().__init__(parent, style="Sidebar.TFrame", **kwargs)
        self._theme = theme

        self.info_label = ttk.Label(self, style="SidebarMuted.TLabel", text="Bereit.")
        self.info_label.pack(side="left", padx=16, pady=8)

        self.message_label = ttk.Label(self, style="SidebarMuted.TLabel", text="")
        self.message_label.pack(side="left", padx=8, pady=8)

        self._progress = ttk.Progressbar(self, mode="indeterminate", length=140)
        # wird erst bei Bedarf gepackt (start_progress), damit die Leiste
        # im Normalzustand nicht unnötig Platz beansprucht

        self._fade_job: str | None = None

    def set_info(self, text: str) -> None:
        self.info_label.configure(text=text)

    def show_message(self, text: str, kind: str = "info", duration_ms: int = 4000) -> None:
        """Zeigt eine icon-codierte Meldung an und blendet sie nach
        `duration_ms` wieder sanft aus."""
        color_key = {
            "success": "severity_niedrig",
            "error": "severity_hoch",
            "warning": "severity_mittel",
            "info": "text_secondary",
        }.get(kind, "text_secondary")
        color = self._theme.colors.get(color_key, self._theme.colors["text_secondary"])
        icon = _STATUS_ICONS.get(kind, "")

        if self._fade_job is not None:
            self.after_cancel(self._fade_job)
            self._fade_job = None

        self.message_label.configure(text=f"{icon}  {text}" if icon else text, foreground=color)
        self._fade_job = self.after(duration_ms, self._start_fade_out)

    def start_progress(self) -> None:
        """Blendet eine unbestimmte Fortschrittsanzeige ein (z. B. während
        des Hintergrund-Scans mehrerer Verträge)."""
        if not self._progress.winfo_ismapped():
            self._progress.pack(side="right", padx=16, pady=8)
        self._progress.start(12)

    def stop_progress(self) -> None:
        self._progress.stop()
        if self._progress.winfo_ismapped():
            self._progress.pack_forget()

    def _start_fade_out(self) -> None:
        self._fade_step(steps_remaining=10)

    def _fade_step(self, steps_remaining: int) -> None:
        if steps_remaining <= 0:
            self.message_label.configure(text="")
            self._fade_job = None
            return

        bg_color = self._theme.colors["bg_secondary"]
        current = self.message_label.cget("foreground") or bg_color
        blended = blend_hex_colors(current, bg_color, ratio=0.25)
        self.message_label.configure(foreground=blended)
        self._fade_job = self.after(40, lambda: self._fade_step(steps_remaining - 1))


class CollapsiblePanel(ttk.Frame):
    """Ein Container, der sich per `expand()`/`collapse()` sanft ein- und
    ausblenden lässt (Ease-Out-Animation der Breite)."""

    def __init__(self, parent, target_width: int = 320, **kwargs) -> None:
        super().__init__(parent, style="Card.TFrame", **kwargs)
        self._target_width = target_width
        self._current_width = 0
        self._expanded = False
        self._animation_job: str | None = None
        self.pack_propagate(False)
        self.configure(width=0)

    @property
    def is_expanded(self) -> bool:
        return self._expanded

    def toggle(self) -> None:
        self.collapse() if self._expanded else self.expand()

    def expand(self) -> None:
        self._expanded = True
        self._animate(target=self._target_width)

    def collapse(self) -> None:
        self._expanded = False
        self._animate(target=0)

    def _animate(self, target: int) -> None:
        if self._animation_job is not None:
            self.after_cancel(self._animation_job)

        start_width = self._current_width
        distance = target - start_width
        if distance == 0:
            return

        duration_ms = 220
        start_time = self._now_ms()

        def tick():
            elapsed = self._now_ms() - start_time
            progress = ease_out_cubic(min(elapsed / duration_ms, 1.0))
            self._current_width = round(start_width + distance * progress)
            self.configure(width=max(self._current_width, 0))
            if progress < 1.0:
                self._animation_job = self.after(12, tick)
            else:
                self._current_width = target
                self.configure(width=max(target, 0))
                self._animation_job = None

        tick()

    @staticmethod
    def _now_ms() -> int:
        import time
        return int(time.monotonic() * 1000)


def _draw_rounded_rect(canvas: tk.Canvas, x1, y1, x2, y2, radius, **kwargs) -> int:
    """Zeichnet ein abgerundetes Rechteck auf einem beliebigen Canvas
    (gemeinsam genutzt von RoundedBadge, RoundedButton und ScoreGauge)."""
    radius = max(0, min(radius, (x2 - x1) / 2, (y2 - y1) / 2))
    points = [
        x1 + radius, y1,
        x2 - radius, y1,
        x2, y1,
        x2, y1 + radius,
        x2, y2 - radius,
        x2, y2,
        x2 - radius, y2,
        x1 + radius, y2,
        x1, y2,
        x1, y2 - radius,
        x1, y1 + radius,
        x1, y1,
    ]
    return canvas.create_polygon(points, smooth=True, **kwargs)
