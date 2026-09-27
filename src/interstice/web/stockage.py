"""Stockage applicatif (SQLite), séparé du corpus juridique.

Chemin : `INTERSTICE_APP_DB`, sinon `<data>/app.sqlite`.
Contient : fournisseurs (clé API en clair, jamais renvoyée par l'API), modèles activés,
réglages, conversations et messages (parts JSON du contrat + trace LLM interne).
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from interstice import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS providers (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    type TEXT NOT NULL,
    base_url TEXT NOT NULL,
    api_key TEXT,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS provider_models (
    provider_id TEXT NOT NULL REFERENCES providers(id) ON DELETE CASCADE,
    model_id TEXT NOT NULL,
    label TEXT,
    thinking TEXT NOT NULL,
    context_length INTEGER,
    position INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (provider_id, model_id)
);
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT
);
CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY,
    title TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS messages (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    id TEXT NOT NULL UNIQUE,
    conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role TEXT NOT NULL,
    parts TEXT NOT NULL,
    created_at TEXT NOT NULL,
    model_key TEXT,
    thinking_level TEXT,
    error TEXT,
    usage TEXT,
    trace TEXT
);
CREATE INDEX IF NOT EXISTS messages_conv ON messages(conversation_id, seq);
"""

# Migrations additives : (version, instructions). Appliquées si PRAGMA user_version < version.
MIGRATIONS: list[tuple[int, str]] = []

TITRE_PAR_DEFAUT = "Nouvelle conversation"
CLES_REGLAGES = ("default_model_key", "default_thinking")


def chemin_app_db() -> Path:
    return Path(os.environ.get("INTERSTICE_APP_DB", config.DATA / "app.sqlite"))


def maintenant() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def nouvel_id() -> str:
    return uuid.uuid4().hex


def cle_modele(provider_id: str, model_id: str) -> str:
    return f"{provider_id}::{model_id}"


def separer_cle(cle: str) -> tuple[str, str]:
    if "::" not in cle:
        raise ValueError(f"clé de modèle invalide : {cle!r} (attendu « fournisseur::modèle »)")
    p, m = cle.split("::", 1)
    return p, m


def titre_depuis(contenu: str, nb_mots: int = 8, max_car: int = 60) -> str:
    mots = contenu.split()
    titre = " ".join(mots[:nb_mots])
    if len(titre) > max_car:
        titre = titre[:max_car].rstrip() + "…"
    elif len(mots) > nb_mots:
        titre += "…"
    return titre or TITRE_PAR_DEFAUT


class Stockage:
    def __init__(self, chemin: Path | str | None = None):
        self.chemin = Path(chemin) if chemin is not None else chemin_app_db()
        if str(self.chemin) != ":memory:":
            self.chemin.parent.mkdir(parents=True, exist_ok=True)
        self._verrou = threading.RLock()
        self.conn = sqlite3.connect(str(self.chemin), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        if str(self.chemin) != ":memory:":
            self.conn.execute("PRAGMA journal_mode = WAL")
        self._migrer()

    def _migrer(self) -> None:
        with self._verrou:
            self.conn.executescript(SCHEMA)
            version = self.conn.execute("PRAGMA user_version").fetchone()[0]
            for v, sql in MIGRATIONS:
                if v > version:
                    self.conn.executescript(sql)
                    self.conn.execute(f"PRAGMA user_version = {int(v)}")
            self.conn.commit()

    def fermer(self) -> None:
        with self._verrou:
            self.conn.close()

    def _exec(self, sql: str, params: tuple | list = ()) -> sqlite3.Cursor:
        with self._verrou:
            cur = self.conn.execute(sql, params)
            self.conn.commit()
            return cur

    def _all(self, sql: str, params: tuple | list = ()) -> list[sqlite3.Row]:
        with self._verrou:
            return self.conn.execute(sql, params).fetchall()

    def _one(self, sql: str, params: tuple | list = ()) -> sqlite3.Row | None:
        with self._verrou:
            return self.conn.execute(sql, params).fetchone()

    # ---- fournisseurs ---------------------------------------------------------------------

    def _modeles_de(self, provider_id: str) -> list[dict[str, Any]]:
        rows = self._all("SELECT * FROM provider_models WHERE provider_id=? ORDER BY position, "
                         "model_id", (provider_id,))
        return [{"id": r["model_id"], "label": r["label"], "thinking": json.loads(r["thinking"]),
                 "context_length": r["context_length"]} for r in rows]

    def _public(self, r: sqlite3.Row) -> dict[str, Any]:
        return {"id": r["id"], "name": r["name"], "type": r["type"], "base_url": r["base_url"],
                "api_key_set": bool(r["api_key"]), "models": self._modeles_de(r["id"])}

    def lister_fournisseurs(self) -> list[dict[str, Any]]:
        return [self._public(r) for r in
                self._all("SELECT * FROM providers ORDER BY created_at, name")]

    def fournisseur(self, provider_id: str) -> dict[str, Any] | None:
        r = self._one("SELECT * FROM providers WHERE id=?", (provider_id,))
        return self._public(r) if r else None

    def fournisseur_prive(self, provider_id: str) -> dict[str, Any] | None:
        """Avec la clé API : usage interne uniquement (jamais renvoyé par l'API)."""
        r = self._one("SELECT * FROM providers WHERE id=?", (provider_id,))
        if not r:
            return None
        d = self._public(r)
        d["api_key"] = r["api_key"] or ""
        return d

    def creer_fournisseur(self, name: str, type: str, base_url: str,
                          api_key: str | None) -> dict[str, Any]:
        pid = nouvel_id()[:12]
        self._exec("INSERT INTO providers(id, name, type, base_url, api_key, created_at) "
                   "VALUES (?,?,?,?,?,?)", (pid, name, type, base_url, api_key or None, maintenant()))
        return self.fournisseur(pid)  # type: ignore[return-value]

    def modifier_fournisseur(self, provider_id: str, **champs: Any) -> dict[str, Any] | None:
        autorises = {k: v for k, v in champs.items() if k in ("name", "base_url", "api_key")}
        if autorises:
            sets = ", ".join(f"{k}=?" for k in autorises)
            self._exec(f"UPDATE providers SET {sets} WHERE id=?",
                       [*autorises.values(), provider_id])
        return self.fournisseur(provider_id)

    def supprimer_fournisseur(self, provider_id: str) -> bool:
        return self._exec("DELETE FROM providers WHERE id=?", (provider_id,)).rowcount > 0

    def definir_modeles(self, provider_id: str, modeles: list[dict[str, Any]]) -> None:
        with self._verrou:
            self.conn.execute("DELETE FROM provider_models WHERE provider_id=?", (provider_id,))
            vus: set[str] = set()
            for i, m in enumerate(modeles):
                if m["id"] in vus:
                    continue
                vus.add(m["id"])
                self.conn.execute(
                    "INSERT INTO provider_models(provider_id, model_id, label, thinking, "
                    "context_length, position) VALUES (?,?,?,?,?,?)",
                    (provider_id, m["id"], m.get("label"), json.dumps(m["thinking"]),
                     m.get("context_length"), i))
            self.conn.commit()

    def modeles_choix(self) -> list[dict[str, Any]]:
        sortie = []
        for f in self.lister_fournisseurs():
            for m in f["models"]:
                sortie.append({"key": cle_modele(f["id"], m["id"]), "provider_id": f["id"],
                               "provider_name": f["name"], "model_id": m["id"],
                               "label": m.get("label") or m["id"], "thinking": m["thinking"]})
        return sortie

    def modele_active(self, provider_id: str, model_id: str) -> dict[str, Any] | None:
        for m in self._modeles_de(provider_id):
            if m["id"] == model_id:
                return m
        return None

    # ---- réglages -------------------------------------------------------------------------

    def lire_reglages(self) -> dict[str, Any]:
        d: dict[str, Any] = {k: None for k in CLES_REGLAGES}
        for r in self._all("SELECT key, value FROM settings"):
            if r["key"] in d:
                d[r["key"]] = json.loads(r["value"]) if r["value"] is not None else None
        return d

    def ecrire_reglages(self, valeurs: dict[str, Any]) -> dict[str, Any]:
        with self._verrou:
            for k in CLES_REGLAGES:
                if k in valeurs:
                    self.conn.execute(
                        "INSERT INTO settings(key, value) VALUES (?, ?) "
                        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                        (k, json.dumps(valeurs[k])))
            self.conn.commit()
        return self.lire_reglages()

    # ---- conversations --------------------------------------------------------------------

    @staticmethod
    def _resume(r: sqlite3.Row) -> dict[str, Any]:
        return {"id": r["id"], "title": r["title"] or TITRE_PAR_DEFAUT,
                "updated_at": r["updated_at"]}

    def lister_conversations(self) -> list[dict[str, Any]]:
        return [self._resume(r) for r in
                self._all("SELECT * FROM conversations ORDER BY updated_at DESC, created_at DESC")]

    def creer_conversation(self, title: str | None = None) -> dict[str, Any]:
        cid = nouvel_id()
        t = maintenant()
        self._exec("INSERT INTO conversations(id, title, created_at, updated_at) "
                   "VALUES (?,?,?,?)", (cid, (title or "").strip() or None, t, t))
        return self.conversation(cid)  # type: ignore[return-value]

    def conversation_brute(self, cid: str) -> sqlite3.Row | None:
        return self._one("SELECT * FROM conversations WHERE id=?", (cid,))

    def conversation(self, cid: str) -> dict[str, Any] | None:
        r = self.conversation_brute(cid)
        if not r:
            return None
        d = self._resume(r)
        d["messages"] = [self._message(m) for m in self._all(
            "SELECT * FROM messages WHERE conversation_id=? ORDER BY seq", (cid,))]
        return d

    def renommer_conversation(self, cid: str, title: str) -> dict[str, Any] | None:
        self._exec("UPDATE conversations SET title=?, updated_at=? WHERE id=?",
                   ((title or "").strip() or None, maintenant(), cid))
        r = self.conversation_brute(cid)
        return self._resume(r) if r else None

    def titrer_si_vide(self, cid: str, contenu: str) -> None:
        self._exec("UPDATE conversations SET title=? WHERE id=? AND (title IS NULL OR title='')",
                   (titre_depuis(contenu), cid))

    def supprimer_conversation(self, cid: str) -> bool:
        return self._exec("DELETE FROM conversations WHERE id=?", (cid,)).rowcount > 0

    def toucher_conversation(self, cid: str) -> None:
        self._exec("UPDATE conversations SET updated_at=? WHERE id=?", (maintenant(), cid))

    # ---- messages -------------------------------------------------------------------------

    @staticmethod
    def _message(r: sqlite3.Row) -> dict[str, Any]:
        return {"id": r["id"], "role": r["role"], "parts": json.loads(r["parts"]),
                "created_at": r["created_at"], "model_key": r["model_key"],
                "thinking_level": r["thinking_level"], "error": r["error"],
                "usage": json.loads(r["usage"]) if r["usage"] else None}

    def ajouter_message(self, cid: str, role: str, parts: list[dict[str, Any]], *,
                        model_key: str | None = None, thinking_level: str | None = None,
                        trace: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        mid = nouvel_id()
        t = maintenant()
        with self._verrou:
            self.conn.execute(
                "INSERT INTO messages(id, conversation_id, role, parts, created_at, model_key, "
                "thinking_level, trace) VALUES (?,?,?,?,?,?,?,?)",
                (mid, cid, role, json.dumps(parts, ensure_ascii=False), t, model_key,
                 thinking_level, json.dumps(trace, ensure_ascii=False) if trace is not None
                 else None))
            self.conn.execute("UPDATE conversations SET updated_at=? WHERE id=?", (t, cid))
            self.conn.commit()
        return self.message(mid)  # type: ignore[return-value]

    def message(self, mid: str) -> dict[str, Any] | None:
        r = self._one("SELECT * FROM messages WHERE id=?", (mid,))
        return self._message(r) if r else None

    def maj_message(self, mid: str, *, parts: list[dict[str, Any]] | None = None,
                    error: str | None = None, usage: dict[str, Any] | None = None,
                    trace: list[dict[str, Any]] | None = None) -> None:
        champs: dict[str, Any] = {}
        if parts is not None:
            champs["parts"] = json.dumps(parts, ensure_ascii=False)
        if error is not None:
            champs["error"] = error
        if usage is not None:
            champs["usage"] = json.dumps(usage)
        if trace is not None:
            champs["trace"] = json.dumps(trace, ensure_ascii=False)
        if champs:
            sets = ", ".join(f"{k}=?" for k in champs)
            self._exec(f"UPDATE messages SET {sets} WHERE id=?", [*champs.values(), mid])

    def historique_llm(self, cid: str, avant_seq_de: str | None = None) -> list[dict[str, Any]]:
        """Historique neutre (voir llm/base.py) reconstruit depuis les traces persistées.

        Les messages sans trace (anciens ou incomplets) sont reconstruits depuis leurs parts.
        """
        rows = self._all("SELECT * FROM messages WHERE conversation_id=? ORDER BY seq", (cid,))
        hist: list[dict[str, Any]] = []
        for r in rows:
            if avant_seq_de is not None and r["id"] == avant_seq_de:
                break
            trace = json.loads(r["trace"]) if r["trace"] else None
            if trace:
                hist.extend(trace)
                continue
            parts = json.loads(r["parts"])
            texte = "".join(p.get("text", "") for p in parts if p.get("type") == "text")
            if r["role"] == "user":
                hist.append({"role": "user", "content": texte})
            elif texte:
                hist.append({"role": "assistant", "content": texte, "tool_calls": [],
                             "brut": None})
        return hist
