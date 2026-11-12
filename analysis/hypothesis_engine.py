# -*- coding: utf-8 -*-
"""
hypothesis_engine.py — Motor de Hipótesis del VEO con NEI auto-aprendido.

SOIS = Sistema Operativo para Intuición Social.
Filosofía: "¿Qué está cambiando? ¿Qué relaciones nuevas están apareciendo?"

Este módulo genera hipótesis interpretables a partir de clusters semánticos,
las puntúa mediante el Narrative Emergence Index (NEI) compuesto por 6 métricas,
y aprende los pesos óptimos del NEI mediante descenso de gradiente simple a
partir del historial de aciertos y fallos.
"""

from __future__ import annotations

import json
import math
import re
import sqlite3
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np
from numpy.linalg import norm

# ---------------------------------------------------------------------------
# Estructuras de datos
# ---------------------------------------------------------------------------

@dataclass
class Evidencia:
    """Una evidencia que respalda o contradice una hipótesis."""

    fuente: str
    contenido: str
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    peso: float = 1.0  # +1.0 = respalda, -1.0 = contradice
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Hipotesis:
    """Hipótesis interpretable generada por el motor."""

    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    texto: str = ""
    nivel_confianza: float = 0.0  # 0.0 — 1.0
    nivel_riesgo: float = 0.0  # 0.0 — 1.0
    evidencias: List[Evidencia] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    nei: float = 0.0  # Narrative Emergence Index
    estado: str = "activa"  # activa | archivada | confirmada | refutada
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    cascada_detectada: bool = False
    historial_nei: List[Tuple[str, float]] = field(default_factory=list)
    # Metadatos para aprendizaje: True = la hipótesis resultó útil/acertada
    feedback_confirmado: Optional[bool] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serializa la hipótesis a diccionario."""
        d = asdict(self)
        # Las evidencias ya son dataclasses, asdict las maneja recursivamente
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Hipotesis":
        """Deserializa una hipótesis desde diccionario."""
        # Reconstruir evidencias
        evs = [Evidencia(**e) for e in data.get("evidencias", [])]
        hist_nei = [tuple(t) for t in data.get("historial_nei", [])]
        campos = {k: v for k, v in data.items() if k not in ("evidencias", "historial_nei")}
        campos["evidencias"] = evs
        campos["historial_nei"] = hist_nei
        return cls(**campos)


# ---------------------------------------------------------------------------
# Motor de Hipótesis
# ---------------------------------------------------------------------------

class MotorHipotesis:
    """Motor de hipótesis con NEI auto-aprendido.

    Parameters
    ----------
    db :
        Conexión a base de datos SQLite (u objeto compatible).
    config : Dict[str, Any]
        Configuración del motor. Claves reconocidas:
        - ``llm_api_url`` : URL del endpoint del LLM.
        - ``llm_api_key`` : API key para autenticación.
        - ``llm_model`` : Nombre del modelo a usar.
        - ``pesos_nei`` : List[float] con 6 pesos iniciales (opcional).
        - ``tasa_aprendizaje`` : float, tasa para gradient descent (default 0.01).
        - ``umbral_cascada`` : float, NEI mínimo para considerar cascada (default 0.7).
    logger :
        Objeto logger compatible con logging.Logger.

    Attributes
    ----------
    pesos_nei : np.ndarray
        Vector de 6 pesos que suman 1.0 para el cálculo del NEI.
    historial_nei : List[Dict]
        Registro histórico de métricas NEI con resultado de acierto/fallo.
    """

    # Nombres de las 6 métricas del NEI
    _NOMBRES_METRICAS = ["FR", "GR", "DV", "NV", "EM", "ST"]

    def __init__(self, db: sqlite3.Connection = None, config: Dict[str, Any] = None, logger: Any = None) -> None:
        # Defaults para instanciacion sin parametros
        if db is None:
            db = sqlite3.connect(":memory:")
            db.row_factory = sqlite3.Row
        if config is None:
            config = {}
        if logger is None:
            class _MockLogger:
                def info(self, *a, **k): pass
                def warning(self, *a, **k): pass
                def error(self, *a, **k): pass
                def debug(self, *a, **k): pass
            logger = _MockLogger()
        self.db = db
        self.config = config
        self.logger = logger

        # Pesos del NEI: w1..w6 — se normalizan para sumar 1.0
        pesos_raw: List[float] = config.get("pesos_nei", [0.20, 0.20, 0.15, 0.20, 0.15, 0.10])
        self.pesos_nei: np.ndarray = self._normalizar_pesos(np.array(pesos_raw, dtype=np.float64))

        # Hiperparámetros de aprendizaje
        self.tasa_aprendizaje: float = config.get("tasa_aprendizaje", 0.01)
        self.umbral_cascada: float = config.get("umbral_cascada", 0.7)

        # Almacén en memoria de hipótesis activas (id -> Hipotesis)
        self._hipotesis_activas: Dict[str, Hipotesis] = {}

        # Historial de NEI con etiqueta de acierto/fallo para aprendizaje
        # Cada entrada: {"metricas": [FR, GR, DV, NV, EM, ST], "acierto": 1|0}
        self.historial_nei: List[Dict[str, Any]] = []

        # Cargar hipótesis previas desde la base de datos
        self._cargar_hipotesis_persistidas()

        self.logger.info(
            "[MotorHipotesis] Inicializado — pesos_NEI=%s",
            np.round(self.pesos_nei, 4).tolist(),
        )

    # ------------------------------------------------------------------
    # Utilidades internas
    # ------------------------------------------------------------------

    @staticmethod
    def _normalizar_pesos(w: np.ndarray) -> np.ndarray:
        """Normaliza un vector de pesos para que sumen exactamente 1.0."""
        s = w.sum()
        if s == 0:
            return np.ones_like(w) / len(w)
        return w / s

    def _now_iso(self) -> str:
        """Timestamp UTC en formato ISO."""
        return datetime.now(timezone.utc).isoformat()

    def _cargar_hipotesis_persistidas(self) -> None:
        """Carga hipótesis con estado 'activa' desde SQLite al diccionario en memoria."""
        try:
            cursor = self.db.execute(
                "SELECT id, data_json FROM hipotesis WHERE estado = 'activa'"
            )
            for row in cursor.fetchall():
                data = json.loads(row["data_json"])
                hip = Hipotesis.from_dict(data)
                self._hipotesis_activas[hip.id] = hip
            self.logger.info(
                "[MotorHipotesis] %d hipótesis activas cargadas desde DB",
                len(self._hipotesis_activas),
            )
        except sqlite3.OperationalError:
            # La tabla puede no existir aún; se creará en _persistir_hipotesis
            self.logger.debug("[MotorHipotesis] Tabla hipotesis no existe aún, iniciando vacía")

    def _persistir_hipotesis(self, hip: Hipotesis) -> None:
        """Guarda o actualiza una hipótesis en la tabla SQLite."""
        try:
            self.db.execute(
                """
                CREATE TABLE IF NOT EXISTS hipotesis (
                    id TEXT PRIMARY KEY,
                    estado TEXT,
                    updated_at TEXT,
                    data_json TEXT
                )
                """
            )
            self.db.execute(
                """
                INSERT INTO hipotesis (id, estado, updated_at, data_json)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    estado = excluded.estado,
                    updated_at = excluded.updated_at,
                    data_json = excluded.data_json
                """,
                (hip.id, hip.estado, hip.updated_at, json.dumps(hip.to_dict(), ensure_ascii=False)),
            )
            self.db.commit()
        except Exception as exc:
            self.logger.error("[MotorHipotesis] Error persistiendo hipótesis %s: %s", hip.id, exc)

    def _extraer_tags(self, texto: str) -> List[str]:
        """Extrae tags automáticamente del texto mediante regex y heurísticas.

        Combina extracción de hashtags, menciones de entidades capitalizadas
        y bigramas relevantes.
        """
        tags: List[str] = []

        # Hashtags explícitos
        tags.extend(re.findall(r"#(\w+)", texto))

        # Menciones @usuario
        tags.extend(re.findall(r"@(\w+)", texto))

        # Entidades capitalizadas (n-gramas de 1-3 palabras)
        palabras = re.findall(r"[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?:\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+){0,2}", texto)
        tags.extend([p.strip() for p in palabras if len(p.strip()) > 2])

        # Normalizar: minúsculas, sin duplicados, máximo 10 tags
        tags = list({t.lower() for t in tags})
        return tags[:10]

    def _embedding_texto(self, texto: str) -> np.ndarray:
        """Obtiene el embedding de un texto usando sentence-transformers.

        Si no está disponible el modelo configurado, devuelve un vector nulo.
        """
        try:
            from sentence_transformers import SentenceTransformer

            modelo_nombre = self.config.get("embedding_model", "all-MiniLM-L6-v2")
            if not hasattr(self, "_modelo_embedding"):
                self._modelo_embedding = SentenceTransformer(modelo_nombre)
            emb = self._modelo_embedding.encode(texto, convert_to_numpy=True, show_progress_bar=False)
            return emb  # type: ignore[no-any-return]
        except Exception as exc:
            self.logger.warning("[MotorHipotesis] Embedding falló para texto: %s", exc)
            return np.zeros(384, dtype=np.float64)

    # ------------------------------------------------------------------
    # Prompt y parsing del LLM
    # ------------------------------------------------------------------

    def _prompt_generacion(self, contexto: str) -> str:
        """Construye el prompt para el LLM a partir del contexto narrativo.

        El prompt instruye al modelo para que genere hipótesis estructuradas
        sobre qué está cambiando en la narrativa, NO predicciones del futuro.
        """
        prompt = f"""Eres el núcleo analítico del VEO, un sistema que detecta cambios emergentes en narrativas de internet. Tu filosofía es: "¿Qué está cambiando? ¿Qué relaciones nuevas están apareciendo?" NO predices el futuro. Observas patrones emergentes en el presente.

CONTEXTO NARRATIVO RECOPILADO:
---
{contexto}
---

INSTRUCCIONES:
1. Analiza el contexto anterior y genera entre 3 y 6 hipótesis sobre patrones emergentes, cambios de narrativa o relaciones nuevas que estás detectando.
2. Cada hipótesis debe ser una afirmación clara, específica y verificable sobre el presente o un cambio en curso.
3. NO hagas predicciones del futuro. Enfócate en: "qué está cambiando ahora", "qué nuevo patrón aparece", "qué relación inesperada emerge".
4. Asigna un nivel de confianza inicial (0.0 a 1.0) basado en la cantidad y calidad de evidencias.
5. Asigna un nivel de riesgo (0.0 a 1.0): qué tan problemático sería ignorar esta hipótesis si resulta cierta.
6. Extrae tags relevantes para cada hipótesis.

FORMATO DE RESPUESTA (JSON estricto):
{{
  "hipotesis": [
    {{
      "texto": "string - descripción clara de la hipótesis emergente",
      "nivel_confianza": float 0.0-1.0,
      "nivel_riesgo": float 0.0-1.0,
      "tags": ["tag1", "tag2"],
      "evidencias": [
        {{"fuente": "cluster_X", "contenido": "resumen de evidencia", "peso": 1.0}}
      ]
    }}
  ]
}}

Responde ÚNICAMENTE con el JSON válido, sin markdown, sin explicaciones adicionales."""
        return prompt

    def _parsear_respuesta_llm(self, respuesta: str) -> List[Hipotesis]:
        """Parsea la respuesta del LLM y construye objetos Hipotesis.

        Realiza limpieza de markdown, manejo de errores de parseo,
        y validación de campos obligatorios.
        """
        hipotesis: List[Hipotesis] = []

        if not respuesta or not respuesta.strip():
            self.logger.warning("[MotorHipotesis] Respuesta del LLM vacía")
            return hipotesis

        # Limpiar markdown ```json ... ```
        texto_limpio = respuesta.strip()
        if texto_limpio.startswith("```"):
            texto_limpio = re.sub(r"^```(?:json)?\s*", "", texto_limpio)
            texto_limpio = re.sub(r"\s*```$", "", texto_limpio)

        try:
            data = json.loads(texto_limpio)
        except json.JSONDecodeError as exc:
            self.logger.error("[MotorHipotesis] JSON inválido del LLM: %s", exc)
            # Intento de recuperación: buscar JSON embebido
            match = re.search(r"\{.*\}", texto_limpio, re.DOTALL)
            if match:
                try:
                    data = json.loads(match.group())
                except json.JSONDecodeError:
                    return hipotesis
            else:
                return hipotesis

        items = data.get("hipotesis", [])
        if not isinstance(items, list):
            self.logger.warning("[MotorHipotesis] 'hipotesis' no es lista en respuesta LLM")
            return hipotesis

        for item in items:
            try:
                texto = item.get("texto", "").strip()
                if not texto:
                    continue

                h = Hipotesis(
                    texto=texto,
                    nivel_confianza=float(item.get("nivel_confianza", 0.5)),
                    nivel_riesgo=float(item.get("nivel_riesgo", 0.3)),
                    tags=item.get("tags", self._extraer_tags(texto)),
                )

                # Evidencias
                for ev_data in item.get("evidencias", []):
                    h.evidencias.append(
                        Evidencia(
                            fuente=ev_data.get("fuente", "desconocida"),
                            contenido=ev_data.get("contenido", ""),
                            peso=float(ev_data.get("peso", 1.0)),
                        )
                    )

                hipotesis.append(h)
            except (ValueError, TypeError) as exc:
                self.logger.warning("[MotorHipotesis] Error parseando item de hipótesis: %s", exc)
                continue

        self.logger.info("[MotorHipotesis] %d hipótesis parseadas del LLM", len(hipotesis))
        return hipotesis

    # ------------------------------------------------------------------
    # NEI — Narrative Emergence Index
    # ------------------------------------------------------------------

    def calcular_nei(self, metricas: Dict[str, float]) -> float:
        """Calcula el Narrative Emergence Index (NEI) ponderado.

        NEI = w1·FR + w2·GR + w3·DV + w4·NV + w5·EM + w6·ST

        Parameters
        ----------
        metricas : Dict[str, float]
            Diccionario con las 6 métricas normalizadas [0, 1]:
            - ``FR`` : Frecuencia Relativa (normalizada).
            - ``GR`` : Growth Rate, tasa de crecimiento (derivada primera).
            - ``DV`` : Diversidad, entropía de Shannon sobre fuentes.
            - ``NV`` : Novedad, 1 - max(similaridad con historial).
            - ``EM`` : Emocional, intensidad emocional promedio.
            - ``ST`` : Sentimiento Trend, cambio en polaridad.

        Returns
        -------
        float
            Valor del NEI en [0, 1].
        """
        valores = np.array(
            [
                metricas.get("FR", 0.0),
                metricas.get("GR", 0.0),
                metricas.get("DV", 0.0),
                metricas.get("NV", 0.0),
                metricas.get("EM", 0.0),
                metricas.get("ST", 0.0),
            ],
            dtype=np.float64,
        )
        # Clip a [0, 1] por seguridad
        valores = np.clip(valores, 0.0, 1.0)
        nei = float(np.dot(self.pesos_nei, valores))
        return float(np.clip(nei, 0.0, 1.0))

    def aprender_pesos(self, historial: List[Dict[str, Any]]) -> None:
        """Ajusta los 6 pesos del NEI mediante descenso de gradiente simple.

        Cada entrada del historial debe contener:
        - ``metricas`` : Dict[str, float] con las 6 métricas.
        - ``acierto``  : int (1 = la hipótesis fue útil/acertada, 0 = falló).

        La función minimiza el error cuadrático entre NEI predicho y la
        etiqueta de acierto, manteniendo la restricción de que los pesos
        sumen 1.0 mediante re-normalización después de cada paso.

        Parameters
        ----------
        historial : List[Dict]
            Historial de métricas con resultado de acierto/fallo.
        """
        if not historial:
            self.logger.debug("[MotorHipotesis] Historial vacío, no se ajustan pesos")
            return

        self.historial_nei.extend(historial)

        # Preparar matrices
        X: List[np.ndarray] = []
        y: List[float] = []
        for entrada in historial:
            m = entrada.get("metricas", {})
            vec = np.array(
                [m.get(k, 0.0) for k in self._NOMBRES_METRICAS],
                dtype=np.float64,
            )
            X.append(vec)
            y.append(float(entrada.get("acierto", 0.0)))

        X_mat = np.vstack(X)  # shape (N, 6)
        y_vec = np.array(y, dtype=np.float64)  # shape (N,)

        # Descenso de gradiente durante varias épocas
        pesos = self.pesos_nei.copy()
        lr = self.tasa_aprendizaje
        epochs = min(100, max(20, len(historial) * 5))

        for epoch in range(epochs):
            # Predicción: NEI = w · x
            pred = X_mat @ pesos  # shape (N,)
            # Error
            error = pred - y_vec  # shape (N,)
            # Gradiente: dL/dw = (2/N) * X^T · error
            grad = (2.0 / len(y_vec)) * (X_mat.T @ error)  # shape (6,)
            # Actualización
            pesos_nuevos = pesos - lr * grad
            # Proyección: re-normalizar para que sumen 1.0 y sean >= 0
            pesos_nuevos = np.maximum(pesos_nuevos, 1e-6)
            pesos_nuevos = self._normalizar_pesos(pesos_nuevos)
            pesos = pesos_nuevos

        self.pesos_nei = pesos
        self.logger.info(
            "[MotorHipotesis] Pesos NEI ajustados (épocas=%d) → %s",
            epochs,
            np.round(self.pesos_nei, 4).tolist(),
        )

    # ------------------------------------------------------------------
    # Generación de hipótesis
    # ------------------------------------------------------------------

    def generar_hipotesis(
        self,
        clusters: List[Dict[str, Any]],
        texto_contexto: str,
    ) -> List[Hipotesis]:
        """Genera hipótesis a partir de clusters semánticos usando un LLM.

        Parameters
        ----------
        clusters : List[Dict]
            Clusters semánticos detectados. Cada cluster debe tener al menos
            ``topic``, ``size`` y ``samples``.
        texto_contexto : str
            Texto de contexto adicional que resume la situación narrativa.

        Returns
        -------
        List[Hipotesis]
            Lista de hipótesis generadas, con NEI calculado y persistidas.
        """
        self.logger.info("[MotorHipotesis] Generando hipótesis para %d clusters", len(clusters))

        # Construir contexto enriquecido
        contexto_parts: List[str] = []
        contexto_parts.append(f"RESUMEN DEL CONTEXTO:\n{texto_contexto}\n")
        contexto_parts.append("CLUSTERS SEMÁNTICOS DETECTADOS:")
        for i, cluster in enumerate(clusters, 1):
            contexto_parts.append(
                f"\nCluster {i}: {cluster.get('topic', 'sin-título')}"
                f" (tamaño={cluster.get('size', 0)}, "
                f"coherencia={cluster.get('coherence', 0):.3f})"
            )
            muestras = cluster.get("samples", [])[:5]
            for muestra in muestras:
                contexto_parts.append(f"  - {str(muestra)[:200]}")

        contexto_completo = "\n".join(contexto_parts)

        # Obtener respuesta del LLM
        prompt = self._prompt_generacion(contexto_completo)
        respuesta_llm = self._llm_call(prompt)

        # Parsear hipótesis
        hipotesis = self._parsear_respuesta_llm(respuesta_llm)

        # Calcular NEI para cada hipótesis y persistir
        for hip in hipotesis:
            # Extraer métricas de las evidencias disponibles
            metricas = self._extraer_metricas_de_evidencias(hip.evidencias, clusters)
            hip.nei = self.calcular_nei(metricas)
            hip.historial_nei.append((self._now_iso(), hip.nei))

            # Tags automáticos si el LLM no proporcionó suficientes
            if len(hip.tags) < 2:
                hip.tags = self._extraer_tags(hip.texto)

            # Guardar en memoria y persistir
            self._hipotesis_activas[hip.id] = hip
            self._persistir_hipotesis(hip)

        self.logger.info(
            "[MotorHipotesis] %d hipótesis generadas y persistidas", len(hipotesis)
        )
        return hipotesis

    def _extraer_metricas_de_evidencias(
        self, evidencias: List[Evidencia], clusters: List[Dict[str, Any]]
    ) -> Dict[str, float]:
        """Extrae las 6 métricas del NEI a partir de evidencias y clusters.

        Cuando no hay datos suficientes, se usan heurísticas basadas en
        la cantidad y diversidad de evidencias.
        """
        n_evs = len(evidencias)
        if n_evs == 0:
            return {"FR": 0.0, "GR": 0.0, "DV": 0.0, "NV": 0.5, "EM": 0.3, "ST": 0.0}

        # FR: proporcional al número de evidencias (saturado a 1.0)
        fr = min(n_evs / 10.0, 1.0)

        # GR: si hay timestamps, calcular tendencia; si no, estimar por diversidad
        timestamps = []
        for ev in evidencias:
            try:
                ts = datetime.fromisoformat(ev.timestamp)
                timestamps.append(ts)
            except (ValueError, TypeError):
                continue
        if len(timestamps) >= 2:
            timestamps.sort()
            deltas = [(timestamps[i + 1] - timestamps[i]).total_seconds() for i in range(len(timestamps) - 1)]
            if deltas:
                # Mayor frecuencia = mayor GR
                gr = min(1.0, 3600.0 / (sum(deltas) / len(deltas) + 1.0))
            else:
                gr = 0.3
        else:
            gr = 0.3

        # DV: entropía de Shannon sobre fuentes
        fuentes = [ev.fuente for ev in evidencias]
        if fuentes:
            unicas, counts = np.unique(fuentes, return_counts=True)
            probs = counts / counts.sum()
            dv = -np.sum(probs * np.log2(probs + 1e-12)) / np.log2(max(len(unicas), 2))
            dv = float(np.clip(dv, 0.0, 1.0))
        else:
            dv = 0.0

        # NV: novedad (sin historial, valor neutro)
        nv = 0.5

        # EM: intensidad emocional estimada por palabras en mayúsculas y signos
        em_total = 0.0
        for ev in evidencias:
            txt = ev.contenido
            mayusculas = sum(1 for c in txt if c.isupper()) / max(len(txt), 1)
            signos = txt.count("!") + txt.count("?")
            em_total += min(1.0, mayusculas * 2 + signos * 0.1)
        em = em_total / n_evs if n_evs > 0 else 0.3

        # ST: cambio en polaridad (estimado por palabras positivas/negativas)
        positivas = {"bueno", "excelente", "positivo", "crecimiento", "oportunidad", "esperanza", "progreso", "nuevo", "mejora"}
        negativas = {"malo", "terrible", "negativo", "crisis", "peligro", "miedo", "destrucción", "caída", "pérdida", "riesgo"}
        st_total = 0.0
        for ev in evidencias:
            txt_lower = ev.contenido.lower()
            p = sum(1 for w in positivas if w in txt_lower)
            neg = sum(1 for w in negativas if w in txt_lower)
            total = p + neg
            if total > 0:
                st_total += abs(p - neg) / total
        st = st_total / n_evs if n_evs > 0 else 0.0

        return {
            "FR": float(fr),
            "GR": float(gr),
            "DV": float(dv),
            "NV": float(nv),
            "EM": float(em),
            "ST": float(st),
        }

    def _llm_call(self, prompt: str) -> str:
        """Realiza la llamada al LLM configurado.

        Soporta llamada vía HTTP a API (OpenAI-compatible) o una implementación
        de fallback que usa reglas heurísticas si no hay API disponible.
        """
        api_url = self.config.get("llm_api_url", "")
        api_key = self.config.get("llm_api_key", "")

        if not api_url:
            self.logger.debug("[MotorHipotesis] Sin API LLM configurada, usando fallback heurístico")
            return self._llm_fallback(prompt)

        try:
            import urllib.request
            import urllib.error

            payload = json.dumps(
                {
                    "model": self.config.get("llm_model", "gpt-4o-mini"),
                    "messages": [
                        {"role": "system", "content": "Eres un analista de narrativas emergente."},
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.7,
                    "max_tokens": 2000,
                }
            ).encode("utf-8")

            req = urllib.request.Request(
                api_url,
                data=payload,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {api_key}",
                },
                method="POST",
            )

            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                choices = data.get("choices", [])
                if choices:
                    return choices[0].get("message", {}).get("content", "")
                return ""

        except Exception as exc:
            self.logger.warning("[MotorHipotesis] Error llamando LLM API: %s. Usando fallback.", exc)
            return self._llm_fallback(prompt)

    def _llm_fallback(self, prompt: str) -> str:
        """Fallback heurístico cuando no hay LLM disponible.

        Extrae patrones del contexto y genera hipótesis estructuradas
        mediante reglas, sin llamada externa.
        """
        # Extraer líneas del prompt que contienen muestras de clusters
        lineas = prompt.split("\n")
        muestras: List[str] = []
        for linea in lineas:
            if linea.strip().startswith("-") and len(linea) > 10:
                muestras.append(linea.strip()[2:].strip())

        if not muestras:
            muestras = ["patrón narrativo detectado en fuentes múltiples"]

        # Generar hipótesis heurísticas básicas
        hip_items: List[Dict[str, Any]] = []

        # Hipótesis 1: frecuencia creciente
        hip_items.append({
            "texto": f"Se detecta un aumento significativo en la frecuencia de menciones relacionadas con: {muestras[0][:80]}...",
            "nivel_confianza": 0.6,
            "nivel_riesgo": 0.4,
            "tags": ["frecuencia", "tendencia"],
            "evidencias": [{"fuente": "cluster_1", "contenido": muestras[0][:200], "peso": 1.0}],
        })

        # Hipótesis 2: diversidad de fuentes
        if len(muestras) >= 2:
            hip_items.append({
                "texto": f"El tema está siendo discutido en fuentes diversas, sugiriendo una expansión narrativa más allá de su nicho original: {muestras[1][:60]}...",
                "nivel_confianza": 0.55,
                "nivel_riesgo": 0.5,
                "tags": ["diversidad", "expansión"],
                "evidencias": [{"fuente": "cluster_2", "contenido": muestras[1][:200], "peso": 1.0}],
            })

        # Hipótesis 3: patrón emergente
        hip_items.append({
            "texto": f"Se observa la formación de un nuevo patrón de discurso que conecta múltiples sub-temas de manera inesperada en el conjunto de muestras analizadas.",
            "nivel_confianza": 0.45,
            "nivel_riesgo": 0.6,
            "tags": ["patrón_emergente", "conexión"],
            "evidencias": [{"fuente": "clusters_agregados", "contenido": f"Total de muestras analizadas: {len(muestras)}", "peso": 0.8}],
        })

        return json.dumps({"hipotesis": hip_items}, ensure_ascii=False)

    # ------------------------------------------------------------------
    # Actualización y ciclo de vida
    # ------------------------------------------------------------------

    def actualizar_confianza(self, hipotesis_id: str, nuevo_dato: Dict[str, Any]) -> None:
        """Actualiza la confianza de una hipótesis cuando llega nueva evidencia.

        Parameters
        ----------
        hipotesis_id : str
            Identificador de la hipótesis a actualizar.
        nuevo_dato : Dict
            Nueva evidencia. Debe contener al menos ``fuente`` y ``contenido``.
            Opcionalmente: ``peso`` (+1 respalda, -1 contradice),
            ``metricas`` (para recalcular NEI).
        """
        hip = self._hipotesis_activas.get(hipotesis_id)
        if hip is None:
            self.logger.warning(
                "[MotorHipotesis] Hipótesis %s no encontrada para actualizar", hipotesis_id
            )
            return

        # Crear nueva evidencia
        nueva_ev = Evidencia(
            fuente=nuevo_dato.get("fuente", "desconocida"),
            contenido=nuevo_dato.get("contenido", ""),
            peso=float(nuevo_dato.get("peso", 1.0)),
            metadata=nuevo_dato.get("metadata", {}),
        )
        hip.evidencias.append(nueva_ev)

        # Recalcular NEI si vienen métricas nuevas
        metricas_nuevas = nuevo_dato.get("metricas")
        if metricas_nuevas:
            hip.nei = self.calcular_nei(metricas_nuevas)
        else:
            # Ajuste Bayesiano simple de confianza con nueva evidencia
            peso_total = sum(ev.peso for ev in hip.evidencias)
            n_pos = sum(1 for ev in hip.evidencias if ev.peso > 0)
            n_neg = sum(1 for ev in hip.evidencias if ev.peso < 0)
            n_total = n_pos + n_neg
            if n_total > 0:
                hip.nivel_confianza = float(np.clip(n_pos / n_total, 0.0, 1.0))

        hip.updated_at = self._now_iso()
        hip.historial_nei.append((hip.updated_at, hip.nei))

        self._persistir_hipotesis(hip)
        self.logger.info(
            "[MotorHipotesis] Hipótesis %s actualizada: confianza=%.3f, NEI=%.3f, evidencias=%d",
            hipotesis_id,
            hip.nivel_confianza,
            hip.nei,
            len(hip.evidencias),
        )

    def detectar_cascada(self, umbral: float = 0.7) -> List[Hipotesis]:
        """Detecta hipótesis que están ganando tracción rápidamente (cascada).

        Una cascada se define como un crecimiento sostenido del NEI por
        encima del umbral durante al menos dos mediciones consecutivas.

        Parameters
        ----------
        umbral : float
            NEI mínimo para considerar cascada (default 0.7).

        Returns
        -------
        List[Hipotesis]
            Hipótesis en estado de cascada, ordenadas por NEI descendente.
        """
        cascadas: List[Hipotesis] = []

        for hip in self._hipotesis_activas.values():
            if hip.estado != "activa":
                continue

            historial = hip.historial_nei
            if len(historial) < 2:
                continue

            # Verificar si el NEI está por encima del umbral y creciendo
            ultimos_nei = [nei for _, nei in historial[-3:]]
            if len(ultimos_nei) >= 2:
                creciendo = all(
                    ultimos_nei[i] <= ultimos_nei[i + 1]
                    for i in range(len(ultimos_nei) - 1)
                )
                if ultimos_nei[-1] >= umbral and creciendo:
                    hip.cascada_detectada = True
                    cascadas.append(hip)
                else:
                    hip.cascada_detectada = False

        cascadas.sort(key=lambda h: h.nei, reverse=True)
        self.logger.info(
            "[MotorHipotesis] Cascadas detectadas: %d (umbral=%.2f)",
            len(cascadas),
            umbral,
        )
        return cascadas

    def archivar_caducas(self, dias: int = 7) -> List[str]:
        """Archiva hipótesis sin actividad reciente.

        Parameters
        ----------
        dias : int
            Número de días sin actividad para considerar caduca (default 7).

        Returns
        -------
        List[str]
            IDs de hipótesis archivadas.
        """
        umbral_tiempo = datetime.now(timezone.utc) - timedelta(days=dias)
        archivadas: List[str] = []

        for hip_id, hip in list(self._hipotesis_activas.items()):
            try:
                ultima_act = datetime.fromisoformat(hip.updated_at)
            except (ValueError, TypeError):
                continue

            if ultima_act < umbral_tiempo and hip.estado == "activa":
                hip.estado = "archivada"
                hip.updated_at = self._now_iso()
                self._persistir_hipotesis(hip)
                del self._hipotesis_activas[hip_id]
                archivadas.append(hip_id)

        self.logger.info(
            "[MotorHipotesis] %d hipótesis archivadas por inactividad (> %d días)",
            len(archivadas),
            dias,
        )
        return archivadas

    # ------------------------------------------------------------------
    # Consultas
    # ------------------------------------------------------------------

    def obtener_hipotesis(self, hipotesis_id: str) -> Optional[Hipotesis]:
        """Obtiene una hipótesis por su ID."""
        return self._hipotesis_activas.get(hipotesis_id)

    def listar_activas(self) -> List[Hipotesis]:
        """Lista todas las hipótesis activas ordenadas por NEI descendente."""
        return sorted(
            self._hipotesis_activas.values(),
            key=lambda h: h.nei,
            reverse=True,
        )

    def registrar_feedback(self, hipotesis_id: str, fue_acertada: bool) -> None:
        """Registra feedback humano sobre una hipótesis para el ciclo de aprendizaje.

        Parameters
        ----------
        hipotesis_id : str
            ID de la hipótesis evaluada.
        fue_acertada : bool
            True si la hipótesis resultó útil o acertada, False en caso contrario.
        """
        hip = self._hipotesis_activas.get(hipotesis_id)
        if hip is None:
            self.logger.warning(
                "[MotorHipotesis] No se encontró hipótesis %s para feedback", hipotesis_id
            )
            return

        hip.feedback_confirmado = fue_acertada

        # Extraer métricas del historial NEI para entrenamiento
        if hip.historial_nei:
            _, ultimo_nei = hip.historial_nei[-1]
            # Reconstruir métricas proporcionales al NEI
            metricas = {k: float(ultimo_nei) for k in self._NOMBRES_METRICAS}
            self.historial_nei.append({
                "metricas": metricas,
                "acierto": 1 if fue_acertada else 0,
            })

        hip.updated_at = self._now_iso()
        self._persistir_hipotesis(hip)
        self.logger.info(
            "[MotorHipotesis] Feedback registrado para %s: acertada=%s",
            hipotesis_id,
            fue_acertada,
        )

    def resumen(self) -> Dict[str, Any]:
        """Devuelve resumen del estado del motor."""
        return {
            "hipotesis_activas": len(self._hipotesis_activas),
            "hipotesis_cascada": sum(1 for h in self._hipotesis_activas.values() if h.cascada_detectada),
            "pesos_nei": np.round(self.pesos_nei, 4).tolist(),
            "historial_aprendizaje": len(self.historial_nei),
            "metricas_nombres": self._NOMBRES_METRICAS,
        }


# ============================================================================
# VEO v2: Funciones de integracion con hermes_commander / veo_core
# ============================================================================
# NOTA: Estas funciones fueron anadidas en la migracion de VEO v1 a VEO v2.
# Proporcionan observabilidad, auditoria y health-checks sin modificar
# la logica existente del Motor de Hipotesis con NEI.
# ============================================================================

import time as _time

# --- Estado observable del modulo (VEO v2) ---
_engine_execution_count: int = 0
_engine_last_execution_time: float = 0.0
_engine_hypothesis_log: list = []


def get_trust_score() -> float:
    """
    VEO v2: Devuelve el score de confianza del motor de hipotesis.

    Calcula un score basado en la precision historica de las hipotesis
    generadas (confirmadas vs refutadas).

    Returns:
        float: Score de confianza en [0.0, 1.0].
    """
    global _engine_hypothesis_log
    if not _engine_hypothesis_log:
        return 0.7  # Valor por defecto para motor no calibrado

    confirmadas = sum(
        1 for h in _engine_hypothesis_log
        if h.get("estado_final") == "confirmada"
    )
    refutadas = sum(
        1 for h in _engine_hypothesis_log
        if h.get("estado_final") == "refutada"
    )
    total = confirmadas + refutadas
    if total == 0:
        return 0.5

    score = confirmadas / (confirmadas + refutadas * 1.1 + 1)
    return round(min(max(score, 0.0), 1.0), 4)


def get_last_execution_time() -> str:
    """
    VEO v2: Devuelve el timestamp ISO de la ultima generacion de hipotesis.

    Returns:
        str: Timestamp en formato ISO 8601, o cadena vacia si no ha ejecutado.
    """
    global _engine_last_execution_time
    if _engine_last_execution_time == 0.0:
        return ""
    return _time.strftime("%Y-%m-%dT%H:%M:%SZ", _time.gmtime(_engine_last_execution_time))


def get_health_status() -> dict:
    """
    VEO v2: Devuelve el estado de salud del motor de hipotesis.

    Returns:
        dict: {"status": "healthy|degraded|unhealthy", "score": 0-100}
    """
    global _engine_last_execution_time, _engine_hypothesis_log

    score = 100

    # Penalizar inactividad
    if _engine_last_execution_time > 0:
        horas = (_time.time() - _engine_last_execution_time) / 3600
        if horas > 24:
            score -= 25
        elif horas > 12:
            score -= 10

    # Penalizar por baja calidad de hipotesis
    if _engine_hypothesis_log:
        trust = get_trust_score()
        if trust < 0.3:
            score -= 35
        elif trust < 0.5:
            score -= 15

    if _engine_execution_count == 0:
        score -= 10

    score = max(0, min(100, score))

    if score >= 80:
        status = "healthy"
    elif score >= 50:
        status = "degraded"
    else:
        status = "unhealthy"

    return {"status": status, "score": score}


def _log_audit_hypothesis(
    hipotesis_texto: str,
    nei: float,
    nivel_confianza: float,
    estado: str = "activa",
) -> None:
    """
    VEO v2: Registra una entrada de auditoria para cada hipotesis generada.

    Args:
        hipotesis_texto: Texto de la hipotesis.
        nei: Valor del Narrative Emergence Index.
        nivel_confianza: Confianza inicial [0.0, 1.0].
        estado: Estado inicial de la hipotesis.
    """
    global _engine_execution_count, _engine_last_execution_time, _engine_hypothesis_log

    _engine_execution_count += 1
    _engine_last_execution_time = _time.time()

    entry = {
        "timestamp": get_last_execution_time(),
        "hipotesis": hipotesis_texto[:200] if hipotesis_texto else "",
        "nei": round(nei, 4),
        "confianza": round(nivel_confianza, 4),
        "estado": estado,
        "estado_final": None,
    }
    _engine_hypothesis_log.append(entry)

    if len(_engine_hypothesis_log) > 1000:
        _engine_hypothesis_log = _engine_hypothesis_log[-1000:]
