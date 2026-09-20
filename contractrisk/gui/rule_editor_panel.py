"""
gui/rule_editor_panel.py
---------------------------
GUI-Panel, um die Regelbibliothek anzusehen, zu bearbeiten, zu
aktivieren/deaktivieren oder neue Regeln hinzuzufügen. Speichert
Änderungen direkt in die `rules.json`-Datei.

Enthält keine eigene Scan-Logik - reine Verwaltung der Regeln.
"""

from __future__ import annotations

import json
import re
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable, Optional

from contractrisk.config import FINDING_TYPE_LABELS, FINDING_TYPES, RULES_FILE_PATH
from contractrisk.domain.models import Rule
from contractrisk.gui.styles import ThemeManager
from contractrisk.utils.exceptions import InvalidRuleConfigError
from contractrisk.utils.logger import get_logger

logger = get_logger(__name__)

_SEVERITY_OPTIONS = ("niedrig", "mittel", "hoch")
_TYPE_LABEL_TO_KEY = {label: key for key, label in FINDING_TYPE_LABELS.items()}


class RuleEditorPanel(ttk.Frame):
    """Panel zur Verwaltung der Regelbibliothek."""

    def __init__(self, parent, theme: ThemeManager, rules: list[Rule],
                 on_rules_changed: Callable[[list[Rule]], None], **kwargs) -> None:
        super().__init__(parent, style="Card.TFrame", **kwargs)
        self._theme = theme
        self._rules: list[Rule] = list(rules)
        self._on_rules_changed = on_rules_changed
        self._has_unsaved_changes = False

        self._selected_rule_id: Optional[str] = None

        self._build_layout()
        self._refresh_rule_list()

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def _build_layout(self) -> None:
        header = ttk.Frame(self, style="Card.TFrame")
        header.pack(fill="x", padx=12, pady=(12, 6))
        ttk.Label(header, text="Regel-Editor", style="Card.TLabel",
                  font=("Segoe UI", 12, "bold")).pack(side="left")

        list_frame = ttk.Frame(self, style="Card.TFrame")
        list_frame.pack(fill="both", expand=False, padx=12, pady=(0, 8))

        columns = ("kategorie", "typ", "schweregrad", "aktiv")
        self._tree = ttk.Treeview(list_frame, columns=columns, show="headings", height=8)
        self._tree.heading("kategorie", text="Kategorie")
        self._tree.heading("typ", text="Typ")
        self._tree.heading("schweregrad", text="Schweregrad")
        self._tree.heading("aktiv", text="Aktiv")
        self._tree.column("kategorie", width=160)
        self._tree.column("typ", width=90, anchor="center")
        self._tree.column("schweregrad", width=80, anchor="center")
        self._tree.column("aktiv", width=50, anchor="center")
        self._tree.pack(fill="both", expand=True, side="left")
        self._tree.bind("<<TreeviewSelect>>", self._on_rule_selected_in_list)

        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self._tree.yview)
        scrollbar.pack(side="right", fill="y")
        self._tree.configure(yscrollcommand=scrollbar.set)

        form_frame = ttk.Frame(self, style="Card.TFrame")
        form_frame.pack(fill="both", expand=True, padx=12, pady=(0, 8))

        self._build_form(form_frame)

        button_bar = ttk.Frame(self, style="Card.TFrame")
        button_bar.pack(fill="x", padx=12, pady=(0, 12))

        ttk.Button(button_bar, text="Neue Regel", command=self._on_new_rule_clicked,
                   style="Secondary.TButton").pack(side="left")
        ttk.Button(button_bar, text="Löschen", command=self._on_delete_rule_clicked,
                   style="Secondary.TButton").pack(side="left", padx=6)
        ttk.Button(button_bar, text="Speichern", command=self._on_save_clicked).pack(side="right")

    def _build_form(self, parent: ttk.Frame) -> None:
        ttk.Label(parent, text="ID:", style="Card.TLabel").grid(row=0, column=0, sticky="w", pady=4)
        self._id_var = tk.StringVar()
        self._id_entry = ttk.Entry(parent, textvariable=self._id_var)
        self._id_entry.grid(row=0, column=1, sticky="ew", pady=4)

        ttk.Label(parent, text="Kategorie:", style="Card.TLabel").grid(row=1, column=0, sticky="w", pady=4)
        self._category_var = tk.StringVar()
        ttk.Entry(parent, textvariable=self._category_var).grid(row=1, column=1, sticky="ew", pady=4)

        ttk.Label(parent, text="Schweregrad:", style="Card.TLabel").grid(row=2, column=0, sticky="w", pady=4)
        self._severity_var = tk.StringVar(value=_SEVERITY_OPTIONS[0])
        severity_combo = ttk.Combobox(
            parent, textvariable=self._severity_var, values=_SEVERITY_OPTIONS, state="readonly",
        )
        severity_combo.grid(row=2, column=1, sticky="ew", pady=4)

        ttk.Label(parent, text="Typ:", style="Card.TLabel").grid(row=3, column=0, sticky="w", pady=4)
        self._typ_var = tk.StringVar(value=FINDING_TYPES[0])
        typ_combo = ttk.Combobox(
            parent, textvariable=self._typ_var,
            values=[FINDING_TYPE_LABELS[t] for t in FINDING_TYPES], state="readonly",
        )
        typ_combo.grid(row=3, column=1, sticky="ew", pady=4)

        self._active_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(parent, text="Regel aktiv", variable=self._active_var).grid(
            row=4, column=0, columnspan=2, sticky="w", pady=4,
        )

        ttk.Label(parent, text="Erklärung:", style="Card.TLabel").grid(row=5, column=0, sticky="nw", pady=4)
        self._description_text = tk.Text(
            parent, height=3, wrap="word", font=("Segoe UI", 9),
            bg=self._theme.colors["bg_hover"], fg=self._theme.colors["text_primary"],
            relief="flat", padx=6, pady=6,
        )
        self._description_text.grid(row=5, column=1, sticky="ew", pady=4)

        ttk.Label(parent, text="Muster (eines je Zeile,\nregulärer Ausdruck):",
                  style="Card.TLabel").grid(row=6, column=0, sticky="nw", pady=4)
        self._patterns_text = tk.Text(
            parent, height=5, wrap="word", font=("Consolas", 9),
            bg=self._theme.colors["bg_hover"], fg=self._theme.colors["text_primary"],
            relief="flat", padx=6, pady=6,
        )
        self._patterns_text.grid(row=6, column=1, sticky="ew", pady=4)

        parent.columnconfigure(1, weight=1)

        for widget in (self._id_entry, self._description_text, self._patterns_text):
            widget.bind("<KeyRelease>", lambda e: self._mark_unsaved())
        self._category_var.trace_add("write", lambda *_: self._mark_unsaved())
        self._severity_var.trace_add("write", lambda *_: self._mark_unsaved())
        self._typ_var.trace_add("write", lambda *_: self._mark_unsaved())
        self._active_var.trace_add("write", lambda *_: self._mark_unsaved())

    # ------------------------------------------------------------------
    # Datenfluss
    # ------------------------------------------------------------------

    def _mark_unsaved(self) -> None:
        self._has_unsaved_changes = True

    def has_unsaved_changes(self) -> bool:
        return self._has_unsaved_changes

    def _refresh_rule_list(self) -> None:
        self._tree.delete(*self._tree.get_children())
        for rule in self._rules:
            self._tree.insert(
                "", "end", iid=rule.id,
                values=(
                    rule.kategorie,
                    FINDING_TYPE_LABELS.get(rule.typ, rule.typ),
                    rule.schweregrad,
                    "Ja" if rule.aktiv else "Nein",
                ),
            )

    def _on_rule_selected_in_list(self, event=None) -> None:
        selection = self._tree.selection()
        if not selection:
            return
        rule_id = selection[0]
        rule = next((r for r in self._rules if r.id == rule_id), None)
        if rule is None:
            return

        self._selected_rule_id = rule_id
        self._id_var.set(rule.id)
        self._category_var.set(rule.kategorie)
        self._severity_var.set(rule.schweregrad)
        self._typ_var.set(FINDING_TYPE_LABELS.get(rule.typ, rule.typ))
        self._active_var.set(rule.aktiv)

        self._description_text.delete("1.0", "end")
        self._description_text.insert("1.0", rule.beschreibung)

        self._patterns_text.delete("1.0", "end")
        self._patterns_text.insert("1.0", "\n".join(rule.muster))

        self._has_unsaved_changes = False

    def _on_new_rule_clicked(self) -> None:
        self._selected_rule_id = None
        self._id_var.set("")
        self._category_var.set("")
        self._severity_var.set(_SEVERITY_OPTIONS[0])
        self._typ_var.set(FINDING_TYPE_LABELS[FINDING_TYPES[0]])
        self._active_var.set(True)
        self._description_text.delete("1.0", "end")
        self._patterns_text.delete("1.0", "end")
        self._tree.selection_remove(self._tree.selection())

    def _on_delete_rule_clicked(self) -> None:
        if self._selected_rule_id is None:
            messagebox.showinfo("Hinweis", "Bitte zuerst eine Regel in der Liste auswählen.")
            return
        confirmed = messagebox.askyesno(
            "Regel löschen", f"Regel '{self._selected_rule_id}' wirklich löschen?"
        )
        if not confirmed:
            return
        self._rules = [r for r in self._rules if r.id != self._selected_rule_id]
        self._refresh_rule_list()
        self._on_new_rule_clicked()
        self._save_rules_to_disk()

    def _read_form_as_rule(self) -> Rule:
        rule_id = self._id_var.get().strip()
        if not rule_id:
            raise InvalidRuleConfigError("Die Regel benötigt eine eindeutige ID.")

        category = self._category_var.get().strip()
        if not category:
            raise InvalidRuleConfigError("Bitte eine Kategorie angeben.")

        description = self._description_text.get("1.0", "end").strip()
        if not description:
            raise InvalidRuleConfigError("Bitte eine Erklärung angeben.")

        raw_patterns = [
            line.strip() for line in self._patterns_text.get("1.0", "end").splitlines()
            if line.strip()
        ]
        if not raw_patterns:
            raise InvalidRuleConfigError("Es muss mindestens ein Muster angegeben werden.")

        for pattern in raw_patterns:
            try:
                re.compile(pattern, flags=re.IGNORECASE | re.DOTALL)
            except re.error as exc:
                raise InvalidRuleConfigError(f"Ungültiges Regex-Muster '{pattern}': {exc}") from exc

        return Rule(
            id=rule_id,
            kategorie=category,
            schweregrad=self._severity_var.get(),
            beschreibung=description,
            muster=raw_patterns,
            aktiv=self._active_var.get(),
            typ=_TYPE_LABEL_TO_KEY.get(self._typ_var.get(), "vertragsklausel"),
        )

    def _on_save_clicked(self) -> None:
        try:
            new_rule = self._read_form_as_rule()
        except InvalidRuleConfigError as exc:
            messagebox.showerror("Ungültige Regel", str(exc))
            return

        existing_ids = [r.id for r in self._rules]
        if self._selected_rule_id is not None and self._selected_rule_id != new_rule.id:
            # ID wurde geändert -> alte Regel entfernen
            self._rules = [r for r in self._rules if r.id != self._selected_rule_id]

        if new_rule.id in [r.id for r in self._rules] and (
            self._selected_rule_id is None or self._selected_rule_id != new_rule.id
        ):
            messagebox.showerror("Ungültige Regel", f"Eine Regel mit der ID '{new_rule.id}' existiert bereits.")
            return

        if self._selected_rule_id is not None and self._selected_rule_id in existing_ids:
            self._rules = [new_rule if r.id == self._selected_rule_id else r for r in self._rules]
        else:
            self._rules.append(new_rule)

        self._selected_rule_id = new_rule.id
        self._refresh_rule_list()
        self._has_unsaved_changes = False
        self._save_rules_to_disk()

    def _save_rules_to_disk(self) -> None:
        try:
            data = {
                "rules": [
                    {
                        "id": r.id,
                        "kategorie": r.kategorie,
                        "schweregrad": r.schweregrad,
                        "beschreibung": r.beschreibung,
                        "muster": r.muster,
                        "aktiv": r.aktiv,
                        "typ": r.typ,
                    }
                    for r in self._rules
                ]
            }
            with open(RULES_FILE_PATH, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.info("Regelbibliothek gespeichert (%d Regeln).", len(self._rules))
            self._on_rules_changed(self._rules)
        except OSError as exc:
            messagebox.showerror("Fehler beim Speichern", f"Regelbibliothek konnte nicht gespeichert werden: {exc}")
