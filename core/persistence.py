"""
================================================================================
CAPA DE PERSISTENCIA HIPOTESIS - VEO v2.0.5
================================================================================
Conector ligero entre HermesCommander y SQLite para persistir hipotesis
entre reinicios del proceso.

No reemplaza core/db.py.  Usa aiosqlite directamente con conexiones
gestionadas localmente (sin singleton global), evitando conflictos con
el pool compartido de core/db.

Uso:
    from core.persistence import guardar_hipotesis, obtener_hipotesis, listar_hipotesis
    await guardar_hipotesis({"id": "hyp_001", "texto": "...", ...})
    h = await obtener_hipotesis("hyp_001")
    lista = await listar_hipotesis()
================================================================================
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import aiosqlite

# Ruta por defecto a la base de datos
DEFAULT_DB_PATH = "veo_data.db"


# Esquema SQL minimo para la tabla de hipotesis
_ESQUEMA_HIPOTESIS = """
CREATE TABLE IF NOT EXISTS hipotesis (
    id TEXT PRIMARY KEY,
    texto TEXT NOT NULL,
    confianza REAL NOT NULL DEFAULT 0.0 CHECK (confianza >= 0 AND confianza <= 1),
    evidencias TEXT NOT NULL DEFAULT '[]',
    refutaciones TEXT NOT NULL DEFAULT '[]',
    estado TEXT NOT NULL DEFAULT 'activa' CHECK (estado IN ('activa', 'confirmada', 'refutada', 'caduca')),
    fecha_creacion TEXT NOT NULL,
    fecha_actualizacion TEXT NOT NULL,
    creador TEXT NOT NULL DEFAULT 'sistema',
    tags TEXT NOT NULL DEFAULT '[]',
    peso_nei REAL NOT NULL DEFAULT 0.0
);

CREATE INDEX IF NOT EXISTS idx_hipotesis_estado ON hipotesis(estado);
CREATE INDEX IF NOT EXISTS idx_hipotesis_confianza ON hipotesis(confianza);
"""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _to_json(value: Any) -> str:
    if value is None:
        return "[]"
    if isinstance(value, str):
        try:
            json.loads(value)
            return value
        except json.JSONDecodeError:
            return json.dumps([value])
    if isinstance(value, (list, dict)):
        return json.dumps(value)
    return "[]"


def _from_json(value: str) -> Any:
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return []


async def _ensure_schema(db: aiosqlite.Connection) -> None:
    """Garantiza que el esquema de hipotesis existe."""
    await db.executescript(_ESQUEMA_HIPOTESIS)
    await db.commit()


async def _open_db(db_path: str | None = None) -> aiosqlite.Connection:
    """Abre una conexion a la base de datos y asegura el esquema."""
    path = db_path or DEFAULT_DB_PATH
    if path != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)

    db = await aiosqlite.connect(
        path,
        detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES,
    )
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA foreign_keys = ON")
    await _ensure_schema(db)
    return db


async def guardar_hipotesis(h: Dict[str, Any], db_path: str | None = None) -> None:
    """Inserta o reemplaza una hipotesis en la base de datos."""
    db = await _open_db(db_path)
    try:
        sql = """
            INSERT OR REPLACE INTO hipotesis (
                id, texto, confianza, evidencias, refutaciones, estado,
                fecha_creacion, fecha_actualizacion, creador, tags, peso_nei
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = (
            h.get("id", ""),
            h.get("texto", h.get("text", "")),
            float(h.get("confianza", h.get("confidence", 0.5))),
            _to_json(h.get("evidencias", h.get("evidence", []))),
            _to_json(h.get("refutaciones", h.get("refutations", []))),
            h.get("estado", "activa"),
            h.get("fecha_creacion", _now_iso()),
            _now_iso(),
            h.get("creador", "sistema"),
            _to_json(h.get("tags", [])),
            float(h.get("nei", h.get("peso_nei", 0.5))),
        )
        await db.execute(sql, params)
        await db.commit()
    finally:
        await db.close()


async def actualizar_hipotesis(hid: str, campos: Dict[str, Any], db_path: str | None = None) -> bool:
    """Actualiza campos especificos de una hipotesis existente."""
    db = await _open_db(db_path)
    try:
        mapeo = {
            "texto": "texto",
            "text": "texto",
            "confianza": "confianza",
            "confidence": "confianza",
            "evidencias": "evidencias",
            "evidence": "evidencias",
            "refutaciones": "refutaciones",
            "refutations": "refutaciones",
            "estado": "estado",
            "creador": "creador",
            "tags": "tags",
            "nei": "peso_nei",
            "peso_nei": "peso_nei",
        }

        sets: List[str] = []
        params: List[Any] = []
        for k, v in campos.items():
            col = mapeo.get(k)
            if col is None:
                continue
            if col in ("evidencias", "refutaciones", "tags"):
                v = _to_json(v)
            sets.append(f"{col} = ?")
            params.append(v)

        if not sets:
            return False

        sets.append("fecha_actualizacion = ?")
        params.append(_now_iso())
        params.append(hid)

        sql = f"UPDATE hipotesis SET {', '.join(sets)} WHERE id = ?"
        cursor = await db.execute(sql, params)
        await db.commit()
        return cursor.rowcount > 0
    finally:
        await db.close()


async def obtener_hipotesis(hid: str, db_path: str | None = None) -> Optional[Dict[str, Any]]:
    """Recupera una hipotesis por ID."""
    db = await _open_db(db_path)
    try:
        cursor = await db.execute("SELECT * FROM hipotesis WHERE id = ?", (hid,))
        fila = await cursor.fetchone()
        await cursor.close()

        if fila is None:
            return None

        return {
            "id": fila["id"],
            "texto": fila["texto"],
            "confianza": fila["confianza"],
            "evidencias": _from_json(fila["evidencias"]),
            "refutaciones": _from_json(fila["refutaciones"]),
            "estado": fila["estado"],
            "fecha_creacion": fila["fecha_creacion"],
            "fecha_actualizacion": fila["fecha_actualizacion"],
            "creador": fila["creador"],
            "tags": _from_json(fila["tags"]),
            "nei": fila["peso_nei"],
        }
    finally:
        await db.close()


async def listar_hipotesis(
    estado: str | None = None,
    confianza_min: float | None = None,
    db_path: str | None = None,
) -> List[Dict[str, Any]]:
    """Lista hipotesis con filtros opcionales."""
    db = await _open_db(db_path)
    try:
        where: List[str] = []
        params: List[Any] = []

        if estado:
            where.append("estado = ?")
            params.append(estado)
        if confianza_min is not None:
            where.append("confianza >= ?")
            params.append(confianza_min)

        sql = "SELECT * FROM hipotesis"
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY fecha_creacion DESC"

        cursor = await db.execute(sql, params)
        filas = await cursor.fetchall()
        await cursor.close()

        return [
            {
                "id": r["id"],
                "texto": r["texto"],
                "confianza": r["confianza"],
                "evidencias": _from_json(r["evidencias"]),
                "refutaciones": _from_json(r["refutaciones"]),
                "estado": r["estado"],
                "fecha_creacion": r["fecha_creacion"],
                "fecha_actualizacion": r["fecha_actualizacion"],
                "creador": r["creador"],
                "tags": _from_json(r["tags"]),
                "nei": r["peso_nei"],
            }
            for r in filas
        ]
    finally:
        await db.close()
