# db.py - VEO v2
"""
Capa de persistencia asincrona con SQLite para VEO v2.

Este modulo gestiona todas las operaciones de base de datos usando
aiosqlite para operaciones async sin bloqueo. Implementa el patron
singleton para la conexion y proporciona funciones CRUD para todas
las entidades del sistema.

Extension V2: Se anaden 6 nuevas tablas para Operations:
    - ciclo_ejecuciones: Registro de los 4 ciclos (reasoning, forecast, executive, operations)
    - audit_log: Trazabilidad completa de acciones
    - health_checks: Monitoreo de salud de componentes
    - trust_scores: Puntuaciones de confianza por modulo
    - metricas_sistema: Metricas recopiladas del sistema
    - backups_registro: Registro de backups realizados

NEI = Nucleo de Evaluacion Intuitiva

Ejemplo de uso:
    >>> from veo_v2.core.db import inicializar_db, init_db_v2
    >>> await inicializar_db("sois.db")
    >>> await init_db_v2()  # Crear tablas V2 sin perder datos
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import aiosqlite

# ---------------------------------------------------------------------------
# Importaciones de models V1 (relativas al proyecto)
# ---------------------------------------------------------------------------

try:
    from models import (
        CambioNarrativa,
        Descubrimiento,
        Escenario,
        EstadoHipotesis,
        EstadoPrediccion,
        Hipotesis,
        Prediccion,
        ResultadoValidacion,
        TipoDistribucion,
        TipoNodo,
        VariableEscenario,
        VeredictoValidacion,
    )
except ImportError:
    # Fallback para cuando se ejecuta standalone o models no esta disponible
    CambioNarrativa = Any
    Descubrimiento = Any
    Escenario = Any
    EstadoHipotesis = Any
    EstadoPrediccion = Any
    Hipotesis = Any
    Prediccion = Any
    ResultadoValidacion = Any
    TipoDistribucion = Any
    TipoNodo = Any
    VariableEscenario = Any
    VeredictoValidacion = Any


# ---------------------------------------------------------------------------
# Singleton de conexion
# ---------------------------------------------------------------------------

_ruta_db: str | None = None
_pool: aiosqlite.Connection | None = None


async def obtener_conexion(ruta: str | None = None) -> aiosqlite.Connection:
    """
    Obtiene la conexion unica a la base de datos (singleton).

    Si no existe una conexion activa, crea una nueva. La misma
    conexion se reutiliza en todas las llamadas subsiguientes.

    Args:
        ruta: Ruta al archivo SQLite. Si es None, usa la ruta previa
              o busca la variable de entorno SOIS_DB_PATH.

    Returns:
        Conexion aiosqlite activa.

    Raises:
        RuntimeError: Si no se puede establecer la conexion.
    """
    global _pool, _ruta_db

    if ruta is not None:
        _ruta_db = ruta

    if _ruta_db is None:
        import os

        _ruta_db = os.environ.get("SOIS_DB_PATH", "sois.db")

    if _pool is None:
        try:
            # Crear directorio si no existe
            Path(_ruta_db).parent.mkdir(parents=True, exist_ok=True)

            _pool = await aiosqlite.connect(
                _ruta_db,
                detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES,
            )
            # Permitir acceso a columnas por nombre: fila["id"]
            _pool.row_factory = aiosqlite.Row
            # Activar soporte de foreign keys
            await _pool.execute("PRAGMA foreign_keys = ON")
            # Mejorar performance para escrituras
            await _pool.execute("PRAGMA journal_mode = WAL")
            await _pool.execute("PRAGMA synchronous = NORMAL")

        except sqlite3.Error as exc:
            raise RuntimeError(
                f"No se pudo conectar a la base de datos {_ruta_db}: {exc}"
            ) from exc

    return _pool


async def cerrar_conexion() -> None:
    """
    Cierra la conexion singleton y libera recursos.

    Es buena practica llamar esta funcion al terminar la aplicacion
    o en el shutdown del servidor.
    """
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


def _ahora() -> str:
    """Devuelve el timestamp actual en formato ISO 8601 UTC."""
    return datetime.now(tz=timezone.utc).isoformat()


def _serialize(valor: Any) -> str:
    """Serializa un valor a JSON string para almacenamiento."""
    if isinstance(valor, str):
        return valor
    return json.dumps(valor, ensure_ascii=False, default=str)


def _deserialize(texto: str | None, default: Any = None) -> Any:
    """Deserializa un JSON string almacenado en la base de datos."""
    if texto is None:
        return default
    try:
        return json.loads(texto)
    except (json.JSONDecodeError, TypeError):
        return texto if texto is not None else default


# ---------------------------------------------------------------------------
# Esquema SQL V1 (tablas originales - COMPLETAS)
# ---------------------------------------------------------------------------

_ESQUEMA_SQL_V1: str = """
-- ============================================================
-- TABLAS V1 ORIGINALES (conservadas al 100%)
-- ============================================================

-- Tabla: hipotesis
-- Almacena las afirmaciones evaluables sobre cambios de narrativa.
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

-- Indice para busqueda por estado (consulta frecuente)
CREATE INDEX IF NOT EXISTS idx_hipotesis_estado ON hipotesis(estado);
CREATE INDEX IF NOT EXISTS idx_hipotesis_confianza ON hipotesis(confianza);

-- Tabla: predicciones
-- Mercado interno de predicciones sobre hipotesis.
CREATE TABLE IF NOT EXISTS predicciones (
    id TEXT PRIMARY KEY,
    hipotesis_id TEXT NOT NULL,
    escenario TEXT NOT NULL,
    probabilidad REAL NOT NULL DEFAULT 0.5 CHECK (probabilidad >= 0 AND probabilidad <= 1),
    fecha_prediccion TEXT NOT NULL,
    fecha_resolucion TEXT,
    estado TEXT NOT NULL DEFAULT 'abierta' CHECK (estado IN ('abierta', 'cerrada', 'suspendida')),
    liquidez REAL NOT NULL DEFAULT 1000.0,
    participaciones INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (hipotesis_id) REFERENCES hipotesis(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_predicciones_estado ON predicciones(estado);
CREATE INDEX IF NOT EXISTS idx_predicciones_hipotesis ON predicciones(hipotesis_id);

-- Tabla: escenarios
-- Simulaciones de escenarios hipoteticos.
CREATE TABLE IF NOT EXISTS escenarios (
    id TEXT PRIMARY KEY,
    nombre TEXT NOT NULL,
    descripcion TEXT NOT NULL DEFAULT '',
    variables TEXT NOT NULL DEFAULT '[]',
    resultado_simulado TEXT NOT NULL DEFAULT '{}',
    confianza REAL NOT NULL DEFAULT 0.0 CHECK (confianza >= 0 AND confianza <= 1),
    fecha TEXT NOT NULL
);

-- Tabla: descubrimientos_semanales
-- Reportes semanales de hallazgos del sistema.
CREATE TABLE IF NOT EXISTS descubrimientos_semanales (
    id TEXT PRIMARY KEY,
    semana INTEGER NOT NULL CHECK (semana >= 1 AND semana <= 53),
    fecha_inicio TEXT NOT NULL,
    fecha_fin TEXT NOT NULL,
    hipotesis_nuevas TEXT NOT NULL DEFAULT '[]',
    hipotesis_confirmadas TEXT NOT NULL DEFAULT '[]',
    hipotesis_refutadas TEXT NOT NULL DEFAULT '[]',
    tendencias_detectadas TEXT NOT NULL DEFAULT '[]',
    aprendizajes TEXT NOT NULL DEFAULT '[]',
    confianza_promedio REAL NOT NULL DEFAULT 0.0 CHECK (confianza_promedio >= 0 AND confianza_promedio <= 1),
    nivel_actividad REAL NOT NULL DEFAULT 0.0 CHECK (nivel_actividad >= 0 AND nivel_actividad <= 1)
);

CREATE INDEX IF NOT EXISTS idx_descubrimientos_semana ON descubrimientos_semanales(semana);

-- Tabla: cambios_narrativa
-- Detecciones documentadas de cambios en narrativas.
CREATE TABLE IF NOT EXISTS cambios_narrativa (
    id TEXT PRIMARY KEY,
    tema TEXT NOT NULL,
    direccion_anterior TEXT NOT NULL DEFAULT '',
    direccion_actual TEXT NOT NULL DEFAULT '',
    magnitud_cambio REAL NOT NULL DEFAULT 0.0 CHECK (magnitud_cambio >= 0 AND magnitud_cambio <= 1),
    fecha_detectado TEXT NOT NULL,
    fuentes TEXT NOT NULL DEFAULT '[]',
    confianza REAL NOT NULL DEFAULT 0.0 CHECK (confianza >= 0 AND confianza <= 1)
);

CREATE INDEX IF NOT EXISTS idx_cambios_tema ON cambios_narrativa(tema);
CREATE INDEX IF NOT EXISTS idx_cambios_fecha ON cambios_narrativa(fecha_detectado);

-- Tabla: grafo_nodos
-- Nodos del grafo de conocimiento.
CREATE TABLE IF NOT EXISTS grafo_nodos (
    id TEXT PRIMARY KEY,
    tipo TEXT NOT NULL CHECK (tipo IN ('entidad', 'concepto', 'evento')),
    nombre TEXT NOT NULL,
    propiedades TEXT NOT NULL DEFAULT '{}',
    embedding TEXT NOT NULL DEFAULT '[]',
    peso REAL NOT NULL DEFAULT 1.0 CHECK (peso >= 0 AND peso <= 1)
);

CREATE INDEX IF NOT EXISTS idx_nodos_tipo ON grafo_nodos(tipo);
CREATE INDEX IF NOT EXISTS idx_nodos_nombre ON grafo_nodos(nombre);

-- Tabla: grafo_relaciones
-- Relaciones dirigidas entre nodos del grafo.
CREATE TABLE IF NOT EXISTS grafo_relaciones (
    origen_id TEXT NOT NULL,
    destino_id TEXT NOT NULL,
    tipo TEXT NOT NULL DEFAULT 'relacion',
    peso REAL NOT NULL DEFAULT 0.5 CHECK (peso >= 0 AND peso <= 1),
    evidencias TEXT NOT NULL DEFAULT '[]',
    confianza REAL NOT NULL DEFAULT 0.0 CHECK (confianza >= 0 AND confianza <= 1),
    PRIMARY KEY (origen_id, destino_id, tipo),
    FOREIGN KEY (origen_id) REFERENCES grafo_nodos(id) ON DELETE CASCADE,
    FOREIGN KEY (destino_id) REFERENCES grafo_nodos(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_relaciones_origen ON grafo_relaciones(origen_id);
CREATE INDEX IF NOT EXISTS idx_relaciones_destino ON grafo_relaciones(destino_id);

-- Tabla: validaciones
-- Resultados del agente cientifico de validacion.
CREATE TABLE IF NOT EXISTS validaciones (
    hipotesis_id TEXT PRIMARY KEY,
    veredicto TEXT NOT NULL CHECK (veredicto IN ('confirmada', 'refutada', 'inconclusa')),
    razonamiento TEXT NOT NULL DEFAULT '',
    nivel_confianza REAL NOT NULL DEFAULT 0.0 CHECK (nivel_confianza >= 0 AND nivel_confianza <= 1),
    sesgos_detectados TEXT NOT NULL DEFAULT '[]',
    test_realizados TEXT NOT NULL DEFAULT '[]',
    fecha_validacion TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_validaciones_veredicto ON validaciones(veredicto);

-- Tabla: historial_nei
-- Historico de pesos NEI para aprendizaje automatico.
CREATE TABLE IF NOT EXISTS historial_nei (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    semana INTEGER NOT NULL,
    peso_fr REAL NOT NULL,
    peso_gr REAL NOT NULL,
    peso_dv REAL NOT NULL,
    peso_nv REAL NOT NULL,
    peso_em REAL NOT NULL,
    peso_st REAL NOT NULL,
    precision_sistema REAL NOT NULL DEFAULT 0.0,
    fecha_registro TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_historial_semana ON historial_nei(semana);
"""

# ---------------------------------------------------------------------------
# NUEVO V2: Esquema SQL V2 (tablas nuevas)
# ---------------------------------------------------------------------------

_ESQUEMA_SQL_V2: str = """
-- ============================================================
-- TABLAS V2 NUEVAS (Operations Layer)
-- ============================================================

-- Tabla: ciclo_ejecuciones
-- Registro de los 4 ciclos: reasoning, forecast, executive, operations
CREATE TABLE IF NOT EXISTS ciclo_ejecuciones (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ciclo_type TEXT NOT NULL CHECK (ciclo_type IN ('reasoning', 'forecast', 'executive', 'operations')),
    estado TEXT NOT NULL DEFAULT 'running' CHECK (estado IN ('running', 'completed', 'failed', 'timeout', 'cancelled')),
    params TEXT NOT NULL DEFAULT '{}',
    resultado TEXT,
    resultado_summary TEXT,
    error_msg TEXT,
    started_at TEXT NOT NULL,
    ended_at TEXT,
    duration_ms INTEGER,
    modulo TEXT NOT NULL DEFAULT 'sistema',
    version TEXT NOT NULL DEFAULT '2.0.0'
);

CREATE INDEX IF NOT EXISTS idx_ciclos_type ON ciclo_ejecuciones(ciclo_type);
CREATE INDEX IF NOT EXISTS idx_ciclos_estado ON ciclo_ejecuciones(estado);
CREATE INDEX IF NOT EXISTS idx_ciclos_started ON ciclo_ejecuciones(started_at);
CREATE INDEX IF NOT EXISTS idx_ciclos_modulo ON ciclo_ejecuciones(modulo);

-- Tabla: audit_log
-- Trazabilidad completa: quien hizo que, cuando, por que
CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    modulo TEXT NOT NULL,
    accion TEXT NOT NULL,
    usuario TEXT NOT NULL DEFAULT 'sistema',
    params TEXT,
    resultado TEXT,
    resultado_tipo TEXT,
    duration_ms INTEGER,
    ip_address TEXT,
    session_id TEXT,
    detalles TEXT
);

CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_log(timestamp);
CREATE INDEX IF NOT EXISTS idx_audit_modulo ON audit_log(modulo);
CREATE INDEX IF NOT EXISTS idx_audit_accion ON audit_log(accion);
CREATE INDEX IF NOT EXISTS idx_audit_usuario ON audit_log(usuario);
CREATE INDEX IF NOT EXISTS idx_audit_modulo_accion ON audit_log(modulo, accion);

-- Tabla: health_checks
-- Monitoreo de salud de componentes
CREATE TABLE IF NOT EXISTS health_checks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    componente TEXT NOT NULL,
    estado TEXT NOT NULL CHECK (estado IN ('healthy', 'degraded', 'unhealthy', 'unknown')),
    latencia_ms INTEGER,
    tasa_exito REAL CHECK (tasa_exito >= 0 AND tasa_exito <= 1),
    ultima_ejecucion TEXT,
    errores_recientes INTEGER DEFAULT 0,
    health_score REAL CHECK (health_score >= 0 AND health_score <= 100),
    detalles TEXT,
    mensaje TEXT
);

CREATE INDEX IF NOT EXISTS idx_health_componente ON health_checks(componente);
CREATE INDEX IF NOT EXISTS idx_health_timestamp ON health_checks(timestamp);
CREATE INDEX IF NOT EXISTS idx_health_estado ON health_checks(estado);
CREATE INDEX IF NOT EXISTS idx_health_componente_timestamp ON health_checks(componente, timestamp);

-- Tabla: trust_scores
-- Puntuaciones de confianza por modulo (Trust Layer)
CREATE TABLE IF NOT EXISTS trust_scores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    modulo TEXT NOT NULL UNIQUE,
    score REAL NOT NULL DEFAULT 50.0 CHECK (score >= 0 AND score <= 100),
    score_inicial REAL NOT NULL DEFAULT 50.0,
    ejecuciones_total INTEGER NOT NULL DEFAULT 0,
    ejecuciones_exitosas INTEGER NOT NULL DEFAULT 0,
    ejecuciones_fallidas INTEGER NOT NULL DEFAULT 0,
    fallos_consecutivos INTEGER NOT NULL DEFAULT 0,
    aciertos_consecutivos INTEGER NOT NULL DEFAULT 0,
    precision_acumulada REAL DEFAULT 0.0,
    ultima_actualizacion TEXT NOT NULL,
    historial TEXT NOT NULL DEFAULT '[]'
);

CREATE INDEX IF NOT EXISTS idx_trust_modulo ON trust_scores(modulo);
CREATE INDEX IF NOT EXISTS idx_trust_score ON trust_scores(score);

-- Tabla: metricas_sistema
-- Metricas recopiladas del sistema (Metrics Engine)
CREATE TABLE IF NOT EXISTS metricas_sistema (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    metric_name TEXT NOT NULL,
    metric_value REAL NOT NULL,
    metric_type TEXT NOT NULL DEFAULT 'gauge' CHECK (metric_type IN ('gauge', 'counter', 'histogram', 'summary')),
    tags TEXT,
    ciclo_type TEXT,
    modulo TEXT,
    fuente TEXT DEFAULT 'sistema'
);

CREATE INDEX IF NOT EXISTS idx_metricas_name ON metricas_sistema(metric_name);
CREATE INDEX IF NOT EXISTS idx_metricas_timestamp ON metricas_sistema(timestamp);
CREATE INDEX IF NOT EXISTS idx_metricas_name_ts ON metricas_sistema(metric_name, timestamp);
CREATE INDEX IF NOT EXISTS idx_metricas_modulo ON metricas_sistema(modulo);
CREATE INDEX IF NOT EXISTS idx_metricas_ciclo ON metricas_sistema(ciclo_type);

-- Tabla: backups_registro
-- Registro de backups realizados (Backup Manager)
CREATE TABLE IF NOT EXISTS backups_registro (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    nombre_backup TEXT NOT NULL,
    ruta_backup TEXT NOT NULL,
    tamano_bytes INTEGER,
    tipo TEXT NOT NULL DEFAULT 'auto' CHECK (tipo IN ('auto', 'manual', 'pre_update', 'emergency')),
    estado TEXT NOT NULL DEFAULT 'ok' CHECK (estado IN ('ok', 'corrupto', 'incompleto', 'fallido')),
    tablas_incluidas TEXT,
    duracion_ms INTEGER,
    checksum TEXT,
    restaurado INTEGER DEFAULT 0 CHECK (restaurado IN (0, 1)),
    notas TEXT
);

CREATE INDEX IF NOT EXISTS idx_backups_timestamp ON backups_registro(timestamp);
CREATE INDEX IF NOT EXISTS idx_backups_tipo ON backups_registro(tipo);
CREATE INDEX IF NOT EXISTS idx_backups_estado ON backups_registro(estado);
"""


# ---------------------------------------------------------------------------
# Inicializacion de tablas V1
# ---------------------------------------------------------------------------

async def inicializar_db(ruta: str | None = None) -> None:
    """
    Crea todas las tablas e indices V1 si no existen.

    Es seguro llamar esta funcion multiples veces: si las tablas
    ya existen, SQLite las ignora silenciosamente.

    Args:
        ruta: Ruta al archivo SQLite. None usa la ruta por defecto.

    Raises:
        RuntimeError: Si hay un error ejecutando el esquema SQL.
    """
    db = await obtener_conexion(ruta)
    try:
        await db.executescript(_ESQUEMA_SQL_V1)
        await db.commit()
    except sqlite3.Error as exc:
        raise RuntimeError(f"Error al inicializar la base de datos V1: {exc}") from exc


# ---------------------------------------------------------------------------
# NUEVO V2: Inicializacion de tablas V2
# ---------------------------------------------------------------------------

async def init_db_v2(ruta: str | None = None) -> None:
    """
    Crea todas las tablas nuevas de V2 sin perder datos existentes.

    Esta funcion es segura para ejecutar sobre una base de datos V1
    existente: solo crea tablas que no existen, nunca modifica las
    tablas V1 existentes.

    Flujo recomendado para migracion V1 -> V2:
        >>> await inicializar_db("sois.db")   # Tablas V1
        >>> await init_db_v2("sois.db")       # Tablas V2

    Args:
        ruta: Ruta al archivo SQLite. None usa la ruta por defecto.

    Raises:
        RuntimeError: Si hay un error ejecutando el esquema SQL V2.
    """
    db = await obtener_conexion(ruta)
    try:
        await db.executescript(_ESQUEMA_SQL_V2)
        await db.commit()
    except sqlite3.Error as exc:
        raise RuntimeError(f"Error al inicializar la base de datos V2: {exc}") from exc


async def inicializar_db_completa(ruta: str | None = None) -> None:
    """
    Inicializa la base de datos completa (V1 + V2) en una sola llamada.

    Args:
        ruta: Ruta al archivo SQLite. None usa la ruta por defecto.
    """
    await inicializar_db(ruta)
    await init_db_v2(ruta)


# ---------------------------------------------------------------------------
# CRUD: hipotesis (V1 - completo)
# ---------------------------------------------------------------------------

async def crear_hipotesis(hipotesis: Hipotesis) -> Hipotesis:
    """
    Inserta una nueva hipotesis en la base de datos.

    Args:
        hipotesis: Objeto Hipotesis a persistir.

    Returns:
        La misma hipotesis (con posible ID asignado).

    Raises:
        ValueError: Si ya existe una hipotesis con el mismo ID.
        RuntimeError: Si hay un error de base de datos.
    """
    db = await obtener_conexion()
    sql = """
        INSERT INTO hipotesis (
            id, texto, confianza, evidencias, refutaciones, estado,
            fecha_creacion, fecha_actualizacion, creador, tags, peso_nei
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    params = (
        hipotesis.id,
        hipotesis.texto,
        hipotesis.confianza,
        _serialize(hipotesis.evidencias),
        _serialize(hipotesis.refutaciones),
        hipotesis.estado.value if hasattr(hipotesis.estado, "value") else str(hipotesis.estado),
        hipotesis.fecha_creacion.isoformat() if hasattr(hipotesis.fecha_creacion, "isoformat") else str(hipotesis.fecha_creacion),
        hipotesis.fecha_actualizacion.isoformat() if hasattr(hipotesis.fecha_actualizacion, "isoformat") else str(hipotesis.fecha_actualizacion),
        hipotesis.creador,
        _serialize(hipotesis.tags),
        hipotesis.peso_nei,
    )
    try:
        await db.execute(sql, params)
        await db.commit()
    except sqlite3.IntegrityError as exc:
        raise ValueError(f"Hipotesis con ID '{hipotesis.id}' ya existe") from exc
    except sqlite3.Error as exc:
        raise RuntimeError(f"Error al crear hipotesis: {exc}") from exc
    return hipotesis


async def obtener_hipotesis(hipotesis_id: str) -> Hipotesis | None:
    """
    Recupera una hipotesis por su ID.

    Args:
        hipotesis_id: Identificador unico de la hipotesis.

    Returns:
        La hipotesis si existe, None en caso contrario.
    """
    db = await obtener_conexion()
    cursor = await db.execute("SELECT * FROM hipotesis WHERE id = ?", (hipotesis_id,))
    fila = await cursor.fetchone()
    await cursor.close()
    if fila is None:
        return None
    return _fila_a_hipotesis(fila)


async def listar_hipotesis(
    estado: Any = None,
    tag: str | None = None,
    limite: int = 100,
    offset: int = 0,
) -> list[Hipotesis]:
    """
    Lista hipotesis con filtros opcionales.

    Args:
        estado: Filtrar por estado especifico.
        tag: Filtrar por etiqueta (busqueda parcial en JSON array).
        limite: Maximo de resultados.
        offset: Desplazamiento para paginacion.

    Returns:
        Lista de hipotesis que cumplen los filtros.
    """
    db = await obtener_conexion()
    condiciones: list[str] = []
    params: list[Any] = []

    if estado is not None:
        condiciones.append("estado = ?")
        estado_val = estado.value if hasattr(estado, "value") else str(estado)
        params.append(estado_val)

    sql = "SELECT * FROM hipotesis"
    if condiciones:
        sql += " WHERE " + " AND ".join(condiciones)
    sql += " ORDER BY fecha_actualizacion DESC LIMIT ? OFFSET ?"
    params.extend([limite, offset])

    cursor = await db.execute(sql, params)
    filas = await cursor.fetchall()
    await cursor.close()

    hipotesis_list = [_fila_a_hipotesis(f) for f in filas]

    if tag:
        hipotesis_list = [
            h for h in hipotesis_list
            if tag.lower() in [t.lower() for t in (h.tags if hasattr(h, "tags") else [])]
        ]

    return hipotesis_list


async def actualizar_hipotesis(hipotesis_id: str, **kwargs: Any) -> None:
    """
    Actualiza campos especificos de una hipotesis.

    Args:
        hipotesis_id: ID de la hipotesis a modificar.
        **kwargs: Campos a actualizar (texto, confianza, estado, etc.).

    Raises:
        ValueError: Si la hipotesis no existe.
    """
    db = await obtener_conexion()

    campos_permitidos = {
        "texto", "confianza", "evidencias", "refutaciones", "estado",
        "creador", "tags", "peso_nei",
    }
    actualizaciones = {k: v for k, v in kwargs.items() if k in campos_permitidos}
    if not actualizaciones:
        return

    if "evidencias" in actualizaciones:
        actualizaciones["evidencias"] = _serialize(actualizaciones["evidencias"])
    if "refutaciones" in actualizaciones:
        actualizaciones["refutaciones"] = _serialize(actualizaciones["refutaciones"])
    if "tags" in actualizaciones:
        actualizaciones["tags"] = _serialize(actualizaciones["tags"])

    actualizaciones["fecha_actualizacion"] = _ahora()

    set_clause = ", ".join(f"{k} = ?" for k in actualizaciones)
    valores = list(actualizaciones.values()) + [hipotesis_id]

    sql = f"UPDATE hipotesis SET {set_clause} WHERE id = ?"
    cursor = await db.execute(sql, valores)
    if cursor.rowcount == 0:
        raise ValueError(f"Hipotesis '{hipotesis_id}' no encontrada")
    await db.commit()


async def eliminar_hipotesis(hipotesis_id: str) -> None:
    """
    Elimina una hipotesis por su ID.

    Args:
        hipotesis_id: ID de la hipotesis a eliminar.
    """
    db = await obtener_conexion()
    await db.execute("DELETE FROM hipotesis WHERE id = ?", (hipotesis_id,))
    await db.commit()


def _fila_a_hipotesis(fila: aiosqlite.Row) -> Hipotesis:
    """Convierte una fila de la base de datos a objeto Hipotesis."""
    fc = fila["fecha_creacion"]
    fa = fila["fecha_actualizacion"]
    estado_val = fila["estado"]

    try:
        from models import EstadoHipotesis
        estado = EstadoHipotesis(estado_val)
    except (ImportError, ValueError):
        estado = estado_val

    fecha_creacion = datetime.fromisoformat(fc) if isinstance(fc, str) else fc
    fecha_actualizacion = datetime.fromisoformat(fa) if isinstance(fa, str) else fa

    try:
        return Hipotesis(
            id=fila["id"],
            texto=fila["texto"],
            confianza=fila["confianza"],
            evidencias=_deserialize(fila["evidencias"], []),
            refutaciones=_deserialize(fila["refutaciones"], []),
            estado=estado,
            fecha_creacion=fecha_creacion,
            fecha_actualizacion=fecha_actualizacion,
            creador=fila["creador"],
            tags=_deserialize(fila["tags"], []),
            peso_nei=fila["peso_nei"],
        )
    except TypeError:
        # Fallback si Hipotesis no es el dataclass esperado
        return fila  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# CRUD: predicciones (V1 - completo)
# ---------------------------------------------------------------------------

async def crear_prediccion(prediccion: Prediccion) -> Prediccion:
    """Inserta una nueva prediccion en la base de datos."""
    db = await obtener_conexion()
    sql = """
        INSERT INTO predicciones (
            id, hipotesis_id, escenario, probabilidad, fecha_prediccion,
            fecha_resolucion, estado, liquidez, participaciones
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    estado_val = prediccion.estado.value if hasattr(prediccion.estado, "value") else str(prediccion.estado)
    params = (
        prediccion.id,
        prediccion.hipotesis_id,
        prediccion.escenario,
        prediccion.probabilidad,
        prediccion.fecha_prediccion.isoformat() if hasattr(prediccion.fecha_prediccion, "isoformat") else str(prediccion.fecha_prediccion),
        prediccion.fecha_resolucion.isoformat() if (prediccion.fecha_resolucion and hasattr(prediccion.fecha_resolucion, "isoformat")) else None,
        estado_val,
        prediccion.liquidez,
        prediccion.participaciones,
    )
    try:
        await db.execute(sql, params)
        await db.commit()
    except sqlite3.IntegrityError as exc:
        raise ValueError(f"Prediccion con ID '{prediccion.id}' ya existe") from exc
    except sqlite3.Error as exc:
        raise RuntimeError(f"Error al crear prediccion: {exc}") from exc
    return prediccion


async def obtener_prediccion(prediccion_id: str) -> Prediccion | None:
    """Recupera una prediccion por su ID."""
    db = await obtener_conexion()
    cursor = await db.execute("SELECT * FROM predicciones WHERE id = ?", (prediccion_id,))
    fila = await cursor.fetchone()
    await cursor.close()
    if fila is None:
        return None
    return _fila_a_prediccion(fila)


async def listar_predicciones(
    estado: Any = None,
    hipotesis_id: str | None = None,
    limite: int = 100,
    offset: int = 0,
) -> list[Prediccion]:
    """
    Lista predicciones con filtros opcionales.

    Args:
        estado: Filtrar por estado (abierta/cerrada/suspendida).
        hipotesis_id: Filtrar por hipotesis asociada.
        limite: Maximo de resultados.
        offset: Desplazamiento para paginacion.

    Returns:
        Lista de predicciones que cumplen los filtros.
    """
    db = await obtener_conexion()
    condiciones: list[str] = []
    params: list[Any] = []

    if estado is not None:
        condiciones.append("estado = ?")
        params.append(estado.value if hasattr(estado, "value") else str(estado))
    if hipotesis_id is not None:
        condiciones.append("hipotesis_id = ?")
        params.append(hipotesis_id)

    sql = "SELECT * FROM predicciones"
    if condiciones:
        sql += " WHERE " + " AND ".join(condiciones)
    sql += " ORDER BY fecha_prediccion DESC LIMIT ? OFFSET ?"
    params.extend([limite, offset])

    cursor = await db.execute(sql, params)
    filas = await cursor.fetchall()
    await cursor.close()
    return [_fila_a_prediccion(f) for f in filas]


async def actualizar_prediccion(prediccion_id: str, **kwargs: Any) -> None:
    """Actualiza campos especificos de una prediccion."""
    db = await obtener_conexion()
    campos_permitidos = {"escenario", "probabilidad", "estado", "liquidez", "participaciones"}
    actualizaciones = {k: v for k, v in kwargs.items() if k in campos_permitidos}
    if not actualizaciones:
        return

    set_clause = ", ".join(f"{k} = ?" for k in actualizaciones)
    valores = list(actualizaciones.values()) + [prediccion_id]

    sql = f"UPDATE predicciones SET {set_clause} WHERE id = ?"
    cursor = await db.execute(sql, valores)
    if cursor.rowcount == 0:
        raise ValueError(f"Prediccion '{prediccion_id}' no encontrada")
    await db.commit()


async def eliminar_prediccion(prediccion_id: str) -> None:
    """Elimina una prediccion por su ID."""
    db = await obtener_conexion()
    await db.execute("DELETE FROM predicciones WHERE id = ?", (prediccion_id,))
    await db.commit()


def _fila_a_prediccion(fila: aiosqlite.Row) -> Prediccion:
    """Convierte una fila de la BD a objeto Prediccion."""
    try:
        from models import EstadoPrediccion
        estado = EstadoPrediccion(fila["estado"])
    except (ImportError, ValueError):
        estado = fila["estado"]

    fecha_res = fila["fecha_resolucion"]
    try:
        return Prediccion(
            id=fila["id"],
            hipotesis_id=fila["hipotesis_id"],
            escenario=fila["escenario"],
            probabilidad=fila["probabilidad"],
            fecha_prediccion=datetime.fromisoformat(fila["fecha_prediccion"]),
            fecha_resolucion=datetime.fromisoformat(fecha_res) if fecha_res else None,
            estado=estado,
            liquidez=fila["liquidez"],
            participaciones=fila["participaciones"],
        )
    except TypeError:
        return fila  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# CRUD: escenarios (V1 - completo)
# ---------------------------------------------------------------------------

async def crear_escenario(escenario: Escenario) -> Escenario:
    """Inserta un nuevo escenario en la base de datos."""
    db = await obtener_conexion()
    sql = """
        INSERT INTO escenarios (id, nombre, descripcion, variables, resultado_simulado, confianza, fecha)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """
    vars_serializadas = []
    if hasattr(escenario, "variables") and escenario.variables:
        for v in escenario.variables:
            if hasattr(v, "a_dict"):
                vars_serializadas.append(v.a_dict())
            elif hasattr(v, "__dict__"):
                vars_serializadas.append(v.__dict__)
            else:
                vars_serializadas.append(v)

    params = (
        escenario.id,
        escenario.nombre,
        escenario.descripcion,
        _serialize(vars_serializadas),
        _serialize(escenario.resultado_simulado if hasattr(escenario, "resultado_simulado") else {}),
        escenario.confianza,
        escenario.fecha.isoformat() if hasattr(escenario.fecha, "isoformat") else str(escenario.fecha),
    )
    try:
        await db.execute(sql, params)
        await db.commit()
    except sqlite3.IntegrityError as exc:
        raise ValueError(f"Escenario con ID '{escenario.id}' ya existe") from exc
    except sqlite3.Error as exc:
        raise RuntimeError(f"Error al crear escenario: {exc}") from exc
    return escenario


async def obtener_escenario(escenario_id: str) -> Escenario | None:
    """Recupera un escenario por su ID."""
    db = await obtener_conexion()
    cursor = await db.execute("SELECT * FROM escenarios WHERE id = ?", (escenario_id,))
    fila = await cursor.fetchone()
    await cursor.close()
    if fila is None:
        return None
    return _fila_a_escenario(fila)


async def listar_escenarios(limite: int = 100, offset: int = 0) -> list[Escenario]:
    """Lista todos los escenarios ordenados por fecha descendente."""
    db = await obtener_conexion()
    cursor = await db.execute(
        "SELECT * FROM escenarios ORDER BY fecha DESC LIMIT ? OFFSET ?",
        (limite, offset),
    )
    filas = await cursor.fetchall()
    await cursor.close()
    return [_fila_a_escenario(f) for f in filas]


async def eliminar_escenario(escenario_id: str) -> None:
    """Elimina un escenario por su ID."""
    db = await obtener_conexion()
    await db.execute("DELETE FROM escenarios WHERE id = ?", (escenario_id,))
    await db.commit()


def _fila_a_escenario(fila: aiosqlite.Row) -> Escenario:
    """Convierte una fila de la BD a objeto Escenario."""
    variables_raw = _deserialize(fila["variables"], [])
    variables = []
    for v in variables_raw:
        if isinstance(v, dict):
            try:
                from models import VariableEscenario, TipoDistribucion
                variables.append(
                    VariableEscenario(
                        nombre=v.get("nombre", ""),
                        valor_base=v.get("valor_base", 0.0),
                        rango_min=v.get("rango_min", 0.0),
                        rango_max=v.get("rango_max", 1.0),
                        distribucion=TipoDistribucion(v.get("distribucion", "uniform")),
                    )
                )
            except ImportError:
                variables.append(v)
    try:
        return Escenario(
            id=fila["id"],
            nombre=fila["nombre"],
            descripcion=fila["descripcion"],
            variables=variables,
            resultado_simulado=_deserialize(fila["resultado_simulado"], {}),
            confianza=fila["confianza"],
            fecha=datetime.fromisoformat(fila["fecha"]),
        )
    except TypeError:
        return fila  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# CRUD: descubrimientos_semanales (V1 - completo)
# ---------------------------------------------------------------------------

async def crear_descubrimiento(descubrimiento: Descubrimiento) -> Descubrimiento:
    """Inserta un nuevo descubrimiento semanal."""
    db = await obtener_conexion()
    sql = """
        INSERT INTO descubrimientos_semanales (
            id, semana, fecha_inicio, fecha_fin, hipotesis_nuevas,
            hipotesis_confirmadas, hipotesis_refutadas, tendencias_detectadas,
            aprendizajes, confianza_promedio, nivel_actividad
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    params = (
        descubrimiento.id,
        descubrimiento.semana,
        descubrimiento.fecha_inicio.isoformat() if hasattr(descubrimiento.fecha_inicio, "isoformat") else str(descubrimiento.fecha_inicio),
        descubrimiento.fecha_fin.isoformat() if hasattr(descubrimiento.fecha_fin, "isoformat") else str(descubrimiento.fecha_fin),
        _serialize(descubrimiento.hipotesis_nuevas),
        _serialize(descubrimiento.hipotesis_confirmadas),
        _serialize(descubrimiento.hipotesis_refutadas),
        _serialize(descubrimiento.tendencias_detectadas),
        _serialize(descubrimiento.aprendizajes),
        descubrimiento.confianza_promedio,
        descubrimiento.nivel_actividad,
    )
    try:
        await db.execute(sql, params)
        await db.commit()
    except sqlite3.Error as exc:
        raise RuntimeError(f"Error al crear descubrimiento: {exc}") from exc
    return descubrimiento


async def obtener_descubrimiento(descubrimiento_id: str) -> Descubrimiento | None:
    """Recupera un descubrimiento por su ID."""
    db = await obtener_conexion()
    cursor = await db.execute(
        "SELECT * FROM descubrimientos_semanales WHERE id = ?", (descubrimiento_id,)
    )
    fila = await cursor.fetchone()
    await cursor.close()
    if fila is None:
        return None
    return _fila_a_descubrimiento(fila)


async def listar_descubrimientos(
    semana: int | None = None,
    limite: int = 100,
    offset: int = 0,
) -> list[Descubrimiento]:
    """
    Lista descubrimientos con filtro opcional por semana.

    Args:
        semana: Numero de semana para filtrar.
        limite: Maximo de resultados.
        offset: Desplazamiento para paginacion.
    """
    db = await obtener_conexion()
    if semana is not None:
        cursor = await db.execute(
            "SELECT * FROM descubrimientos_semanales WHERE semana = ? ORDER BY fecha_fin DESC LIMIT ? OFFSET ?",
            (semana, limite, offset),
        )
    else:
        cursor = await db.execute(
            "SELECT * FROM descubrimientos_semanales ORDER BY fecha_fin DESC LIMIT ? OFFSET ?",
            (limite, offset),
        )
    filas = await cursor.fetchall()
    await cursor.close()
    return [_fila_a_descubrimiento(f) for f in filas]


def _fila_a_descubrimiento(fila: aiosqlite.Row) -> Descubrimiento:
    """Convierte una fila de la BD a objeto Descubrimiento."""
    try:
        return Descubrimiento(
            id=fila["id"],
            semana=fila["semana"],
            fecha_inicio=datetime.fromisoformat(fila["fecha_inicio"]),
            fecha_fin=datetime.fromisoformat(fila["fecha_fin"]),
            hipotesis_nuevas=_deserialize(fila["hipotesis_nuevas"], []),
            hipotesis_confirmadas=_deserialize(fila["hipotesis_confirmadas"], []),
            hipotesis_refutadas=_deserialize(fila["hipotesis_refutadas"], []),
            tendencias_detectadas=_deserialize(fila["tendencias_detectadas"], []),
            aprendizajes=_deserialize(fila["aprendizajes"], []),
            confianza_promedio=fila["confianza_promedio"],
            nivel_actividad=fila["nivel_actividad"],
        )
    except TypeError:
        return fila  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# CRUD: cambios_narrativa (V1 - completo)
# ---------------------------------------------------------------------------

async def crear_cambio_narrativa(cambio: CambioNarrativa) -> CambioNarrativa:
    """Inserta un nuevo cambio de narrativa detectado."""
    db = await obtener_conexion()
    sql = """
        INSERT INTO cambios_narrativa (
            id, tema, direccion_anterior, direccion_actual, magnitud_cambio,
            fecha_detectado, fuentes, confianza
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """
    params = (
        cambio.id,
        cambio.tema,
        cambio.direccion_anterior,
        cambio.direccion_actual,
        cambio.magnitud_cambio,
        cambio.fecha_detectado.isoformat() if hasattr(cambio.fecha_detectado, "isoformat") else str(cambio.fecha_detectado),
        _serialize(cambio.fuentes),
        cambio.confianza,
    )
    try:
        await db.execute(sql, params)
        await db.commit()
    except sqlite3.Error as exc:
        raise RuntimeError(f"Error al crear cambio de narrativa: {exc}") from exc
    return cambio


async def obtener_cambio_narrativa(cambio_id: str) -> CambioNarrativa | None:
    """Recupera un cambio de narrativa por su ID."""
    db = await obtener_conexion()
    cursor = await db.execute(
        "SELECT * FROM cambios_narrativa WHERE id = ?", (cambio_id,)
    )
    fila = await cursor.fetchone()
    await cursor.close()
    if fila is None:
        return None
    return _fila_a_cambio_narrativa(fila)


async def listar_cambios_narrativa(
    tema: str | None = None,
    limite: int = 100,
    offset: int = 0,
) -> list[CambioNarrativa]:
    """
    Lista cambios de narrativa con filtro opcional por tema.

    Args:
        tema: Filtrar por tema (busqueda exacta, case-insensitive).
        limite: Maximo de resultados.
        offset: Desplazamiento para paginacion.
    """
    db = await obtener_conexion()
    if tema:
        cursor = await db.execute(
            "SELECT * FROM cambios_narrativa WHERE LOWER(tema) = LOWER(?) ORDER BY fecha_detectado DESC LIMIT ? OFFSET ?",
            (tema, limite, offset),
        )
    else:
        cursor = await db.execute(
            "SELECT * FROM cambios_narrativa ORDER BY fecha_detectado DESC LIMIT ? OFFSET ?",
            (limite, offset),
        )
    filas = await cursor.fetchall()
    await cursor.close()
    return [_fila_a_cambio_narrativa(f) for f in filas]


def _fila_a_cambio_narrativa(fila: aiosqlite.Row) -> CambioNarrativa:
    """Convierte una fila de la BD a objeto CambioNarrativa."""
    try:
        return CambioNarrativa(
            id=fila["id"],
            tema=fila["tema"],
            direccion_anterior=fila["direccion_anterior"],
            direccion_actual=fila["direccion_actual"],
            magnitud_cambio=fila["magnitud_cambio"],
            fecha_detectado=datetime.fromisoformat(fila["fecha_detectado"]),
            fuentes=_deserialize(fila["fuentes"], []),
            confianza=fila["confianza"],
        )
    except TypeError:
        return fila  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# CRUD: grafo_nodos (V1 - completo)
# ---------------------------------------------------------------------------

async def crear_nodo(nodo: Any) -> Any:
    """Inserta un nuevo nodo en el grafo de conocimiento."""
    db = await obtener_conexion()
    sql = """
        INSERT INTO grafo_nodos (id, tipo, nombre, propiedades, embedding, peso)
        VALUES (?, ?, ?, ?, ?, ?)
    """
    tipo_val = nodo.tipo.value if hasattr(nodo.tipo, "value") else str(nodo.tipo)
    params = (
        nodo.id,
        tipo_val,
        nodo.nombre,
        _serialize(nodo.propiedades if hasattr(nodo, "propiedades") else {}),
        _serialize(nodo.embedding if hasattr(nodo, "embedding") else []),
        nodo.peso,
    )
    try:
        await db.execute(sql, params)
        await db.commit()
    except sqlite3.IntegrityError as exc:
        raise ValueError(f"Nodo con ID '{nodo.id}' ya existe") from exc
    except sqlite3.Error as exc:
        raise RuntimeError(f"Error al crear nodo: {exc}") from exc
    return nodo


async def obtener_nodo(nodo_id: str) -> Any | None:
    """Recupera un nodo por su ID."""
    db = await obtener_conexion()
    cursor = await db.execute("SELECT * FROM grafo_nodos WHERE id = ?", (nodo_id,))
    fila = await cursor.fetchone()
    await cursor.close()
    if fila is None:
        return None
    return _fila_a_nodo(fila)


async def listar_nodos(
    tipo: Any = None,
    limite: int = 100,
    offset: int = 0,
) -> list[Any]:
    """
    Lista nodos del grafo con filtro opcional por tipo.

    Args:
        tipo: Filtrar por tipo de nodo (entidad/concepto/evento).
        limite: Maximo de resultados.
        offset: Desplazamiento para paginacion.
    """
    db = await obtener_conexion()
    tipo_val = tipo.value if hasattr(tipo, "value") else str(tipo) if tipo else None
    if tipo_val:
        cursor = await db.execute(
            "SELECT * FROM grafo_nodos WHERE tipo = ? ORDER BY peso DESC LIMIT ? OFFSET ?",
            (tipo_val, limite, offset),
        )
    else:
        cursor = await db.execute(
            "SELECT * FROM grafo_nodos ORDER BY peso DESC LIMIT ? OFFSET ?",
            (limite, offset),
        )
    filas = await cursor.fetchall()
    await cursor.close()
    return [_fila_a_nodo(f) for f in filas]


async def eliminar_nodo(nodo_id: str) -> None:
    """
    Elimina un nodo y sus relaciones asociadas (CASCADE).

    Args:
        nodo_id: ID del nodo a eliminar.
    """
    db = await obtener_conexion()
    await db.execute("DELETE FROM grafo_nodos WHERE id = ?", (nodo_id,))
    await db.commit()


def _fila_a_nodo(fila: aiosqlite.Row) -> Any:
    """Convierte una fila de la BD a objeto NodoGrafo."""
    try:
        from models import NodoGrafo, TipoNodo
        return NodoGrafo(
            id=fila["id"],
            tipo=TipoNodo(fila["tipo"]),
            nombre=fila["nombre"],
            propiedades=_deserialize(fila["propiedades"], {}),
            embedding=_deserialize(fila["embedding"], []),
            peso=fila["peso"],
        )
    except ImportError:
        return {
            "id": fila["id"],
            "tipo": fila["tipo"],
            "nombre": fila["nombre"],
            "propiedades": _deserialize(fila["propiedades"], {}),
            "embedding": _deserialize(fila["embedding"], []),
            "peso": fila["peso"],
        }


# ---------------------------------------------------------------------------
# CRUD: grafo_relaciones (V1 - completo)
# ---------------------------------------------------------------------------

async def crear_relacion(relacion: Any) -> Any:
    """Inserta una nueva relacion entre nodos del grafo."""
    db = await obtener_conexion()
    sql = """
        INSERT INTO grafo_relaciones (origen_id, destino_id, tipo, peso, evidencias, confianza)
        VALUES (?, ?, ?, ?, ?, ?)
    """
    params = (
        relacion.origen_id,
        relacion.destino_id,
        relacion.tipo,
        relacion.peso,
        _serialize(relacion.evidencias if hasattr(relacion, "evidencias") else []),
        relacion.confianza,
    )
    try:
        await db.execute(sql, params)
        await db.commit()
    except sqlite3.IntegrityError as exc:
        raise ValueError(
            f"Relacion ({relacion.origen_id} -> {relacion.destino_id}, tipo={relacion.tipo}) ya existe"
        ) from exc
    except sqlite3.Error as exc:
        raise RuntimeError(f"Error al crear relacion: {exc}") from exc
    return relacion


async def obtener_relacion(
    origen_id: str, destino_id: str, tipo: str
) -> Any | None:
    """Recupera una relacion especifica por su clave compuesta."""
    db = await obtener_conexion()
    cursor = await db.execute(
        "SELECT * FROM grafo_relaciones WHERE origen_id = ? AND destino_id = ? AND tipo = ?",
        (origen_id, destino_id, tipo),
    )
    fila = await cursor.fetchone()
    await cursor.close()
    if fila is None:
        return None
    return _fila_a_relacion(fila)


async def listar_relaciones(
    nodo_id: str | None = None,
    limite: int = 100,
    offset: int = 0,
) -> list[Any]:
    """
    Lista relaciones del grafo.

    Args:
        nodo_id: Si se proporciona, lista relaciones donde el nodo
                 es origen O destino.
        limite: Maximo de resultados.
        offset: Desplazamiento para paginacion.
    """
    db = await obtener_conexion()
    if nodo_id:
        cursor = await db.execute(
            """
            SELECT * FROM grafo_relaciones
            WHERE origen_id = ? OR destino_id = ?
            ORDER BY peso DESC LIMIT ? OFFSET ?
            """,
            (nodo_id, nodo_id, limite, offset),
        )
    else:
        cursor = await db.execute(
            "SELECT * FROM grafo_relaciones ORDER BY peso DESC LIMIT ? OFFSET ?",
            (limite, offset),
        )
    filas = await cursor.fetchall()
    await cursor.close()
    return [_fila_a_relacion(f) for f in filas]


def _fila_a_relacion(fila: aiosqlite.Row) -> Any:
    """Convierte una fila de la BD a objeto RelacionGrafo."""
    try:
        from models import RelacionGrafo
        return RelacionGrafo(
            origen_id=fila["origen_id"],
            destino_id=fila["destino_id"],
            tipo=fila["tipo"],
            peso=fila["peso"],
            evidencias=_deserialize(fila["evidencias"], []),
            confianza=fila["confianza"],
        )
    except ImportError:
        return {
            "origen_id": fila["origen_id"],
            "destino_id": fila["destino_id"],
            "tipo": fila["tipo"],
            "peso": fila["peso"],
            "evidencias": _deserialize(fila["evidencias"], []),
            "confianza": fila["confianza"],
        }


# ---------------------------------------------------------------------------
# CRUD: validaciones (V1 - completo)
# ---------------------------------------------------------------------------

async def crear_validacion(validacion: ResultadoValidacion) -> ResultadoValidacion:
    """Inserta un resultado de validacion cientifica."""
    db = await obtener_conexion()
    sql = """
        INSERT INTO validaciones (
            hipotesis_id, veredicto, razonamiento, nivel_confianza,
            sesgos_detectados, test_realizados, fecha_validacion
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
    """
    params = (
        validacion.hipotesis_id,
        validacion.veredicto.value if hasattr(validacion.veredicto, "value") else str(validacion.veredicto),
        validacion.razonamiento,
        validacion.nivel_confianza,
        _serialize(validacion.sesgos_detectados),
        _serialize(validacion.test_realizados),
        _ahora(),
    )
    try:
        await db.execute(sql, params)
        await db.commit()
    except sqlite3.IntegrityError as exc:
        raise ValueError(
            f"Validacion para hipotesis '{validacion.hipotesis_id}' ya existe"
        ) from exc
    except sqlite3.Error as exc:
        raise RuntimeError(f"Error al crear validacion: {exc}") from exc
    return validacion


async def obtener_validacion(hipotesis_id: str) -> ResultadoValidacion | None:
    """Recupera la validacion asociada a una hipotesis."""
    db = await obtener_conexion()
    cursor = await db.execute(
        "SELECT * FROM validaciones WHERE hipotesis_id = ?", (hipotesis_id,)
    )
    fila = await cursor.fetchone()
    await cursor.close()
    if fila is None:
        return None
    return _fila_a_validacion(fila)


async def listar_validaciones(
    veredicto: Any = None,
    limite: int = 100,
    offset: int = 0,
) -> list[ResultadoValidacion]:
    """
    Lista validaciones con filtro opcional por veredicto.

    Args:
        veredicto: Filtrar por tipo de veredicto.
        limite: Maximo de resultados.
        offset: Desplazamiento para paginacion.
    """
    db = await obtener_conexion()
    if veredicto:
        cursor = await db.execute(
            "SELECT * FROM validaciones WHERE veredicto = ? ORDER BY fecha_validacion DESC LIMIT ? OFFSET ?",
            (veredicto.value if hasattr(veredicto, "value") else str(veredicto), limite, offset),
        )
    else:
        cursor = await db.execute(
            "SELECT * FROM validaciones ORDER BY fecha_validacion DESC LIMIT ? OFFSET ?",
            (limite, offset),
        )
    filas = await cursor.fetchall()
    await cursor.close()
    return [_fila_a_validacion(f) for f in filas]


def _fila_a_validacion(fila: aiosqlite.Row) -> ResultadoValidacion:
    """Convierte una fila de la BD a objeto ResultadoValidacion."""
    try:
        from models import VeredictoValidacion
        veredicto = VeredictoValidacion(fila["veredicto"])
    except (ImportError, ValueError):
        veredicto = fila["veredicto"]

    try:
        return ResultadoValidacion(
            hipotesis_id=fila["hipotesis_id"],
            veredicto=veredicto,
            razonamiento=fila["razonamiento"],
            nivel_confianza=fila["nivel_confianza"],
            sesgos_detectados=_deserialize(fila["sesgos_detectados"], []),
            test_realizados=_deserialize(fila["test_realizados"], []),
        )
    except TypeError:
        return fila  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# CRUD: historial_nei (V1 - completo)
# ---------------------------------------------------------------------------

async def registrar_historial_nei(
    semana: int,
    pesos: dict[str, float],
    precision_sistema: float,
) -> int:
    """
    Registra una entrada en el historial de pesos NEI.

    Args:
        semana: Numero de semana (1-53).
        pesos: Diccionario con los pesos FR, GR, DV, NV, EM, ST.
        precision_sistema: Precision alcanzada esa semana.

    Returns:
        ID autoincremental de la entrada creada.
    """
    db = await obtener_conexion()
    sql = """
        INSERT INTO historial_nei (
            semana, peso_fr, peso_gr, peso_dv, peso_nv, peso_em, peso_st,
            precision_sistema, fecha_registro
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    params = (
        semana,
        pesos.get("FR", 0.0),
        pesos.get("GR", 0.0),
        pesos.get("DV", 0.0),
        pesos.get("NV", 0.0),
        pesos.get("EM", 0.0),
        pesos.get("ST", 0.0),
        precision_sistema,
        _ahora(),
    )
    try:
        cursor = await db.execute(sql, params)
        await db.commit()
        return cursor.lastrowid or 0
    except sqlite3.Error as exc:
        raise RuntimeError(f"Error al registrar historial NEI: {exc}") from exc


async def obtener_historial_nei(
    semana: int | None = None,
    limite: int = 100,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """
    Recupera el historial de pesos NEI.

    Args:
        semana: Filtrar por semana especifica.
        limite: Maximo de resultados.
        offset: Desplazamiento para paginacion.

    Returns:
        Lista de diccionarios con los registros del historial.
    """
    db = await obtener_conexion()
    if semana is not None:
        cursor = await db.execute(
            "SELECT * FROM historial_nei WHERE semana = ? ORDER BY fecha_registro DESC LIMIT ? OFFSET ?",
            (semana, limite, offset),
        )
    else:
        cursor = await db.execute(
            "SELECT * FROM historial_nei ORDER BY fecha_registro DESC LIMIT ? OFFSET ?",
            (limite, offset),
        )
    filas = await cursor.fetchall()
    await cursor.close()

    resultado = []
    for fila in filas:
        resultado.append(
            {
                "id": fila["id"],
                "semana": fila["semana"],
                "pesos": {
                    "FR": fila["peso_fr"],
                    "GR": fila["peso_gr"],
                    "DV": fila["peso_dv"],
                    "NV": fila["peso_nv"],
                    "EM": fila["peso_em"],
                    "ST": fila["peso_st"],
                },
                "precision_sistema": fila["precision_sistema"],
                "fecha_registro": fila["fecha_registro"],
            }
        )
    return resultado


# ---------------------------------------------------------------------------
# NUEVO V2: CRUD - ciclo_ejecuciones
# ---------------------------------------------------------------------------

async def registrar_ciclo(
    ciclo_type: str,
    params: dict[str, Any] | None = None,
    modulo: str = "sistema",
) -> int:
    """
    Registra el inicio de un ciclo de ejecucion.

    Args:
        ciclo_type: Tipo de ciclo ('reasoning', 'forecast', 'executive', 'operations').
        params: Parametros del ciclo.
        modulo: Modulo que ejecuta el ciclo.

    Returns:
        ID del ciclo registrado.
    """
    db = await obtener_conexion()
    sql = """
        INSERT INTO ciclo_ejecuciones (ciclo_type, estado, params, started_at, modulo)
        VALUES (?, 'running', ?, ?, ?)
    """
    try:
        cursor = await db.execute(sql, (_serialize(ciclo_type), _serialize(params or {}), _ahora(), modulo))
        await db.commit()
        return cursor.lastrowid or 0
    except sqlite3.Error as exc:
        raise RuntimeError(f"Error al registrar ciclo: {exc}") from exc


async def finalizar_ciclo(
    ciclo_id: int,
    estado: str,
    resultado: dict[str, Any] | None = None,
    resultado_summary: str | None = None,
    error_msg: str | None = None,
    duration_ms: int | None = None,
) -> None:
    """
    Marca un ciclo como finalizado.

    Args:
        ciclo_id: ID del ciclo a finalizar.
        estado: Estado final ('completed', 'failed', 'timeout', 'cancelled').
        resultado: Resultado completo del ciclo.
        resultado_summary: Resumen del resultado.
        error_msg: Mensaje de error si fallo.
        duration_ms: Duracion en milisegundos.
    """
    db = await obtener_conexion()
    sql = """
        UPDATE ciclo_ejecuciones
        SET estado = ?, resultado = ?, resultado_summary = ?, error_msg = ?, ended_at = ?, duration_ms = ?
        WHERE id = ?
    """
    await db.execute(
        sql,
        (estado, _serialize(resultado or {}), resultado_summary, error_msg, _ahora(), duration_ms, ciclo_id),
    )
    await db.commit()


async def obtener_ciclos(
    ciclo_type: str | None = None,
    estado: str | None = None,
    limite: int = 100,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """Lista ciclos de ejecucion con filtros opcionales."""
    db = await obtener_conexion()
    condiciones: list[str] = []
    params: list[Any] = []

    if ciclo_type:
        condiciones.append("ciclo_type = ?")
        params.append(ciclo_type)
    if estado:
        condiciones.append("estado = ?")
        params.append(estado)

    sql = "SELECT * FROM ciclo_ejecuciones"
    if condiciones:
        sql += " WHERE " + " AND ".join(condiciones)
    sql += " ORDER BY started_at DESC LIMIT ? OFFSET ?"
    params.extend([limite, offset])

    cursor = await db.execute(sql, params)
    filas = await cursor.fetchall()
    await cursor.close()
    return [dict(fila) for fila in filas]


# ---------------------------------------------------------------------------
# NUEVO V2: CRUD - audit_log
# ---------------------------------------------------------------------------

async def registrar_audit(
    modulo: str,
    accion: str,
    usuario: str = "sistema",
    params: dict[str, Any] | None = None,
    resultado: Any = None,
    resultado_tipo: str | None = None,
    duration_ms: int | None = None,
    ip_address: str | None = None,
    session_id: str | None = None,
    detalles: str | None = None,
) -> int:
    """
    Registra una accion en el audit log.

    Args:
        modulo: Modulo que realiza la accion.
        accion: Nombre de la accion.
        usuario: Usuario o entidad que realiza la accion.
        params: Parametros de la accion.
        resultado: Resultado de la accion.
        resultado_tipo: Tipo del resultado.
        duration_ms: Duracion en milisegundos.
        ip_address: Direccion IP si aplica.
        session_id: ID de sesion si aplica.
        detalles: Detalles adicionales.

    Returns:
        ID del registro de audit creado.
    """
    db = await obtener_conexion()
    sql = """
        INSERT INTO audit_log (
            timestamp, modulo, accion, usuario, params, resultado,
            resultado_tipo, duration_ms, ip_address, session_id, detalles
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    try:
        cursor = await db.execute(
            sql,
            (
                _ahora(), modulo, accion, usuario,
                _serialize(params or {}),
                _serialize(resultado) if resultado is not None else None,
                resultado_tipo, duration_ms, ip_address, session_id, detalles,
            ),
        )
        await db.commit()
        return cursor.lastrowid or 0
    except sqlite3.Error as exc:
        raise RuntimeError(f"Error al registrar audit: {exc}") from exc


async def consultar_audit(
    modulo: str | None = None,
    accion: str | None = None,
    usuario: str | None = None,
    desde: str | None = None,
    hasta: str | None = None,
    limite: int = 100,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """
    Consulta el audit log con filtros.

    Args:
        modulo: Filtrar por modulo.
        accion: Filtrar por accion.
        usuario: Filtrar por usuario.
        desde: Timestamp ISO minimo.
        hasta: Timestamp ISO maximo.
        limite: Maximo de resultados.
        offset: Desplazamiento para paginacion.

    Returns:
        Lista de registros de audit.
    """
    db = await obtener_conexion()
    condiciones: list[str] = []
    params: list[Any] = []

    if modulo:
        condiciones.append("modulo = ?")
        params.append(modulo)
    if accion:
        condiciones.append("accion = ?")
        params.append(accion)
    if usuario:
        condiciones.append("usuario = ?")
        params.append(usuario)
    if desde:
        condiciones.append("timestamp >= ?")
        params.append(desde)
    if hasta:
        condiciones.append("timestamp <= ?")
        params.append(hasta)

    sql = "SELECT * FROM audit_log"
    if condiciones:
        sql += " WHERE " + " AND ".join(condiciones)
    sql += " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
    params.extend([limite, offset])

    cursor = await db.execute(sql, params)
    filas = await cursor.fetchall()
    await cursor.close()
    return [dict(fila) for fila in filas]


# ---------------------------------------------------------------------------
# NUEVO V2: CRUD - health_checks
# ---------------------------------------------------------------------------

async def registrar_health_check(
    componente: str,
    estado: str,
    latencia_ms: int | None = None,
    tasa_exito: float | None = None,
    ultima_ejecucion: str | None = None,
    errores_recientes: int = 0,
    health_score: float | None = None,
    detalles: dict[str, Any] | None = None,
    mensaje: str | None = None,
) -> int:
    """
    Registra un health check de un componente.

    Args:
        componente: Nombre del componente.
        estado: Estado ('healthy', 'degraded', 'unhealthy', 'unknown').
        latencia_ms: Latencia en milisegundos.
        tasa_exito: Tasa de exito (0-1).
        ultima_ejecucion: Timestamp de la ultima ejecucion.
        errores_recientes: Numero de errores recientes.
        health_score: Puntuacion de salud (0-100).
        detalles: Detalles adicionales.
        mensaje: Mensaje descriptivo.

    Returns:
        ID del registro creado.
    """
    db = await obtener_conexion()
    sql = """
        INSERT INTO health_checks (
            timestamp, componente, estado, latencia_ms, tasa_exito,
            ultima_ejecucion, errores_recientes, health_score, detalles, mensaje
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    try:
        cursor = await db.execute(
            sql,
            (
                _ahora(), componente, estado, latencia_ms, tasa_exito,
                ultima_ejecucion, errores_recientes, health_score,
                _serialize(detalles or {}), mensaje,
            ),
        )
        await db.commit()
        return cursor.lastrowid or 0
    except sqlite3.Error as exc:
        raise RuntimeError(f"Error al registrar health check: {exc}") from exc


async def obtener_ultimo_health_check(componente: str) -> dict[str, Any] | None:
    """Obtiene el ultimo health check de un componente."""
    db = await obtener_conexion()
    cursor = await db.execute(
        "SELECT * FROM health_checks WHERE componente = ? ORDER BY timestamp DESC LIMIT 1",
        (componente,),
    )
    fila = await cursor.fetchone()
    await cursor.close()
    return dict(fila) if fila else None


async def obtener_health_checks(
    componente: str | None = None,
    estado: str | None = None,
    limite: int = 100,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """Lista health checks con filtros opcionales."""
    db = await obtener_conexion()
    condiciones: list[str] = []
    params: list[Any] = []

    if componente:
        condiciones.append("componente = ?")
        params.append(componente)
    if estado:
        condiciones.append("estado = ?")
        params.append(estado)

    sql = "SELECT * FROM health_checks"
    if condiciones:
        sql += " WHERE " + " AND ".join(condiciones)
    sql += " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
    params.extend([limite, offset])

    cursor = await db.execute(sql, params)
    filas = await cursor.fetchall()
    await cursor.close()
    return [dict(fila) for fila in filas]


# ---------------------------------------------------------------------------
# NUEVO V2: CRUD - trust_scores
# ---------------------------------------------------------------------------

async def inicializar_trust_score(modulo: str, score_inicial: float = 50.0) -> int:
    """
    Inicializa el trust score de un modulo si no existe.

    Args:
        modulo: Nombre del modulo.
        score_inicial: Puntuacion inicial (0-100).

    Returns:
        ID del registro creado o existente.
    """
    db = await obtener_conexion()
    # Verificar si ya existe
    cursor = await db.execute("SELECT id FROM trust_scores WHERE modulo = ?", (modulo,))
    fila = await cursor.fetchone()
    await cursor.close()

    if fila:
        return fila["id"]

    sql = """
        INSERT INTO trust_scores (
            timestamp, modulo, score, score_inicial, ultima_actualizacion
        ) VALUES (?, ?, ?, ?, ?)
    """
    ahora = _ahora()
    cursor = await db.execute(sql, (ahora, modulo, score_inicial, score_inicial, ahora))
    await db.commit()
    return cursor.lastrowid or 0


async def actualizar_trust_score(
    modulo: str,
    exito: bool,
    precision: float | None = None,
) -> dict[str, Any]:
    """
    Actualiza el trust score de un modulo basado en el resultado.

    Args:
        modulo: Nombre del modulo.
        exito: True si la ejecucion fue exitosa.
        precision: Precision de la ejecucion (0-1).

    Returns:
        Diccionario con el estado actualizado del trust score.
    """
    db = await obtener_conexion()

    # Obtener estado actual
    cursor = await db.execute("SELECT * FROM trust_scores WHERE modulo = ?", (modulo,))
    fila = await cursor.fetchone()
    await cursor.close()

    if not fila:
        await inicializar_trust_score(modulo)
        cursor = await db.execute("SELECT * FROM trust_scores WHERE modulo = ?", (modulo,))
        fila = await cursor.fetchone()
        await cursor.close()

    if not fila:
        raise RuntimeError(f"No se pudo inicializar trust score para {modulo}")

    # Calcular nuevos valores
    score = fila["score"]
    fallos_consecutivos = fila["fallos_consecutivos"]
    aciertos_consecutivos = fila["aciertos_consecutivos"]
    ejecuciones_total = fila["ejecuciones_total"] + 1
    ejecuciones_exitosas = fila["ejecuciones_exitosas"]
    ejecuciones_fallidas = fila["ejecuciones_fallidas"]
    precision_acumulada = fila["precision_acumulada"] or 0.0

    historial = _deserialize(fila["historial"], [])

    if exito:
        ejecuciones_exitosas += 1
        aciertos_consecutivos += 1
        fallos_consecutivos = 0
        # Reward: aumenta score hasta max 100
        reward = min(5 + aciertos_consecutivos * 0.5, 15)
        score = min(100.0, score + reward)
        if precision is not None:
            precision_acumulada += precision
    else:
        ejecuciones_fallidas += 1
        fallos_consecutivos += 1
        aciertos_consecutivos = 0
        # Penalizacion: reduce score, mas severa con fallos consecutivos
        penalty = min(5 + fallos_consecutivos * 2, 20)
        score = max(0.0, score - penalty)

    # Actualizar historial
    historial.append({
        "timestamp": _ahora(),
        "exito": exito,
        "precision": precision,
        "score": score,
    })
    if len(historial) > 100:
        historial = historial[-100:]

    sql = """
        UPDATE trust_scores SET
            score = ?, ejecuciones_total = ?, ejecuciones_exitosas = ?,
            ejecuciones_fallidas = ?, fallos_consecutivos = ?,
            aciertos_consecutivos = ?, precision_acumulada = ?,
            ultima_actualizacion = ?, historial = ?
        WHERE modulo = ?
    """
    await db.execute(
        sql,
        (
            round(score, 2), ejecuciones_total, ejecuciones_exitosas,
            ejecuciones_fallidas, fallos_consecutivos,
            aciertos_consecutivos, round(precision_acumulada, 4),
            _ahora(), _serialize(historial), modulo,
        ),
    )
    await db.commit()

    return {
        "modulo": modulo,
        "score": round(score, 2),
        "ejecuciones_total": ejecuciones_total,
        "ejecuciones_exitosas": ejecuciones_exitosas,
        "ejecuciones_fallidas": ejecuciones_fallidas,
        "fallos_consecutivos": fallos_consecutivos,
        "aciertos_consecutivos": aciertos_consecutivos,
    }


async def obtener_trust_score(modulo: str) -> dict[str, Any] | None:
    """Obtiene el trust score de un modulo."""
    db = await obtener_conexion()
    cursor = await db.execute("SELECT * FROM trust_scores WHERE modulo = ?", (modulo,))
    fila = await cursor.fetchone()
    await cursor.close()
    return dict(fila) if fila else None


async def listar_trust_scores() -> list[dict[str, Any]]:
    """Lista todos los trust scores."""
    db = await obtener_conexion()
    cursor = await db.execute("SELECT * FROM trust_scores ORDER BY score DESC")
    filas = await cursor.fetchall()
    await cursor.close()
    return [dict(fila) for fila in filas]


# ---------------------------------------------------------------------------
# NUEVO V2: CRUD - metricas_sistema
# ---------------------------------------------------------------------------

async def registrar_metrica(
    metric_name: str,
    metric_value: float,
    metric_type: str = "gauge",
    tags: dict[str, str] | None = None,
    ciclo_type: str | None = None,
    modulo: str | None = None,
    fuente: str = "sistema",
) -> int:
    """
    Registra una metrica del sistema.

    Args:
        metric_name: Nombre de la metrica.
        metric_value: Valor numerico.
        metric_type: Tipo ('gauge', 'counter', 'histogram', 'summary').
        tags: Etiquetas adicionales.
        ciclo_type: Ciclo asociado si aplica.
        modulo: Modulo asociado si aplica.
        fuente: Fuente de la metrica.

    Returns:
        ID del registro creado.
    """
    db = await obtener_conexion()
    sql = """
        INSERT INTO metricas_sistema (
            timestamp, metric_name, metric_value, metric_type, tags, ciclo_type, modulo, fuente
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """
    try:
        cursor = await db.execute(
            sql,
            (_ahora(), metric_name, metric_value, metric_type,
             _serialize(tags or {}), ciclo_type, modulo, fuente),
        )
        await db.commit()
        return cursor.lastrowid or 0
    except sqlite3.Error as exc:
        raise RuntimeError(f"Error al registrar metrica: {exc}") from exc


async def obtener_serie_metrica(
    metric_name: str,
    start: str | None = None,
    end: str | None = None,
    modulo: str | None = None,
    limite: int = 1000,
) -> list[dict[str, Any]]:
    """
    Obtiene una serie temporal de una metrica.

    Args:
        metric_name: Nombre de la metrica.
        start: Timestamp ISO de inicio.
        end: Timestamp ISO de fin.
        modulo: Filtrar por modulo.
        limite: Maximo de puntos.

    Returns:
        Lista de puntos de la serie temporal.
    """
    db = await obtener_conexion()
    condiciones: list[str] = ["metric_name = ?"]
    params: list[Any] = [metric_name]

    if start:
        condiciones.append("timestamp >= ?")
        params.append(start)
    if end:
        condiciones.append("timestamp <= ?")
        params.append(end)
    if modulo:
        condiciones.append("modulo = ?")
        params.append(modulo)

    sql = "SELECT * FROM metricas_sistema WHERE " + " AND ".join(condiciones)
    sql += " ORDER BY timestamp DESC LIMIT ?"
    params.append(limite)

    cursor = await db.execute(sql, params)
    filas = await cursor.fetchall()
    await cursor.close()
    return [dict(fila) for fila in filas]


async def obtener_metricas_dashboard() -> dict[str, Any]:
    """
    Obtiene datos agregados para el dashboard.

    Returns:
        Diccionario con metricas agregadas por categoria.
    """
    db = await obtener_conexion()
    resultado: dict[str, Any] = {"timestamp": _ahora()}

    # Metricas por ciclo
    for ciclo in ["reasoning", "forecast", "executive", "operations"]:
        cursor = await db.execute(
            "SELECT COUNT(*) as total FROM metricas_sistema WHERE ciclo_type = ?",
            (ciclo,),
        )
        fila = await cursor.fetchone()
        resultado[f"{ciclo}_count"] = fila["total"] if fila else 0
        await cursor.close()

    # Metricas recientes
    cursor = await db.execute(
        """
        SELECT metric_name, AVG(metric_value) as promedio, COUNT(*) as total
        FROM metricas_sistema
        WHERE timestamp >= datetime('now', '-1 hour')
        GROUP BY metric_name
        """
    )
    filas = await cursor.fetchall()
    resultado["metricas_recientes"] = {fila["metric_name"]: {"promedio": fila["promedio"], "total": fila["total"]} for fila in filas}
    await cursor.close()

    # Total de metricas
    cursor = await db.execute("SELECT COUNT(*) as total FROM metricas_sistema")
    fila = await cursor.fetchone()
    resultado["total_metricas"] = fila["total"] if fila else 0
    await cursor.close()

    return resultado


# ---------------------------------------------------------------------------
# NUEVO V2: CRUD - backups_registro
# ---------------------------------------------------------------------------

async def registrar_backup(
    nombre_backup: str,
    ruta_backup: str,
    tamano_bytes: int | None = None,
    tipo: str = "auto",
    tablas_incluidas: list[str] | None = None,
    duracion_ms: int | None = None,
    checksum: str | None = None,
    notas: str | None = None,
) -> int:
    """
    Registra un backup en la base de datos.

    Args:
        nombre_backup: Nombre del archivo de backup.
        ruta_backup: Ruta completa al backup.
        tamano_bytes: Tamano en bytes.
        tipo: Tipo de backup ('auto', 'manual', 'pre_update', 'emergency').
        tablas_incluidas: Lista de tablas incluidas.
        duracion_ms: Duracion del backup en ms.
        checksum: Hash de verificacion.
        notas: Notas adicionales.

    Returns:
        ID del registro creado.
    """
    db = await obtener_conexion()
    sql = """
        INSERT INTO backups_registro (
            timestamp, nombre_backup, ruta_backup, tamano_bytes, tipo,
            tablas_incluidas, duracion_ms, checksum, notas
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    try:
        cursor = await db.execute(
            sql,
            (
                _ahora(), nombre_backup, ruta_backup, tamano_bytes, tipo,
                _serialize(tablas_incluidas or []), duracion_ms, checksum, notas,
            ),
        )
        await db.commit()
        return cursor.lastrowid or 0
    except sqlite3.Error as exc:
        raise RuntimeError(f"Error al registrar backup: {exc}") from exc


async def listar_backups(
    tipo: str | None = None,
    estado: str | None = None,
    limite: int = 100,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """
    Lista backups registrados con filtros opcionales.

    Args:
        tipo: Filtrar por tipo.
        estado: Filtrar por estado.
        limite: Maximo de resultados.
        offset: Desplazamiento.

    Returns:
        Lista de backups.
    """
    db = await obtener_conexion()
    condiciones: list[str] = []
    params: list[Any] = []

    if tipo:
        condiciones.append("tipo = ?")
        params.append(tipo)
    if estado:
        condiciones.append("estado = ?")
        params.append(estado)

    sql = "SELECT * FROM backups_registro"
    if condiciones:
        sql += " WHERE " + " AND ".join(condiciones)
    sql += " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
    params.extend([limite, offset])

    cursor = await db.execute(sql, params)
    filas = await cursor.fetchall()
    await cursor.close()
    return [dict(fila) for fila in filas]


async def marcar_backup_restaurado(backup_id: int) -> None:
    """Marca un backup como restaurado."""
    db = await obtener_conexion()
    await db.execute(
        "UPDATE backups_registro SET restaurado = 1 WHERE id = ?",
        (backup_id,),
    )
    await db.commit()


# ---------------------------------------------------------------------------
# Consultas especializadas V1
# ---------------------------------------------------------------------------

async def contar_hipotesis_por_estado() -> dict[str, int]:
    """
    Cuenta hipotesis agrupadas por estado.

    Returns:
        Diccionario {estado: cantidad}.
    """
    db = await obtener_conexion()
    cursor = await db.execute(
        "SELECT estado, COUNT(*) as total FROM hipotesis GROUP BY estado"
    )
    filas = await cursor.fetchall()
    await cursor.close()
    return {fila["estado"]: fila["total"] for fila in filas}


async def hipotesis_mas_evidenciadas(limite: int = 10) -> list[Hipotesis]:
    """
    Obtiene las hipotesis con mas evidencias acumuladas.

    Args:
        limite: Maximo de resultados.

    Returns:
        Lista de hipotesis ordenadas por numero de evidencias descendente.
    """
    db = await obtener_conexion()
    cursor = await db.execute(
        """
        SELECT * FROM hipotesis
        WHERE estado = 'activa'
        ORDER BY LENGTH(evidencias) DESC
        LIMIT ?
        """,
        (limite,),
    )
    filas = await cursor.fetchall()
    await cursor.close()
    return [_fila_a_hipotesis(f) for f in filas]


async def predicciones_abiertas() -> list[Prediccion]:
    """
    Obtiene todas las predicciones en estado abierto.

    Returns:
        Lista de predicciones abiertas ordenadas por fecha.
    """
    try:
        from models import EstadoPrediccion
        return await listar_predicciones(estado=EstadoPrediccion.ABIERTA)
    except ImportError:
        return await listar_predicciones(estado="abierta")


async def estadisticas_sistema() -> dict[str, Any]:
    """
    Calcula estadisticas agregadas del sistema.

    Returns:
        Diccionario con conteos y metricas clave.
    """
    db = await obtener_conexion()

    stats: dict[str, Any] = {}

    # Conteos basicos
    for tabla in [
        "hipotesis", "predicciones", "escenarios", "descubrimientos_semanales",
        "cambios_narrativa", "grafo_nodos", "grafo_relaciones", "validaciones",
    ]:
        cursor = await db.execute(f"SELECT COUNT(*) as total FROM {tabla}")
        fila = await cursor.fetchone()
        stats[f"total_{tabla}"] = fila["total"] if fila else 0
        await cursor.close()

    # Nuevas tablas V2
    for tabla in [
        "ciclo_ejecuciones", "audit_log", "health_checks",
        "trust_scores", "metricas_sistema", "backups_registro",
    ]:
        try:
            cursor = await db.execute(f"SELECT COUNT(*) as total FROM {tabla}")
            fila = await cursor.fetchone()
            stats[f"total_{tabla}"] = fila["total"] if fila else 0
            await cursor.close()
        except sqlite3.Error:
            stats[f"total_{tabla}"] = 0

    # Hipotesis por estado
    stats["hipotesis_por_estado"] = await contar_hipotesis_por_estado()

    # Confianza promedio de hipotesis activas
    cursor = await db.execute(
        "SELECT AVG(confianza) as promedio FROM hipotesis WHERE estado = 'activa'"
    )
    fila = await cursor.fetchone()
    stats["confianza_promedio_activas"] = round(fila["promedio"] or 0.0, 4)
    await cursor.close()

    # Ultimo descubrimiento semanal
    cursor = await db.execute(
        "SELECT semana, confianza_promedio, nivel_actividad FROM descubrimientos_semanales ORDER BY fecha_fin DESC LIMIT 1"
    )
    fila = await cursor.fetchone()
    if fila:
        stats["ultima_semana"] = {
            "semana": fila["semana"],
            "confianza_promedio": fila["confianza_promedio"],
            "nivel_actividad": fila["nivel_actividad"],
        }
    await cursor.close()

    # Trust scores promedio
    cursor = await db.execute("SELECT AVG(score) as promedio FROM trust_scores")
    fila = await cursor.fetchone()
    stats["trust_score_promedio"] = round(fila["promedio"] or 0.0, 2)
    await cursor.close()

    return stats


async def buscar_hipotesis_por_tag(tag: str, limite: int = 50) -> list[Hipotesis]:
    """
    Busca hipotesis que contengan una etiqueta especifica.

    Args:
        tag: Etiqueta a buscar.
        limite: Maximo de resultados.

    Returns:
        Lista de hipotesis con esa etiqueta.
    """
    return await listar_hipotesis(tag=tag, limite=limite)


async def tendencias_recientes(dias: int = 30, limite: int = 20) -> list[CambioNarrativa]:
    """
    Obtiene cambios de narrativa detectados recientemente.

    Args:
        dias: Numero de dias hacia atras para filtrar.
        limite: Maximo de resultados.

    Returns:
        Lista de cambios recientes ordenados por fecha.
    """
    db = await obtener_conexion()
    from datetime import timedelta

    fecha_limite = (datetime.now(tz=timezone.utc) - timedelta(days=dias)).isoformat()
    cursor = await db.execute(
        """
        SELECT * FROM cambios_narrativa
        WHERE fecha_detectado >= ?
        ORDER BY fecha_detectado DESC
        LIMIT ?
        """,
        (fecha_limite, limite),
    )
    filas = await cursor.fetchall()
    await cursor.close()
    return [_fila_a_cambio_narrativa(f) for f in filas]
