"""
================================================================================
MOTOR CAUSAL - VEO v2.0.5
Análisis de coherencia causal entre eventos e hipótesis.
Integrado en el ciclo de Reasoning para validación post-científica.
================================================================================
"""

import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class RelacionCausal:
    causa: str
    efecto: str
    fuerza: float  # 0.0 - 1.0
    tipo: str  # "directa", "indirecta", "espuria"
    evidencia: List[str]


@dataclass
class HipotesisCausal:
    id: str
    texto: str
    variables: List[str]
    relaciones: List[RelacionCausal]
    coherencia: float  # 0.0 - 1.0
    ciclos_detectados: List[str]


class MotorCausal:
    """
    Motor de análisis causal para VEO.

    Responsabilidades:
    1. Detectar ciclos causales en hipótesis (circularidad lógica)
    2. Evaluar coherencia causal de relaciones propuestas
    3. Identificar variables espurias (correlación != causalidad)
    4. Calcular fuerza de evidencia causal

    Integración: Llamado desde ReasoningCycle._validate_hypotheses
    después de la validación científica para verificar que las
    hipótesis validadas tienen coherencia causal.
    """

    def __init__(self):
        self.version = "2.0.5"
        self.historial: List[HipotesisCausal] = []
        logger.info("[MotorCausal] Inicializado v%s", self.version)

    def analizar(self, hipotesis: Dict[str, Any], contexto: Optional[List[Dict[str, Any]]] = None) -> HipotesisCausal:
        """
        Analiza una hipótesis para detectar problemas causales.

        Args:
            hipotesis: Dict con 'id', 'text', 'confidence', etc.
            contexto: Lista de señales/contexto para validación cruzada

        Returns:
            HipotesisCausal con análisis completo
        """
        try:
            texto = hipotesis.get("text", "")
            variables = self._extraer_variables(texto)

            # Detectar ciclos causales (A->B->A)
            ciclos = self._detectar_ciclos(texto, variables)

            # Evaluar coherencia causal
            coherencia = self._evaluar_coherencia(texto, variables, ciclos)

            # Construir relaciones
            relaciones = self._inferir_relaciones(texto, variables)

            resultado = HipotesisCausal(
                id=hipotesis.get("id", "unknown"),
                texto=texto,
                variables=variables,
                relaciones=relaciones,
                coherencia=coherencia,
                ciclos_detectados=ciclos
            )

            self.historial.append(resultado)
            return resultado

        except Exception as e:
            logger.warning("[MotorCausal] Error en análisis: %s", e)
            # Fallback: devolver resultado neutral
            return HipotesisCausal(
                id=hipotesis.get("id", "unknown"),
                texto=hipotesis.get("text", ""),
                variables=[],
                relaciones=[],
                coherencia=0.5,
                ciclos_detectados=[]
            )

    def _extraer_variables(self, texto: str) -> List[str]:
        """Extrae posibles variables causales del texto usando límites de palabra.

        Extrae sustantivos completos antes y después de verbos causales,
        evitando truncamientos o capturas parciales.
        """
        import re
        variables: set[str] = set()
        text_lower = texto.lower()

        # Verbos causales en español e inglés
        verbos_causales = (
            r'(?:causa|produce|genera|provoca|origina|conduce\s+a|'
            r'leads?\s+to|causes?|results?\s+in)'
        )

        # Patrón con límites de palabra \b: captura palabras completas
        # de 3+ letras, máximo 2 palabras consecutivas por variable.
        patron = re.compile(
            r'\b([a-záéíóúñ]{3,}(?:\s+[a-záéíóúñ]{3,}){0,1})\b'
            r'\s+' + verbos_causales + r'\s+'
            r'\b([a-záéíóúñ]{3,}(?:\s+[a-záéíóúñ]{3,}){0,1})\b',
            re.I
        )

        for match in patron.finditer(texto):
            for grupo in (1, 2):
                v = match.group(grupo).strip().lower()
                # Filtrar conectores y artículos
                stopwords = {'y', 'o', 'el', 'la', 'los', 'las', 'un', 'una',
                             'de', 'en', 'por', 'con', 'que', 'a', 'al', 'del'}
                palabras = [p for p in v.split() if p not in stopwords]
                if palabras:
                    v_limpia = ' '.join(palabras[:2])  # máx 2 palabras significativas
                    if len(v_limpia) >= 3:
                        variables.add(v_limpia)

        # Fallback: si no hay patrones causales, extraer sustantivos del texto
        if not variables:
            palabras = re.findall(r'\b[a-záéíóúñ]{4,}\b', text_lower)
            stopwords_texto = {
                'causa', 'produce', 'genera', 'provoca', 'origina', 'conduce',
                'cambio', 'debido', 'donde', 'cuando', 'entonces', 'porque',
                'como', 'esto', 'esta', 'este', 'estos', 'estas', 'mismo',
                'misma', 'tanto', 'tanta', 'cada', 'todos', 'todas', 'entre',
            }
            for p in palabras:
                if p not in stopwords_texto:
                    variables.add(p)

        return sorted(list(variables))

    def _detectar_ciclos(self, texto: str, variables: List[str]) -> List[str]:
        """Detecta ciclos causales A->B->...->A basado en variables extraídas."""
        ciclos = []
        if len(variables) < 2:
            return ciclos

        import re
        text_lower = texto.lower()

        # Construir grafo causal simple
        grafo: Dict[str, List[str]] = {v: [] for v in variables}
        for v1 in variables:
            for v2 in variables:
                if v1 != v2:
                    # Buscar si v1 causa v2 en el texto
                    patron = re.compile(
                        re.escape(v1) + r'\s+(?:causa|produce|genera|provoca|origina)\s+' + re.escape(v2),
                        re.I
                    )
                    if patron.search(text_lower):
                        grafo[v1].append(v2)

        # Detectar ciclos de longitud 2 y 3
        for v1 in variables:
            for v2 in grafo.get(v1, []):
                if v1 in grafo.get(v2, []):
                    ciclos.append(f"Ciclo bidireccional: {v1} <-> {v2}")
                for v3 in grafo.get(v2, []):
                    if v3 != v1 and v1 in grafo.get(v3, []):
                        ciclos.append(f"Ciclo triangular: {v1} -> {v2} -> {v3} -> {v1}")

        # Palabras clave como respaldo
        indicadores = ["retroalimentación", "feedback", "bucle", "loop", "cíclico", "circular"]
        for ind in indicadores:
            if ind in text_lower and not ciclos:
                ciclos.append(f"Indicador textual de ciclo: {ind}")

        return ciclos

    def _evaluar_coherencia(self, texto: str, variables: List[str], ciclos: List[str]) -> float:
        """Evalúa coherencia causal 0.0-1.0."""
        base = 0.7

        # Penalizar ciclos
        base -= len(ciclos) * 0.15

        # Penalizar falta de variables
        if len(variables) < 2:
            base -= 0.2

        # Bonificar por conectores causales explícitos
        conectores = ["porque", "debido a", "causa", "produce", "resultado", "therefore"]
        text_lower = texto.lower()
        for c in conectores:
            if c in text_lower:
                base += 0.05

        return max(0.0, min(1.0, base))

    def _inferir_relaciones(self, texto: str, variables: List[str]) -> List[RelacionCausal]:
        """Infiere relaciones causales entre variables."""
        relaciones = []
        if len(variables) >= 2:
            # Relación simple entre primera y segunda variable
            relaciones.append(RelacionCausal(
                causa=variables[0],
                efecto=variables[1],
                fuerza=0.5,
                tipo="directa" if "directa" in texto.lower() else "indirecta",
                evidencia=["inferida del texto"]
            ))
        return relaciones

    def detectar_ciclos_causales(self, hipotesis_texto: str) -> List[str]:
        """API pública: detecta ciclos en texto de hipótesis."""
        variables = self._extraer_variables(hipotesis_texto)
        return self._detectar_ciclos(hipotesis_texto, variables)

    def entropia_shannon(self, probabilidades: List[float]) -> float:
        """API pública: calcula entropía de Shannon."""
        import math
        entropia = 0.0
        for p in probabilidades:
            if p > 0:
                entropia -= p * math.log2(p)
        return entropia

    def informacion_mutua(self, px: List[float], py: List[float], pxy: List[List[float]]) -> float:
        """API pública: información mutua entre variables.

        Args:
            px: Distribución marginal P(X) como lista de probabilidades.
            py: Distribución marginal P(Y) como lista de probabilidades.
            pxy: Distribución conjunta P(X,Y) como matriz de probabilidades.

        Returns:
            Información mutua I(X;Y) en bits.

        Raises:
            TypeError: Si px, py o pxy no son listas/arrays.
            ValueError: Si las dimensiones no son consistentes.
        """
        import math

        if not isinstance(px, (list, tuple)):
            raise TypeError(
                f"px debe ser una lista de probabilidades (list[float]), "
                f"recibido {type(px).__name__}. "
                f"Para variables binarias use px=[0.5, 0.5]."
            )
        if not isinstance(py, (list, tuple)):
            raise TypeError(
                f"py debe ser una lista de probabilidades (list[float]), "
                f"recibido {type(py).__name__}."
            )
        if not isinstance(pxy, (list, tuple)):
            raise TypeError(
                f"pxy debe ser una matriz (list[list[float]]), "
                f"recibido {type(pxy).__name__}."
            )

        if len(pxy) != len(px) or any(len(row) != len(py) for row in pxy):
            raise ValueError(
                f"Dimensiones inconsistentes: px={len(px)}, py={len(py)}, "
                f"pxy={len(pxy)}x{len(pxy[0]) if pxy else 0}"
            )

        mi = 0.0
        for i, pi in enumerate(px):
            for j, pj in enumerate(py):
                if pxy[i][j] > 0 and pi > 0 and pj > 0:
                    mi += pxy[i][j] * math.log2(pxy[i][j] / (pi * pj))
        return mi

    def disponible(self) -> bool:
        """Indica si el motor está operativo."""
        return True

    def get_health_status(self) -> Dict[str, Any]:
        """Estado de salud del motor."""
        return {
            "status": "ok",
            "version": self.version,
            "historial_count": len(self.historial),
            "disponible": True
        }
