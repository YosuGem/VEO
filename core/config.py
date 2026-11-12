# config.py - VEO v2
"""
Configuracion central del Sistema Operativo para Intuicion Social (VEO) v2.

Version ampliada con soporte para las 4 capas de VEO v2:
    - VeoCore: Motor de razonamiento y evaluacion intuitiva
    - HermesCommander: Motor de ejecucion y despliegue
    - Operations: Capa de monitoreo, logging, backups y metricas
    - Governance: Siete leyes de gobernanza de IA

Toda la configuracion se carga via variables de entorno con valores por defecto
sensatos para desarrollo local. En produccion se recomienda usar un archivo .env
o el sistema de secretos de la plataforma de despliegue.

NEI = Nucleo de Evaluacion Intuitiva. Los pesos FR, GR, DV, NV, EM, ST definen
como el sistema pondera las senales que recoge de internet. Son auto-aprendibles:
el sistema ajusta estos pesos semanalmente segun la precision de sus detecciones.

Ejemplo de uso:
    >>> from veo_v2.core.config import get_config
    >>> cfg = get_config()
    >>> print(cfg.nei_weights)
    {'FR': 0.20, 'GR': 0.25, ...}
    >>> print(cfg.veo_core.max_concurrent_tasks)
    5
    >>> print(cfg.governance.ley_1_transparencia)
    True
"""

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


# ---------------------------------------------------------------------------
# Configuracion NEI (Nucleo de Evaluacion Intuitiva) - V1
# ---------------------------------------------------------------------------

class NEIWeights(BaseSettings):
    """
    Pesos del Nucleo de Evaluacion Intuitiva (NEI).

    Cada peso representa cuanta importancia da el sistema a una senal
    especifica al evaluar si una narrativa esta cambiando. La suma debe
    ser 1.0 para que la puntuacion sea interpretable como probabilidad.

    Atributos:
        FR: Frecuencia de aparicion de terminos clave en fuentes.
        GR: Giro retorico, cambios en como se cuentan las historias.
        DV: Diversidad de fuentes que mencionan el tema.
        NV: Nivel de novedad respecto al periodo anterior.
        EM: Carga emocional detectada en los textos.
        ST: Sentimiento general (positivo/negativo).
    """

    model_config = SettingsConfigDict(
        env_prefix="SOIS_NEI_",
        env_nested_delimiter="__",
        extra="ignore",
    )

    FR: float = Field(default=0.20, ge=0.0, le=1.0, description="Peso: Frecuencia de aparicion")
    GR: float = Field(default=0.25, ge=0.0, le=1.0, description="Peso: Giro retorico")
    DV: float = Field(default=0.20, ge=0.0, le=1.0, description="Peso: Diversidad de fuentes")
    NV: float = Field(default=0.20, ge=0.0, le=1.0, description="Peso: Nivel de novedad")
    EM: float = Field(default=0.10, ge=0.0, le=1.0, description="Peso: Carga emocional")
    ST: float = Field(default=0.05, ge=0.0, le=1.0, description="Peso: Sentimiento general")

    @field_validator("FR", "GR", "DV", "NV", "EM", "ST", mode="before")
    @classmethod
    def _parse_float(cls, v: Any) -> float:
        """Convierte strings a float, maneja valores vacios."""
        if v is None or v == "":
            return 0.0
        if isinstance(v, str):
            v = v.strip()
            if v.lower() in ("null", "none", "nil"):
                return 0.0
        return float(v)

    def normalizar(self) -> dict[str, float]:
        """
        Escala los pesos para que sumen exactamente 1.0.

        Esto evita problemas numericos cuando el sistema ajusta
        los pesos durante el aprendizaje automatico.
        """
        total = self.FR + self.GR + self.DV + self.NV + self.EM + self.ST
        if total == 0:
            return {"FR": 0.20, "GR": 0.25, "DV": 0.20, "NV": 0.20, "EM": 0.10, "ST": 0.05}
        return {
            "FR": round(self.FR / total, 4),
            "GR": round(self.GR / total, 4),
            "DV": round(self.DV / total, 4),
            "NV": round(self.NV / total, 4),
            "EM": round(self.EM / total, 4),
            "ST": round(self.ST / total, 4),
        }


# ---------------------------------------------------------------------------
# Configuracion LLM - V1
# ---------------------------------------------------------------------------

class LLMConfig(BaseSettings):
    """Configuracion del modelo de lenguaje para analisis de narrativas."""

    model_config = SettingsConfigDict(
        env_prefix="SOIS_LLM_",
        env_nested_delimiter="__",
        extra="ignore",
    )

    url: str = Field(default="http://localhost:11434/v1", description="URL base del servidor LLM")
    modelo: str = Field(default="llama3.2:3b", description="Nombre del modelo a usar")
    timeout: int = Field(default=120, ge=1, description="Timeout en segundos para peticiones")
    max_tokens: int = Field(default=4096, ge=1, description="Maximo de tokens por respuesta")
    temperatura: float = Field(default=0.3, ge=0.0, le=2.0, description="Temperatura de muestreo")
    api_key: str = Field(default="not-needed", description="API key si el servidor la requiere")

    @field_validator("timeout", "max_tokens", mode="before")
    @classmethod
    def _parse_int(cls, v: Any) -> int:
        if v is None or v == "":
            return 0
        if isinstance(v, str):
            v = v.strip()
            if v.lower() in ("null", "none", "nil"):
                return 0
        return int(v)


# ---------------------------------------------------------------------------
# Configuracion Embeddings - V1
# ---------------------------------------------------------------------------

class EmbeddingConfig(BaseSettings):
    """Configuracion del modelo de embeddings para vectorizacion de textos."""

    model_config = SettingsConfigDict(
        env_prefix="SOIS_EMBED_",
        env_nested_delimiter="__",
        extra="ignore",
    )

    modelo: str = Field(
        default="sentence-transformers/all-MiniLM-L6-v2",
        description="Modelo de embeddings de HuggingFace",
    )
    dimension: int = Field(default=384, ge=1, description="Dimension del vector de embedding")
    batch_size: int = Field(default=32, ge=1, description="Tamano de lote para procesamiento")
    device: str = Field(default="cpu", description="Dispositivo: cpu o cuda")

    @field_validator("dimension", "batch_size", mode="before")
    @classmethod
    def _parse_int(cls, v: Any) -> int:
        if v is None or v == "":
            return 0
        if isinstance(v, str):
            v = v.strip()
            if v.lower() in ("null", "none", "nil"):
                return 0
        return int(v)


# ---------------------------------------------------------------------------
# Configuracion API REST - V1
# ---------------------------------------------------------------------------

class APIConfig(BaseSettings):
    """Configuracion del servidor API REST."""

    model_config = SettingsConfigDict(
        env_prefix="SOIS_API_",
        env_nested_delimiter="__",
        extra="ignore",
    )

    host: str = Field(default="0.0.0.0", description="Host de escucha del servidor")
    port: int = Field(default=8000, ge=1, le=65535, description="Puerto del servidor")
    workers: int = Field(default=1, ge=1, description="Numero de workers")
    reload: bool = Field(default=False, description="Recarga automatica en desarrollo")
    cors_origins: str = Field(default="*", description="Origenes permitidos para CORS")

    @field_validator("port", "workers", mode="before")
    @classmethod
    def _parse_int(cls, v: Any) -> int:
        if v is None or v == "":
            return 0
        if isinstance(v, str):
            v = v.strip()
            if v.lower() in ("null", "none", "nil"):
                return 0
        return int(v)

    @field_validator("reload", mode="before")
    @classmethod
    def _parse_bool(cls, v: Any) -> bool:
        if isinstance(v, bool):
            return v
        if isinstance(v, str):
            return v.strip().lower() in ("true", "1", "yes", "on")
        return bool(v)


# ---------------------------------------------------------------------------
# Configuracion Logging - V1
# ---------------------------------------------------------------------------

class LoggingConfig(BaseSettings):
    """Configuracion del sistema de logging."""

    model_config = SettingsConfigDict(
        env_prefix="SOIS_LOG_",
        env_nested_delimiter="__",
        extra="ignore",
    )

    nivel: str = Field(default="INFO", description="Nivel de logging (DEBUG, INFO, WARNING, ERROR)")
    formato_json: bool = Field(default=True, description="Usar formato JSON en archivo")
    archivo: str = Field(default="veo.log", description="Nombre del archivo de log")
    rotacion_dias: int = Field(default=7, ge=1, description="Dias de retencion de logs")
    max_bytes: int = Field(default=10_485_760, ge=1, description="Tamano maximo del archivo antes de rotar")
    consola_colores: bool = Field(default=True, description="Usar colores en consola")

    @field_validator("rotacion_dias", "max_bytes", mode="before")
    @classmethod
    def _parse_int(cls, v: Any) -> int:
        if v is None or v == "":
            return 0
        if isinstance(v, str):
            v = v.strip()
            if v.lower() in ("null", "none", "nil"):
                return 0
        return int(v)

    @field_validator("formato_json", "consola_colores", mode="before")
    @classmethod
    def _parse_bool(cls, v: Any) -> bool:
        if isinstance(v, bool):
            return v
        if isinstance(v, str):
            return v.strip().lower() in ("true", "1", "yes", "on")
        return bool(v)


# ---------------------------------------------------------------------------
# Configuracion Mercado de Predicciones - V1
# ---------------------------------------------------------------------------

class MercadoConfig(BaseSettings):
    """
    Configuracion del mercado de predicciones interno.

    El mercado permite a los agentes del sistema 'apostar' sobre
    que narrativas se confirmaran o refutaran, generando una
    senal adicional de confianza basada en el consenso.
    """

    model_config = SettingsConfigDict(
        env_prefix="SOIS_MERCADO_",
        env_nested_delimiter="__",
        extra="ignore",
    )

    liquidez_inicial: float = Field(
        default=1000.0, ge=0.0, description="Liquidez inicial del mercado"
    )
    comision: float = Field(
        default=0.02, ge=0.0, le=1.0, description="Comision por transaccion (2%)"
    )
    numero_maximo_predicciones: int = Field(
        default=100, ge=1, description="Maximo de predicciones simultaneas"
    )
    periodo_cierre_dias: int = Field(
        default=30, ge=1, description="Dias hasta cierre automatico"
    )

    @field_validator("liquidez_inicial", "comision", mode="before")
    @classmethod
    def _parse_float(cls, v: Any) -> float:
        if v is None or v == "":
            return 0.0
        if isinstance(v, str):
            v = v.strip()
            if v.lower() in ("null", "none", "nil"):
                return 0.0
        return float(v)

    @field_validator("numero_maximo_predicciones", "periodo_cierre_dias", mode="before")
    @classmethod
    def _parse_int(cls, v: Any) -> int:
        if v is None or v == "":
            return 0
        if isinstance(v, str):
            v = v.strip()
            if v.lower() in ("null", "none", "nil"):
                return 0
        return int(v)


# ---------------------------------------------------------------------------
# Configuracion Directorios - V1
# ---------------------------------------------------------------------------

class DirectoriosConfig(BaseSettings):
    """Rutas de directorios para datos, journal y cache."""

    model_config = SettingsConfigDict(
        env_prefix="SOIS_DIR_",
        env_nested_delimiter="__",
        extra="ignore",
    )

    base: str = Field(default="./sois-data", description="Directorio base del sistema")
    datos: str = Field(default="", description="Directorio de datos persistentes")
    journal: str = Field(default="", description="Directorio de logs de operacion")
    cache: str = Field(default="", description="Directorio de cache temporal")
    salida: str = Field(default="", description="Directorio de salidas y reportes")

    @field_validator("datos", "journal", "cache", "salida", mode="before")
    @classmethod
    def _default_subdir(cls, v: Any, info: Any) -> str:
        """Si no se especifica subdirectorio, usa el nombre del campo."""
        if v and str(v).strip():
            return str(v).strip()
        return info.field_name


# ---------------------------------------------------------------------------
# NUEVO V2: Configuracion VeoCore
# ---------------------------------------------------------------------------

class VeoCoreConfig(BaseSettings):
    """
    Configuracion del motor VeoCore (razonamiento y evaluacion intuitiva).

    Controla los parametros del ciclo de razonamiento, incluyendo
    los intervalos entre ciclos, tareas concurrentes y umbrales
    de confianza para la deteccion de cambios de narrativa.
    """

    model_config = SettingsConfigDict(
        env_prefix="SOIS_VEOCORE_",
        env_nested_delimiter="__",
        extra="ignore",
    )

    ciclos_intervalos: int = Field(
        default=3600, ge=60, description="Segundos entre ciclos de razonamiento"
    )
    max_concurrent_tasks: int = Field(
        default=5, ge=1, le=20, description="Maximo de tareas concurrentes"
    )
    default_confidence_threshold: float = Field(
        default=0.6, ge=0.0, le=1.0, description="Umbral minimo de confianza por defecto"
    )

    @field_validator("ciclos_intervalos", "max_concurrent_tasks", mode="before")
    @classmethod
    def _parse_int(cls, v: Any) -> int:
        if v is None or v == "":
            return 0
        if isinstance(v, str):
            v = v.strip()
            if v.lower() in ("null", "none", "nil"):
                return 0
        return int(v)

    @field_validator("default_confidence_threshold", mode="before")
    @classmethod
    def _parse_float(cls, v: Any) -> float:
        if v is None or v == "":
            return 0.0
        if isinstance(v, str):
            v = v.strip()
            if v.lower() in ("null", "none", "nil"):
                return 0.0
        return float(v)


# ---------------------------------------------------------------------------
# NUEVO V2: Configuracion Operations
# ---------------------------------------------------------------------------

class OperationsConfig(BaseSettings):
    """
    Configuracion de la capa de Operations.

    Controla el logging, backup automatico, retencion de metricas
    y el intervalo de health checks del sistema.
    """

    model_config = SettingsConfigDict(
        env_prefix="SOIS_OPS_",
        env_nested_delimiter="__",
        extra="ignore",
    )

    log_level: str = Field(
        default="INFO", description="Nivel de logging: DEBUG, INFO, WARNING, ERROR, CRITICAL"
    )
    backup_interval_hours: int = Field(
        default=24, ge=1, description="Horas entre backups automaticos"
    )
    metrics_retention_days: int = Field(
        default=90, ge=1, description="Dias de retencion de metricas"
    )
    health_check_interval: int = Field(
        default=60, ge=10, description="Segundos entre health checks"
    )

    @field_validator("backup_interval_hours", "metrics_retention_days", "health_check_interval", mode="before")
    @classmethod
    def _parse_int(cls, v: Any) -> int:
        if v is None or v == "":
            return 0
        if isinstance(v, str):
            v = v.strip()
            if v.lower() in ("null", "none", "nil"):
                return 0
        return int(v)


# ---------------------------------------------------------------------------
# NUEVO V2: Configuracion HermesCommander
# ---------------------------------------------------------------------------

class HermesCommanderConfig(BaseSettings):
    """
    Configuracion del motor HermesCommander (ejecucion y despliegue).

    Controla la cola de peticiones, timeouts y prioridades
    por defecto para las operaciones de ejecucion.
    """

    model_config = SettingsConfigDict(
        env_prefix="SOIS_HERMES_",
        env_nested_delimiter="__",
        extra="ignore",
    )

    max_queue_size: int = Field(
        default=1000, ge=10, description="Tamano maximo de la cola de peticiones"
    )
    request_timeout_seconds: int = Field(
        default=300, ge=10, description="Timeout en segundos para peticiones"
    )
    default_priority: int = Field(
        default=5, ge=1, le=10, description="Prioridad por defecto (1=urgente, 10=baja)"
    )

    @field_validator("max_queue_size", "request_timeout_seconds", "default_priority", mode="before")
    @classmethod
    def _parse_int(cls, v: Any) -> int:
        if v is None or v == "":
            return 0
        if isinstance(v, str):
            v = v.strip()
            if v.lower() in ("null", "none", "nil"):
                return 0
        return int(v)


# ---------------------------------------------------------------------------
# NUEVO V2: Configuracion Governance (7 Leyes)
# ---------------------------------------------------------------------------

class GovernanceConfig(BaseSettings):
    """
    Configuracion de gobernanza: Las 7 Leyes de VEO.

    Cada ley es un setting booleano que puede activarse o
    desactivarse. Por defecto todas estan activas en produccion.
    Las leyes garantizan el comportamiento etico y seguro del sistema.

    Leyes:
        1. Transparencia: El sistema debe explicar sus decisiones.
        2. Control Humano: Los humanos tienen veto sobre acciones criticas.
        3. Privacidad: Los datos personales se protegen y anonimizan.
        4. Equidad: El sistema no discrimina por origen, genero, etc.
        5. Seguridad: Se prioriza la seguridad sobre la velocidad.
        6. Responsabilidad: Cada decision es trazable a un responsable.
        7. Mejora Continua: El sistema aprende de sus errores.
    """

    model_config = SettingsConfigDict(
        env_prefix="SOIS_GOV_",
        env_nested_delimiter="__",
        extra="ignore",
    )

    ley_1_transparencia: bool = Field(
        default=True, description="Ley 1: El sistema explica sus decisiones"
    )
    ley_2_control_humano: bool = Field(
        default=True, description="Ley 2: Veto humano sobre acciones criticas"
    )
    ley_3_privacidad: bool = Field(
        default=True, description="Ley 3: Proteccion y anonimizacion de datos"
    )
    ley_4_equidad: bool = Field(
        default=True, description="Ley 4: No discriminacion"
    )
    ley_5_seguridad: bool = Field(
        default=True, description="Ley 5: Seguridad sobre velocidad"
    )
    ley_6_responsabilidad: bool = Field(
        default=True, description="Ley 6: Trazabilidad de decisiones"
    )
    ley_7_mejora_continua: bool = Field(
        default=True, description="Ley 7: Aprendizaje de errores"
    )

    @field_validator(
        "ley_1_transparencia",
        "ley_2_control_humano",
        "ley_3_privacidad",
        "ley_4_equidad",
        "ley_5_seguridad",
        "ley_6_responsabilidad",
        "ley_7_mejora_continua",
        mode="before",
    )
    @classmethod
    def _parse_bool(cls, v: Any) -> bool:
        if isinstance(v, bool):
            return v
        if isinstance(v, str):
            return v.strip().lower() in ("true", "1", "yes", "on")
        return bool(v)

    def verificar_leyes(self) -> dict[str, bool]:
        """
        Devuelve el estado de todas las leyes.

        Returns:
            Diccionario con nombre de ley -> estado (True/False).
        """
        return {
            "ley_1_transparencia": self.ley_1_transparencia,
            "ley_2_control_humano": self.ley_2_control_humano,
            "ley_3_privacidad": self.ley_3_privacidad,
            "ley_4_equidad": self.ley_4_equidad,
            "ley_5_seguridad": self.ley_5_seguridad,
            "ley_6_responsabilidad": self.ley_6_responsabilidad,
            "ley_7_mejora_continua": self.ley_7_mejora_continua,
        }

    def todas_activas(self) -> bool:
        """Comprueba si todas las leyes de gobernanza estan activas."""
        return all(self.verificar_leyes().values())

    def leyes_activas_count(self) -> int:
        """Devuelve el numero de leyes activas."""
        return sum(1 for v in self.verificar_leyes().values() if v)


# ---------------------------------------------------------------------------
# Settings principal - V1 compatible + V2 extensions
# ---------------------------------------------------------------------------

class Settings(BaseSettings):
    """
    Configuracion central de VEO v2.

    Reune todos los submodulos de configuracion V1 (NEI, LLM, API, etc.)
    y los nuevos modulos V2 (VeoCore, Operations, HermesCommander, Governance).

    Variables de entorno reconocidas (prefijo SOIS_):
        SOIS_MIN_CONFIDENCE -- Umbral minimo de confianza (0.6)
        SOIS_MIN_EVIDENCE   -- Minimo de evidencias para considerar (3)
        SOIS_AMBIENTE       -- Entorno de ejecucion: dev/test/prod
        SOIS_DIR_BASE       -- Directorio base del sistema

    Variables V2 nuevas:
        SOIS_VEOCORE_CICLOS_INTERVALOS         -- Segundos entre ciclos
        SOIS_VEOCORE_MAX_CONCURRENT_TASKS      -- Tareas concurrentes
        SOIS_OPS_LOG_LEVEL                     -- Nivel de logging
        SOIS_OPS_BACKUP_INTERVAL_HOURS         -- Intervalo de backup
        SOIS_HERMES_MAX_QUEUE_SIZE             -- Tamano de cola
        SOIS_GOV_LEY_1_TRANSPARENCIA           -- Activar ley 1

    Ejemplo:
        SOIS_MIN_CONFIDENCE=0.75 SOIS_AMBIENTE=prod python main.py
    """

    model_config = SettingsConfigDict(
        env_prefix="SOIS_",
        env_nested_delimiter="__",
        extra="ignore",
        env_file=".env",
        env_file_encoding="utf-8",
    )

    # Umbrales de deteccion: estos valores determinan cuando el sistema
    # considera que ha detectado un cambio de narrativa real y no ruido.
    min_confidence: float = Field(
        default=0.6,
        ge=0.0,
        le=1.0,
        description="Confianza minima para reportar un cambio de narrativa",
    )
    min_evidence: int = Field(
        default=3,
        ge=1,
        description="Minimo de evidencias independientes requeridas",
    )

    # Entorno: dev, test, prod
    ambiente: str = Field(default="dev", description="Entorno de ejecucion")

    # -----------------------------------------------------------------------
    # Sub-configuraciones V1 (compatibilidad completa)
    # -----------------------------------------------------------------------
    directorios: DirectoriosConfig = Field(default_factory=DirectoriosConfig)
    nei: NEIWeights = Field(default_factory=NEIWeights)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    embedding: EmbeddingConfig = Field(default_factory=EmbeddingConfig)
    api: APIConfig = Field(default_factory=APIConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    mercado: MercadoConfig = Field(default_factory=MercadoConfig)

    # -----------------------------------------------------------------------
    # NUEVO V2: Sub-configuraciones adicionales
    # -----------------------------------------------------------------------
    veo_core: VeoCoreConfig = Field(default_factory=VeoCoreConfig)
    operations: OperationsConfig = Field(default_factory=OperationsConfig)
    hermes_commander: HermesCommanderConfig = Field(default_factory=HermesCommanderConfig)
    governance: GovernanceConfig = Field(default_factory=GovernanceConfig)

    @field_validator("min_confidence", mode="before")
    @classmethod
    def _parse_float(cls, v: Any) -> float:
        if v is None or v == "":
            return 0.0
        if isinstance(v, str):
            v = v.strip()
            if v.lower() in ("null", "none", "nil"):
                return 0.0
        return float(v)

    @field_validator("min_evidence", mode="before")
    @classmethod
    def _parse_int(cls, v: Any) -> int:
        if v is None or v == "":
            return 0
        if isinstance(v, str):
            v = v.strip()
            if v.lower() in ("null", "none", "nil"):
                return 0
        return int(v)

    # -----------------------------------------------------------------------
    # Propiedades V1 (compatibilidad completa)
    # -----------------------------------------------------------------------

    @property
    def ruta_base(self) -> Path:
        """Ruta absoluta al directorio base del sistema."""
        return Path(self.directorios.base).resolve()

    @property
    def ruta_datos(self) -> Path:
        """Ruta absoluta al directorio de datos."""
        return self.ruta_base / self.directorios.datos

    @property
    def ruta_journal(self) -> Path:
        """Ruta absoluta al directorio de journal."""
        return self.ruta_base / self.directorios.journal

    @property
    def ruta_cache(self) -> Path:
        """Ruta absoluta al directorio de cache."""
        return self.ruta_base / self.directorios.cache

    @property
    def ruta_salida(self) -> Path:
        """Ruta absoluta al directorio de salidas."""
        return self.ruta_base / self.directorios.salida

    @property
    def ruta_db(self) -> Path:
        """Ruta absoluta a la base de datos SQLite."""
        return self.ruta_datos / "sois.db"

    @property
    def ruta_log(self) -> Path:
        """Ruta absoluta al archivo de log."""
        return self.ruta_journal / self.logging.archivo

    @property
    def pesos_nei_normalizados(self) -> dict[str, float]:
        """Devuelve los pesos NEI escalados a suma 1.0."""
        return self.nei.normalizar()

    # -----------------------------------------------------------------------
    # NUEVO V2: Propiedades adicionales
    # -----------------------------------------------------------------------

    @property
    def ruta_logs(self) -> Path:
        """Ruta absoluta al directorio de logs (nuevo en V2)."""
        return self.ruta_base / "logs"

    @property
    def ruta_backups(self) -> Path:
        """Ruta absoluta al directorio de backups (nuevo en V2)."""
        return self.ruta_base / "backups"

    @property
    def ruta_metrics(self) -> Path:
        """Ruta absoluta al directorio de metricas (nuevo en V2)."""
        return self.ruta_base / "metrics"

    @property
    def is_produccion(self) -> bool:
        """True si el entorno es produccion."""
        return self.ambiente.lower() == "prod"

    @property
    def is_desarrollo(self) -> bool:
        """True si el entorno es desarrollo."""
        return self.ambiente.lower() == "dev"

    # -----------------------------------------------------------------------
    # Metodos
    # -----------------------------------------------------------------------

    def crear_directorios(self) -> None:
        """
        Crea todos los directorios necesarios si no existen.
        Incluye los nuevos directorios V2 (logs, backups, metrics).

        Seguro para ejecutar multiples veces (mkdir con exist_ok).
        """
        for ruta in (
            self.ruta_datos,
            self.ruta_journal,
            self.ruta_cache,
            self.ruta_salida,
            self.ruta_logs,
            self.ruta_backups,
            self.ruta_metrics,
        ):
            try:
                ruta.mkdir(parents=True, exist_ok=True)
            except OSError as exc:
                raise RuntimeError(
                    f"No se pudo crear el directorio {ruta}: {exc}"
                ) from exc

    def dump_json(self) -> str:
        """Exporta la configuracion completa como JSON (sin secretos)."""
        datos = self.model_dump(exclude={"llm": {"api_key"}})
        return json.dumps(datos, indent=2, ensure_ascii=False, default=str)

    def resumen_v2(self) -> dict[str, Any]:
        """
        Devuelve un resumen de la configuracion V2.

        Returns:
            Diccionario con las configuraciones clave de cada modulo V2.
        """
        return {
            "ambiente": self.ambiente,
            "veo_core": {
                "ciclos_intervalos_seg": self.veo_core.ciclos_intervalos,
                "max_concurrent_tasks": self.veo_core.max_concurrent_tasks,
                "confidence_threshold": self.veo_core.default_confidence_threshold,
            },
            "operations": {
                "log_level": self.operations.log_level,
                "backup_interval_hours": self.operations.backup_interval_hours,
                "metrics_retention_days": self.operations.metrics_retention_days,
                "health_check_interval": self.operations.health_check_interval,
            },
            "hermes_commander": {
                "max_queue_size": self.hermes_commander.max_queue_size,
                "request_timeout_seconds": self.hermes_commander.request_timeout_seconds,
                "default_priority": self.hermes_commander.default_priority,
            },
            "governance": {
                "leyes_activas": self.governance.leyes_activas_count(),
                "todas_activas": self.governance.todas_activas(),
                "detalle": self.governance.verificar_leyes(),
            },
        }


# ---------------------------------------------------------------------------
# Singleton de configuracion
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def get_config() -> Settings:
    """
    Devuelve una instancia cacheada de la configuracion.

    La cache con lru_cache garantiza que la configuracion se cargue
    una sola vez por proceso, evitando lecturas repetidas de env vars.

    Si necesitas recargar la configuracion en runtime:
        >>> get_config.cache_clear()
        >>> cfg = get_config()
    """
    return Settings()


# Instancia global de conveniencia (se carga al importar, pero es lazy
# gracias al cache). En tests se recomienda usar get_config() directamente
# para poder hacer cache_clear().
_config: Settings | None = None


def get_config_lazy() -> Settings:
    """Acceso lazy a la configuracion global."""
    global _config
    if _config is None:
        _config = get_config()
    return _config
