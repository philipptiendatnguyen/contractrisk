"""
database/db_manager.py
------------------------
Kapselt den gesamten SQLite-Zugriff für Verträge, Scan-Ergebnisse und
Fristen. Verwendet ausschließlich parametrisierte Queries (`?`-Platzhalter)
- niemals String-Interpolation - als Schutz vor SQL-Injection, auch wenn
die Datenquelle rein lokal ist.
"""

from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime
from typing import Iterator

from contractrisk.config import DATABASE_PATH
from contractrisk.domain.models import Contract, Deadline, RiskFinding
from contractrisk.utils.exceptions import DatabaseError
from contractrisk.utils.logger import get_logger

logger = get_logger(__name__)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS contracts (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    dateiname               TEXT NOT NULL,
    originaltext            TEXT NOT NULL,
    importiert_am           TEXT NOT NULL,
    vertragsbeginn          TEXT,
    risk_score              REAL NOT NULL DEFAULT 0,
    risk_level              TEXT NOT NULL DEFAULT 'niedrig',
    quellformat             TEXT NOT NULL DEFAULT '',
    vertrags_risiko_score   REAL NOT NULL DEFAULT 0,
    betrugs_risiko_score    REAL NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_contracts_risk_score ON contracts (risk_score);

CREATE TABLE IF NOT EXISTS findings (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    contract_id    INTEGER NOT NULL,
    rule_id        TEXT NOT NULL,
    kategorie      TEXT NOT NULL,
    schweregrad    TEXT NOT NULL,
    erklaerung     TEXT NOT NULL,
    fundstelle     TEXT NOT NULL,
    start_index    INTEGER NOT NULL,
    end_index      INTEGER NOT NULL,
    confidence     TEXT NOT NULL DEFAULT 'hoch',
    begruendung    TEXT NOT NULL DEFAULT '',
    typ            TEXT NOT NULL DEFAULT 'vertragsklausel',
    FOREIGN KEY (contract_id) REFERENCES contracts (id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_findings_contract_id ON findings (contract_id);

CREATE TABLE IF NOT EXISTS deadlines (
    id                       INTEGER PRIMARY KEY AUTOINCREMENT,
    contract_id              INTEGER NOT NULL,
    bezeichnung               TEXT NOT NULL,
    datum                     TEXT,
    quelle_text               TEXT NOT NULL,
    konnte_berechnet_werden   INTEGER NOT NULL,
    hinweis                   TEXT,
    FOREIGN KEY (contract_id) REFERENCES contracts (id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_deadlines_contract_id ON deadlines (contract_id);
"""

# Leichtgewichtige Schema-Migration: Spalten, die in einer früheren
# Projektversion noch nicht existierten (z. B. bei einer bereits
# bestehenden lokalen Datenbank älterer Nutzer). `CREATE TABLE IF NOT
# EXISTS` allein würde bei einer bereits vorhandenen, älteren Tabelle
# keine neuen Spalten ergänzen - das übernimmt `_apply_migrations`.
_COLUMN_MIGRATIONS = {
    "contracts": {
        "quellformat": "TEXT NOT NULL DEFAULT ''",
        "vertrags_risiko_score": "REAL NOT NULL DEFAULT 0",
        "betrugs_risiko_score": "REAL NOT NULL DEFAULT 0",
    },
    "findings": {
        "confidence": "TEXT NOT NULL DEFAULT 'hoch'",
        "begruendung": "TEXT NOT NULL DEFAULT ''",
        "typ": "TEXT NOT NULL DEFAULT 'vertragsklausel'",
    },
}


class DatabaseManager:
    """Verwaltet die Verbindung zur SQLite-Datenbank und stellt CRUD-
    Operationen für Verträge, Funde und Fristen bereit."""

    def __init__(self, database_path: str = DATABASE_PATH) -> None:
        self._database_path = database_path
        os.makedirs(os.path.dirname(database_path), exist_ok=True)
        self._initialize_schema()

    def _initialize_schema(self) -> None:
        try:
            with self._connect() as conn:
                conn.executescript(_SCHEMA)
                self._apply_column_migrations(conn)
        except sqlite3.Error as exc:
            raise DatabaseError(f"Datenbankschema konnte nicht initialisiert werden: {exc}") from exc

    @staticmethod
    def _apply_column_migrations(conn: sqlite3.Connection) -> None:
        """Ergänzt fehlende Spalten in bereits existierenden Tabellen
        (z. B. wenn eine ältere Projektversion die Datenbank ursprünglich
        angelegt hat). Idempotent: bereits vorhandene Spalten werden
        übersprungen."""
        for table_name, columns in _COLUMN_MIGRATIONS.items():
            existing_columns = {
                row["name"] for row in conn.execute(f"PRAGMA table_info({table_name})").fetchall()
            }
            for column_name, column_definition in columns.items():
                if column_name not in existing_columns:
                    conn.execute(
                        f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_definition}"
                    )
                    logger.info("Datenbank-Migration: Spalte '%s.%s' ergänzt.", table_name, column_name)

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self._database_path)
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except sqlite3.Error:
            conn.rollback()
            raise
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Verträge
    # ------------------------------------------------------------------

    def save_contract(self, contract: Contract) -> int:
        """Speichert einen Vertrag inkl. aller Funde und Fristen und
        liefert die vergebene Datenbank-ID zurück."""
        try:
            with self._connect() as conn:
                cursor = conn.execute(
                    """
                    INSERT INTO contracts
                        (dateiname, originaltext, importiert_am, vertragsbeginn,
                         risk_score, risk_level, quellformat,
                         vertrags_risiko_score, betrugs_risiko_score)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        contract.dateiname,
                        contract.originaltext,
                        contract.importiert_am.isoformat(),
                        contract.vertragsbeginn.isoformat() if contract.vertragsbeginn else None,
                        contract.risk_score,
                        contract.risk_level,
                        contract.quellformat,
                        contract.vertrags_risiko_score,
                        contract.betrugs_risiko_score,
                    ),
                )
                contract_id = cursor.lastrowid

                for finding in contract.findings:
                    conn.execute(
                        """
                        INSERT INTO findings
                            (contract_id, rule_id, kategorie, schweregrad,
                             erklaerung, fundstelle, start_index, end_index,
                             confidence, begruendung, typ)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            contract_id, finding.rule_id, finding.kategorie,
                            finding.schweregrad, finding.erklaerung,
                            finding.fundstelle_text, finding.start_index, finding.end_index,
                            finding.confidence, finding.begruendung, finding.typ,
                        ),
                    )

                for deadline in contract.deadlines:
                    conn.execute(
                        """
                        INSERT INTO deadlines
                            (contract_id, bezeichnung, datum, quelle_text,
                             konnte_berechnet_werden, hinweis)
                        VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (
                            contract_id, deadline.bezeichnung,
                            deadline.datum.isoformat() if deadline.datum else None,
                            deadline.quelle_text,
                            1 if deadline.konnte_berechnet_werden else 0,
                            deadline.hinweis,
                        ),
                    )

            logger.info("Vertrag gespeichert: id=%s, datei=%s", contract_id, contract.dateiname)
            return contract_id
        except sqlite3.Error as exc:
            raise DatabaseError(f"Vertrag konnte nicht gespeichert werden: {exc}") from exc

    def load_all_contracts(self) -> list[Contract]:
        """Lädt alle gespeicherten Verträge inkl. Funde und Fristen."""
        try:
            with self._connect() as conn:
                contract_rows = conn.execute(
                    "SELECT * FROM contracts ORDER BY importiert_am DESC"
                ).fetchall()

                contracts: list[Contract] = []
                for row in contract_rows:
                    findings = self._load_findings_for_contract(conn, row["id"])
                    deadlines = self._load_deadlines_for_contract(conn, row["id"])
                    contracts.append(self._row_to_contract(row, findings, deadlines))

                return contracts
        except sqlite3.Error as exc:
            raise DatabaseError(f"Verträge konnten nicht geladen werden: {exc}") from exc

    def delete_contract(self, contract_id: int) -> None:
        try:
            with self._connect() as conn:
                conn.execute("DELETE FROM contracts WHERE id = ?", (contract_id,))
            logger.info("Vertrag gelöscht: id=%s", contract_id)
        except sqlite3.Error as exc:
            raise DatabaseError(f"Vertrag konnte nicht gelöscht werden: {exc}") from exc

    # ------------------------------------------------------------------
    # Interne Hilfsfunktionen
    # ------------------------------------------------------------------

    @staticmethod
    def _load_findings_for_contract(conn: sqlite3.Connection, contract_id: int) -> list[RiskFinding]:
        rows = conn.execute(
            "SELECT * FROM findings WHERE contract_id = ? ORDER BY start_index",
            (contract_id,),
        ).fetchall()
        return [
            RiskFinding(
                rule_id=row["rule_id"],
                kategorie=row["kategorie"],
                schweregrad=row["schweregrad"],
                erklaerung=row["erklaerung"],
                fundstelle_text=row["fundstelle"],
                start_index=row["start_index"],
                end_index=row["end_index"],
                confidence=row["confidence"] or "hoch",
                begruendung=row["begruendung"] or "",
                typ=row["typ"] or "vertragsklausel",
            )
            for row in rows
        ]

    @staticmethod
    def _load_deadlines_for_contract(conn: sqlite3.Connection, contract_id: int) -> list[Deadline]:
        rows = conn.execute(
            "SELECT * FROM deadlines WHERE contract_id = ?",
            (contract_id,),
        ).fetchall()
        return [
            Deadline(
                bezeichnung=row["bezeichnung"],
                datum=date.fromisoformat(row["datum"]) if row["datum"] else None,
                quelle_text=row["quelle_text"],
                konnte_berechnet_werden=bool(row["konnte_berechnet_werden"]),
                hinweis=row["hinweis"] or "",
            )
            for row in rows
        ]

    @staticmethod
    def _row_to_contract(row: sqlite3.Row, findings: list[RiskFinding], deadlines: list[Deadline]) -> Contract:
        return Contract(
            id=row["id"],
            dateiname=row["dateiname"],
            originaltext=row["originaltext"],
            importiert_am=datetime.fromisoformat(row["importiert_am"]),
            vertragsbeginn=date.fromisoformat(row["vertragsbeginn"]) if row["vertragsbeginn"] else None,
            quellformat=row["quellformat"] or "",
            risk_score=row["risk_score"],
            risk_level=row["risk_level"],
            vertrags_risiko_score=row["vertrags_risiko_score"] or 0.0,
            betrugs_risiko_score=row["betrugs_risiko_score"] or 0.0,
            findings=findings,
            deadlines=deadlines,
        )
