"""
gui/timeline_panel.py
------------------------
Visualisiert die erkannten Fristen eines Vertrags als horizontale
Zeitleiste mittels matplotlib, eingebettet in tkinter über
`matplotlib.backends.backend_tkagg`.

matplotlib ist die einzige bewusste Ausnahme von der ansonsten reinen
"Standardbibliothek-only"-Regel des Projekts, weil tkinter selbst keine
Möglichkeit bietet, eine professionell wirkende, beschriftete Zeitleiste
mit vertretbarem Aufwand zu zeichnen. Alle anderen Programmteile
(Textanalyse, Datenhaltung, Fristenberechnung) kommen bewusst ohne
externe Abhängigkeiten aus.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

import matplotlib
matplotlib.use("TkAgg")

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from tkinter import ttk

from contractrisk.config import CRITICAL_DEADLINE_WARNING_DAYS, UPCOMING_DEADLINE_WARNING_DAYS
from contractrisk.domain.models import Contract, Deadline
from contractrisk.gui.styles import ThemeManager
from contractrisk.utils.exceptions import ReportExportError
from contractrisk.utils.logger import get_logger

logger = get_logger(__name__)


class TimelinePanel(ttk.Frame):
    """Zeigt die Fristen-Zeitleiste für den aktuell ausgewählten Vertrag."""

    def __init__(self, parent, theme: ThemeManager, **kwargs) -> None:
        super().__init__(parent, style="TFrame", **kwargs)
        self._theme = theme
        self._current_figure: Optional[plt.Figure] = None
        self._current_contract: Optional[Contract] = None

        self._build_layout()

    def _build_layout(self) -> None:
        header = ttk.Frame(self, style="TFrame")
        header.pack(fill="x", padx=16, pady=(8, 0))
        ttk.Label(header, text="Fristen-Zeitleiste", style="Subtitle.TLabel").pack(side="left")

        self._canvas_container = ttk.Frame(self, style="TFrame")
        self._canvas_container.pack(fill="both", expand=True, padx=16, pady=8)

        self._empty_label = ttk.Label(
            self._canvas_container,
            text="Keine Fristen erkannt oder kein Vertrag ausgewählt.",
            style="Muted.TLabel",
        )
        self._empty_label.pack(pady=24)

        self._canvas_widget = None  # type: ignore[assignment]

    def show_contract(self, contract: Contract) -> None:
        self._current_contract = contract
        self._clear_canvas()

        deadlines_with_date = [d for d in contract.deadlines if d.datum is not None]

        if not deadlines_with_date:
            self._empty_label = ttk.Label(
                self._canvas_container,
                text="Keine berechenbaren Fristen für diesen Vertrag "
                     "(ggf. fehlt ein Vertragsstart-Datum).",
                style="Muted.TLabel",
            )
            self._empty_label.pack(pady=24)
            return

        figure = self._build_figure(deadlines_with_date)
        self._current_figure = figure

        canvas = FigureCanvasTkAgg(figure, master=self._canvas_container)
        canvas.draw()
        self._canvas_widget = canvas.get_tk_widget()
        self._canvas_widget.pack(fill="both", expand=True)
        self._canvas = canvas

    def _clear_canvas(self) -> None:
        for child in self._canvas_container.winfo_children():
            child.destroy()
        if self._current_figure is not None:
            plt.close(self._current_figure)
            self._current_figure = None

    def _build_figure(self, deadlines: list[Deadline]) -> plt.Figure:
        colors = self._theme.colors
        today = date.today()

        sorted_deadlines = sorted(deadlines, key=lambda d: d.datum)  # type: ignore[arg-type, return-value]
        dates_ = [d.datum for d in sorted_deadlines]

        figure = plt.Figure(figsize=(6, 2.2), dpi=100)
        figure.patch.set_facecolor(colors["bg_primary"])
        ax = figure.add_subplot(111)
        ax.set_facecolor(colors["bg_primary"])

        # Horizontale Basislinie
        ax.axhline(y=0, color=colors["border"], linewidth=1.5, zorder=1)

        for deadline in sorted_deadlines:
            days_until = (deadline.datum - today).days  # type: ignore[operator]
            if days_until < 0:
                point_color = colors["text_muted"]
            elif days_until <= CRITICAL_DEADLINE_WARNING_DAYS:
                point_color = colors["severity_hoch"]
            elif days_until <= UPCOMING_DEADLINE_WARNING_DAYS:
                point_color = colors["severity_mittel"]
            else:
                point_color = colors["severity_niedrig"]

            ax.scatter([deadline.datum], [0], s=140, color=point_color, zorder=3,
                       edgecolors=colors["bg_primary"], linewidths=1.5)
            ax.annotate(
                f"{deadline.bezeichnung}\n{deadline.datum.strftime('%d.%m.%Y')}",  # type: ignore[union-attr]
                xy=(deadline.datum, 0), xytext=(0, 28), textcoords="offset points",
                ha="center", va="bottom", fontsize=8, color=colors["text_primary"],
            )

        # "Heute"-Markierung
        ax.axvline(x=today, color=colors["accent"], linestyle="--", linewidth=1, zorder=2)
        ax.annotate(
            "Heute", xy=(today, 0), xytext=(0, -22), textcoords="offset points",
            ha="center", va="top", fontsize=8, color=colors["accent"],
        )

        ax.set_yticks([])
        ax.spines["top"].set_visible(False)
        ax.spines["left"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.spines["bottom"].set_color(colors["border"])
        ax.tick_params(colors=colors["text_secondary"], labelsize=8)

        ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
        ax.set_ylim(-1, 1)

        # Puffer links/rechts, damit die äußeren Beschriftungen nicht abgeschnitten werden
        span = max((max(dates_) - min(dates_)).days, 1)  # type: ignore[operator]
        padding = timedelta(days=max(span * 0.15, 15))
        ax.set_xlim(min(min(dates_), today) - padding, max(max(dates_), today) + padding)  # type: ignore[operator]

        figure.tight_layout()
        return figure

    def export_as_png(self, target_path: str) -> None:
        """Exportiert die aktuell angezeigte Zeitleiste als PNG-Datei."""
        if self._current_figure is None:
            raise ReportExportError("Keine Zeitleiste zum Exportieren vorhanden.")
        try:
            self._current_figure.savefig(
                target_path, dpi=150, facecolor=self._current_figure.get_facecolor(),
            )
        except OSError as exc:
            raise ReportExportError(f"Zeitleiste konnte nicht exportiert werden: {exc}") from exc
        logger.info("Zeitleiste exportiert: %s", target_path)
