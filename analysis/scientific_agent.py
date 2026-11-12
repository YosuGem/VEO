# -*- coding: utf-8 -*-
"""
VEO: Sistema Operativo para Intuicion Social
=====================================================

Sistema de validacion dual para hipotesis basado en:
- Agente Cientifico: metodo popperiano de refutacion
- Agente Esceptico: deteccion y cuestionamiento de sesgos
- CoordinadorValidacion: integracion de ambos veredictos

Filosofia VEO: toda conclusion debe incluir evidencias, nivel de confianza,
explicacion del razonamiento, hipotesis alternativas, y posibles sesgos detectados.

Autor: VEO Team
Licencia: MIT
"""

from __future__ import annotations

import json
import logging
import re
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Dependencia minima: solo 'requests' para llamadas al LLM
# ---------------------------------------------------------------------------
try:
    import requests
except ImportError:
    requests = None  # type: ignore[assignment]


# ============================================================================
# EXCEPCIONES PERSONALIZADAS
# ============================================================================

class ValidacionError(Exception):
    """Error base del sistema de validacion VEO."""


class LLMError(ValidacionError):
    """Error al comunicarse con el servicio de LLM."""


class ConfiguracionError(ValidacionError):
    """Error en la configuracion del agente."""


# ============================================================================
# ENUMERACIONES
# ============================================================================

class VeredictoCientifico(str, Enum):
    """Veredicto emitido por el Agente Cientifico tras refutacion popperiana."""
    CONFIRMADA = "confirmada"
    REFUTADA = "refutada"
    INCONCLUSA = "inconclusa"


class VeredictoFinal(str, Enum):
    """Veredicto integrado emitido por el CoordinadorValidacion."""
    ACEPTAR = "ACEPTAR"
    DESCARTAR = "DESCARTAR"
    NECESITA_MAS_EVIDENCIA = "NECESITA_MAS_EVIDENCIA"
    REVISION_MANUAL = "REVISION_MANUAL"


class TipoSesgo(str, Enum):
    """Tipos de sesgo cognitivo detectados por el Agente Esceptico."""
    CONFIRMACION = "sesgo_de_confirmacion"
    DISPONIBILIDAD = "sesgo_de_disponibilidad"
    ANCLAJE = "sesgo_de_anclaje"
    GRUPO = "sesgo_de_grupo"
    SUPERVIVENCIA = "sesgo_de_supervivencia"
    CAUSALIDAD_INVERSA = "sesgo_de_causalidad_inversa"
    GENERALIZACION_EXCESIVA = "generalizacion_excesiva"
    SENSACIONALISMO = "sensacionalismo"


class TipoFalacia(str, Enum):
    """Tipos de falacia logica detectables por el sistema."""
    POST_HOC = "post_hoc_ergo_propter_hoc"
    AD_HOMINEM = "ad_hominem"
    FALSO_DILEMA = "falso_dilema"
    APPEL_AD_AUCTORITATEM = "appeal_to_authority"
    SLIPPERY_SLOPE = "slippery_slope"
    HASTY_GENERALIZATION = "hasty_generalization"
    CIRCULAR = "circular_reasoning"
    STRAW_MAN = "straw_man"
    TU_QUOQUE = "tu_quoque"
    NO_TRUE_SCOTSMAN = "no_true_scotsman"


# ============================================================================
# CLASES DE DATOS (Data Classes)
# ============================================================================

@dataclass
class Hipotesis:
    """
    Representa una hipotesis a validar por el sistema VEO.

    Atributos:
        texto: Enunciado de la hipotesis.
        autor: Quien propuso la hipotesis (opcional).
        fuentes: Lista de fuentes/evidencias citadas (opcional).
        fecha: Fecha de formulacion (opcional).
        contexto: Contexto adicional (tema, dominio, etc.).
        nivel_confianza_inicial: Confianza declarada por el proponente (0-1).
        evidencia_a_favor: Evidencias que apoyan la hipotesis.
        evidencia_en_contra: Evidencias que contradice la hipotesis.
    """
    texto: str
    autor: Optional[str] = None
    fuentes: List[str] = field(default_factory=list)
    fecha: Optional[str] = None
    contexto: Optional[str] = None
    nivel_confianza_inicial: float = 0.5
    evidencia_a_favor: List[str] = field(default_factory=list)
    evidencia_en_contra: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.texto or not self.texto.strip():
            raise ConfiguracionError("La hipotesis no puede estar vacia.")


@dataclass
class ResultadoValidacion:
    """
    Resultado estructurado de la validacion de una hipotesis.

    Atributos:
        veredicto: Veredicto cientifico emitido.
        confianza: Nivel de confianza en el veredicto (0.0 - 1.0).
        razonamiento: Explicacion detallada del razonamiento.
        supuestos_identificados: Supuestos implicitos detectados.
        falacias_detectadas: Falacias logicas encontradas.
        hipotesis_alternativas: Hipotesis alternativas plausibles.
        evidencia_contraria: Evidencia que contradice la hipotesis.
        muestra_representativa: Si la muestra de datos es representativa.
        sesgos_detectados: Sesgos cognitivos identificados.
        recomendacion: Recomendacion final del sistema.
        timestamp: Momento de la validacion.
        metadatos: Informacion adicional.
    """
    veredicto: VeredictoCientifico
    confianza: float
    razonamiento: str
    supuestos_identificados: List[str] = field(default_factory=list)
    falacias_detectadas: List[str] = field(default_factory=list)
    hipotesis_alternativas: List[str] = field(default_factory=list)
    evidencia_contraria: List[str] = field(default_factory=list)
    muestra_representativa: Optional[bool] = None
    sesgos_detectados: Dict[str, Any] = field(default_factory=dict)
    recomendacion: str = ""
    timestamp: str = field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    metadatos: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EvaluacionSesgo:
    """
    Evaluacion de un sesgo especifico.

    Atributos:
        tipo: Tipo de sesgo detectado.
        presente: Si el sesgo esta presente.
        severidad: Gravedad del sesgo (0.0 = ausente, 1.0 = extremo).
        explicacion: Justificacion de la evaluacion.
        evidencia: Texto o datos que sustentan la deteccion.
    """
    tipo: TipoSesgo
    presente: bool
    severidad: float
    explicacion: str
    evidencia: str = ""


# ============================================================================
# FUNCIONES AUXILIARES DE PROMPTS Y TEXTO
# ============================================================================

def prompt_base_validacion() -> str:
    """
    Devuelve el prompt base con instrucciones de rigor cientifico
    que se aplica a todos los agentes del sistema.

    Returns:
        str: Prompt base con instrucciones de rigor metodologico.
    """
    return (
        "Eres un investigador cientifico riguroso aplicando el metodo critico de Karl Popper. "
        "Tu objetivo NO es confirmar la hipotesis, sino INTENTAR REFUTARLA. "
        "Una hipotesis solo es cientificamente util si es falsable.\n\n"
        "REGLAS DE RIGOR:\n"
        "1. Exige evidencia empirica observable y verificable.\n"
        "2. Identifica supuestos implicitos que podrian ser falsos.\n"
        "3. Busca explicaciones alternativas que tambien expliquen los datos.\n"
        "4. Distingue entre correlacion y causalidad con rigor.\n"
        "5. Evalua si la muestra de datos es representativa y suficiente.\n"
        "6. Detecta falacias logicas en el razonamiento.\n"
        "7. Considera sesgos cognitivos que podrian distorsionar la conclusion.\n"
        "8. Evalua la replicabilidad de los resultados citados.\n"
        "9. Examina conflictos de interes en las fuentes.\n"
        "10. Respeta el principio de parcimonia (Rasoir d'Ockham).\n\n"
        "FORMATO DE RESPUESTA (JSON estricto):\n"
        "Devuelve SIEMPRE un JSON valido sin texto adicional.\n"
    )


def extraer_supuestos(texto: str) -> List[str]:
    """
    Extrae supuestos implicitos de un texto usando patrones linguisticos.

    Metodo heuristico que identifica:
    - Afirmaciones causales implicitas
    - Supuestos de generalidad
    - Presuposiciones en el lenguaje
    - Premisas no declaradas

    Args:
        texto: Texto de la hipotesis o argumento.

    Returns:
        List[str]: Lista de supuestos implicitos identificados.
    """
    supuestos: List[str] = []
    texto_lower = texto.lower()

    # Patrones de supuestos causales
    patrones_causales = [
        r"(\w+)\s+(causa|provoca|genera|produce)\s+(\w+)",
        r"(por\s+que|porque|debido\s+a|gracias\s+a)",
        r"(resulta\s+en|conduce\s+a|lleva\s+a)",
    ]
    for patron in patrones_causales:
        matches = re.finditer(patron, texto_lower)
        for m in matches:
            supuestos.append(f"Supuesto causal: '{m.group()}' - se asume relacion causal sin evidencia experimental.")

    # Patrones de generalizacion
    if re.search(r"\b(todos|siempre|nunca|ninguno|cada)\b", texto_lower):
        supuestos.append("Supuesto de generalidad universal: el uso de cuantificadores absolutos ('todos', 'siempre', 'nunca') asume que no existen excepciones.")

    # Patrones de suposicion temporal
    if re.search(r"\b(ahora|hoy|recientemente|ultimamente|actualmente)\b", texto_lower):
        supuestos.append("Supuesto temporal: la hipotesis puede estar anclada a condiciones temporales especificas que no son permanentes.")

    # Patrones de valoracion normativa
    if re.search(r"\b(deberia|deberiamos|es\s+necesario|es\s+urgente|es\s+importante)\b", texto_lower):
        supuestos.append("Supuesto normativo: la hipotesis mezcla descripcion de hechos con prescripcion de valores (falacia naturalista).")

    # Supuesto de homogeneidad grupal
    if re.search(r"\b(los\s+\w+|las\s+\w+|ellos|nosotros)\s+(son|tienen|hacen)\b", texto_lower):
        supuestos.append("Supuesto de homogeneidad grupal: se asume que un grupo es uniforme en sus caracteristicas.")

    # Supuesto de linealidad
    if re.search(r"\b(mientras\s+más|a\s+mayor|a\s+menor|incrementa|disminuye)\b", texto_lower):
        supuestos.append("Supuesto de linealidad: se asume una relacion lineal que podria ser no lineal o tener umbrales.")

    # Si no se detectaron supuestos heuristicamente
    if not supuestos:
        supuestos.append("Supuesto implicito general: la hipotesis asume que las condiciones observadas son aplicables al contexto general.")

    return supuestos


def evaluar_fuerza_evidente(evidencias: List[str]) -> float:
    """
    Evalua la calidad y fuerza de un conjunto de evidencias.

    Heuristicas:
    - Evidencia experimental > Evidencia observacional > Evidencia anecdotal
    - Diversidad de fuentes aumenta la fuerza
    - Cantidad minima de evidencias para robustez

    Args:
        evidencias: Lista de strings con evidencias.

    Returns:
        float: Score de fuerza evidente (0.0 - 1.0).
    """
    if not evidencias:
        return 0.0

    score: float = 0.0
    evidencia_texto = " ".join(evidencias).lower()

    # Evidencia experimental (maximo peso)
    if any(p in evidencia_texto for p in ["experimento", "ensayo controlado", "aleatorizado", "randomizado", "trial"]):
        score += 0.4

    # Evidencia estadistica
    if any(p in evidencia_texto for p in ["p <", "significativo", "correlacion", "regresion", "meta-analisis", "metaanalisis"]):
        score += 0.3

    # Evidencia observacional sistematica
    if any(p in evidencia_texto for p in ["estudio longitudinal", "cohorte", "transversal", "encuesta", "observacional"]):
        score += 0.2

    # Evidencia replicada
    if any(p in evidencia_texto for p in ["replicado", "replicacion", "confirmado independientemente", "consistente"]):
        score += 0.15

    # Penalizacion por evidencia puramente anecdotal
    if any(p in evidencia_texto for p in ["alguien dijo", "he oido", "mi experiencia", "caso de", "anecdota"]):
        score -= 0.2

    # Bonificacion por diversidad de fuentes
    diversidad_indicadores = ["revista", "universidad", "instituto", "laboratorio", "dataset", "encuesta"]
    diversidad_count = sum(1 for d in diversidad_indicadores if d in evidencia_texto)
    score += min(diversidad_count * 0.05, 0.15)

    # Penalizacion por poca cantidad de evidencia
    if len(evidencias) < 2:
        score -= 0.15
    elif len(evidencias) >= 5:
        score += 0.1

    return max(0.0, min(1.0, score))


# ============================================================================
# CLIENTE LLM MINIMO
# ============================================================================

class LLMClient:
    """
    Cliente minimo para comunicarse con cualquier API compatible con OpenAI.

    Soporta:
    - APIs con formato OpenAI (/v1/chat/completions)
    - Configuracion de timeout y reintentos
    - Fallback silencioso ante fallos de conectividad
    """

    def __init__(
        self,
        api_url: str,
        api_key: Optional[str] = None,
        model: str = "gpt-4o-mini",
        timeout: int = 30,
        max_retries: int = 2,
    ) -> None:
        self.api_url = api_url.rstrip("/")
        self.api_key = api_key or ""
        self.model = model
        self.timeout = timeout
        self.max_retries = max_retries
        self._disponible = requests is not None

    def completar(self, prompt_sistema: str, prompt_usuario: str, temperature: float = 0.3) -> str:
        """
        Envia una peticion de completacion al LLM y devuelve el texto.

        Args:
            prompt_sistema: Instrucciones del sistema.
            prompt_usuario: Contenido de la consulta.
            temperature: Creatividad de la respuesta (baja para rigor).

        Returns:
            str: Texto de respuesta del LLM.

        Raises:
            LLMError: Si no hay conectividad o la API falla despues de reintentos.
        """
        if not self._disponible:
            raise LLMError("La libreria 'requests' no esta instalada. Instalar con: pip install requests")

        headers: Dict[str, str] = {
            "Content-Type": "application/json",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": prompt_sistema},
                {"role": "user", "content": prompt_usuario},
            ],
            "temperature": temperature,
            "max_tokens": 4000,
        }

        ultimo_error: Optional[Exception] = None
        for intento in range(self.max_retries + 1):
            try:
                respuesta = requests.post(
                    f"{self.api_url}/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=self.timeout,
                )
                respuesta.raise_for_status()
                datos = respuesta.json()
                contenido = datos["choices"][0]["message"]["content"]
                return contenido
            except Exception as exc:
                ultimo_error = exc
                if intento < self.max_retries:
                    time.sleep(1.5 * (intento + 1))

        raise LLMError(
            f"Fallo la comunicacion con el LLM tras {self.max_retries + 1} intentos: {ultimo_error}"
        )

    @property
    def disponible(self) -> bool:
        """Indica si el cliente LLM esta operativo."""
        return self._disponible and self.api_url != ""


# ============================================================================
# AGENTE CIENTIFICO (Metodo Popperiano de Refutacion)
# ============================================================================

class AgenteCientifico:
    """
    Agente que aplica el metodo popperiano para INTENTAR REFUTAR hipotesis.

    Principio: una hipotesis cientifica solo tiene valor si es falsable.
    El agente busca activamente evidencia contraria, supuestos debiles,
    falacias logicas y problemas metodologicos.

    Attributes:
        config: Diccionario de configuracion con al menos 'llm_api_url'.
        logger: Logger para seguimiento de operaciones.
        llm_client: Cliente para comunicacion con el LLM.
    """

    # Patrones heuristicos de falacias logicas (deteccion rapida sin LLM)
    PATRONES_FALACIAS: Dict[TipoFalacia, List[str]] = {
        TipoFalacia.POST_HOC: [
            r"despu[eé]s de .* (ocurri[oó]|pas[oó]|sucedi[oó])",
            r"luego de .* (aument[oó]|disminuy[oó]|cambi[oó])",
            r"(.*) provoc[oó] (.*)",
        ],
        TipoFalacia.AD_HOMINEM: [
            r"(como|porque|dado que) es \w+",
            r"(no merece confianza|no sabe de|incompetente)",
            r"(hip[oó]crita|doble moral)",
        ],
        TipoFalacia.FALSO_DILEMA: [
            r"(o .* o|o bien .* o bien)",
            r"(la [uú]nica opci[oó]n|no hay alternativa|o est[aá]s con|o est[aá]s contra)",
        ],
        TipoFalacia.APPEL_AD_AUCTORITATEM: [
            r"(seg[úu]n .* experto|de acuerdo con .* doctor|como dice .* cient[íi]fico)",
            r"(estudios demuestran|la ciencia dice|los expertos afirman)",
        ],
        TipoFalacia.SLIPPERY_SLOPE: [
            r"(si permitimos|si aceptamos|si dejamos) .* (luego|despu[eé]s|eventualmente) .* (terminaremos|acabaremos|llegaremos)",
            r"(puerta abierta|efecto domin[oó]|escalada) .* (hasta|hacia)",
        ],
        TipoFalacia.HASTY_GENERALIZATION: [
            r"(todos los|ninguno de los|siempre|nunca) .* (son|hacen|piensan)",
            r"(en mi experiencia|lo que vi|lo que observe) .* por eso",
        ],
        TipoFalacia.CIRCULAR: [
            r"(.*) porque \1",
            r"(es verdadero|es correcto) porque .* (es verdadero|es correcto)",
        ],
    }

    def __init__(self, config: Dict[str, Any] = None, logger: Optional[logging.Logger] = None) -> None:
        """
        Inicializa el Agente Cientifico.

        Args:
            config: Configuracion con:
                - llm_api_url (str): URL base de la API del LLM.
                - llm_api_key (str, opcional): Clave de API.
                - llm_model (str, opcional): Modelo a usar (default: gpt-4o-mini).
            logger: Logger opcional. Si no se provee, se usa uno por defecto.
        """
        self.config = config or {}
        self.logger = logger or logging.getLogger(self.__class__.__name__)
        self.llm_client = LLMClient(
            api_url=self.config.get("llm_api_url", ""),
            api_key=self.config.get("llm_api_key"),
            model=self.config.get("llm_model", "gpt-4o-mini"),
        )

    def refutar_hipotesis(
        self,
        hipotesis: Hipotesis,
        evidencia_contraria: Optional[List[str]] = None,
    ) -> ResultadoValidacion:
        """
        Aplica el metodo popperiano para INTENTAR REFUTAR una hipotesis.

        Pasos del metodo:
        1. Identifica supuestos implicitos de la hipotesis.
        2. Busca evidencia que contradiga cada supuesto.
        3. Verifica falacias logicas (post hoc, ad hominem, falso dilema, etc.).
        4. Comprueba si hay correlacion sin causalidad.
        5. Evalua si los datos de muestra son representativos.
        6. Asigna veredicto: confirmada / refutada / inconclusa.

        Args:
            hipotesis: La hipotesis a refutar.
            evidencia_contraria: Evidencia adicional contra la hipotesis.

        Returns:
            ResultadoValidacion: Resultado completo con razonamiento detallado.
        """
        self.logger.info("[AgenteCientifico] Iniciando refutacion popperiana de: %s", hipotesis.texto[:80])

        # --- Paso 1: Identificar supuestos implicitos ---
        supuestos = extraer_supuestos(hipotesis.texto)
        self.logger.debug("[AgenteCientifico] Supuestos identificados: %d", len(supuestos))

        # --- Paso 2: Buscar falacias logicas (heuristico + LLM) ---
        falacias = self._analizar_falacias(hipotesis.texto)
        self.logger.debug("[AgenteCientifico] Falacias detectadas: %d", len(falacias))

        # --- Paso 3: Verificar representatividad de la muestra ---
        todas_evidencias = list(hipotesis.evidencia_a_favor)
        representatividad = self._verificar_representatividad(todas_evidencias)
        self.logger.debug("[AgenteCientifico] Representatividad evaluada: %s", representatividad)

        # --- Paso 4: Evaluar fuerza de la evidencia ---
        fuerza_evidencia = evaluar_fuerza_evidente(hipotesis.evidencia_a_favor)
        self.logger.debug("[AgenteCientifico] Fuerza de evidencia: %.2f", fuerza_evidencia)

        # --- Paso 5: Intentar refutacion via LLM (si disponible) ---
        resultado_llm: Optional[Dict[str, Any]] = None
        if self.llm_client.disponible:
            try:
                prompt = self._construir_prompt_refutacion(hipotesis, evidencia_contraria)
                respuesta_llm = self.llm_client.completar(
                    prompt_sistema=prompt_base_validacion(),
                    prompt_usuario=prompt,
                    temperature=0.2,
                )
                resultado_llm = self._parsear_respuesta_llm(respuesta_llm)
                self.logger.info("[AgenteCientifico] Refutacion via LLM completada exitosamente.")
            except LLMError as exc:
                self.logger.warning("[AgenteCientifico] LLM no disponible, usando fallback heuristico: %s", exc)
        else:
            self.logger.info("[AgenteCientifico] LLM no configurado, usando evaluacion heuristica.")

        # --- Paso 6: Integrar resultados y emitir veredicto ---
        veredicto, confianza, razonamiento, hipotesis_alt, score_compuesto = self._integrar_veredicto(
            supuestos=supuestos,
            falacias=falacias,
            representatividad=representatividad,
            fuerza_evidencia=fuerza_evidencia,
            resultado_llm=resultado_llm,
            hipotesis=hipotesis,
        )

        self.logger.info(
            "[AgenteCientifico] Veredicto: %s | Confianza: %.2f",
            veredicto.value,
            confianza,
        )

        return ResultadoValidacion(
            veredicto=veredicto,
            confianza=confianza,
            razonamiento=razonamiento,
            supuestos_identificados=supuestos,
            falacias_detectadas=falacias,
            hipotesis_alternativas=hipotesis_alt,
            evidencia_contraria=evidencia_contraria or [],
            muestra_representativa=representatividad.get("es_representativa"),
            recomendacion=self._generar_recomendacion(veredicto, confianza, falacias),
            metadatos={
                "agente": "AgenteCientifico",
                "metodo": "popperiano",
                "fuerza_evidencia": fuerza_evidencia,
                "falacias_count": len(falacias),
                "supuestos_count": len(supuestos),
                "uso_llm": resultado_llm is not None,
                "score_compuesto": round(score_compuesto, 3),
            },
        )

    def _construir_prompt_refutacion(
        self,
        hipotesis: Hipotesis,
        evidencia_contraria: Optional[List[str]] = None,
    ) -> str:
        """
        Construye el prompt para el LLM con instrucciones de rigor cientifico.

        Args:
            hipotesis: Hipotesis a refutar.
            evidencia_contraria: Evidencia adicional contra.

        Returns:
            str: Prompt detallado para el LLM.
        """
        prompt = (
            f"HIPOTESIS A REFUTAR:\n"
            f"\"{hipotesis.texto}\"\n\n"
        )

        if hipotesis.contexto:
            prompt += f"CONTEXTO:\n{hipotesis.contexto}\n\n"

        if hipotesis.evidencia_a_favor:
            prompt += f"EVIDENCIA A FAVOR (presentada por el proponente):\n"
            for i, ev in enumerate(hipotesis.evidencia_a_favor, 1):
                prompt += f"  {i}. {ev}\n"
            prompt += "\n"

        if hipotesis.evidencia_en_contra:
            prompt += f"EVIDENCIA EN CONTRA (ya conocida):\n"
            for i, ev in enumerate(hipotesis.evidencia_en_contra, 1):
                prompt += f"  {i}. {ev}\n"
            prompt += "\n"

        if evidencia_contraria:
            prompt += f"EVIDENCIA CONTRARIA ADICIONAL:\n"
            for i, ev in enumerate(evidencia_contraria, 1):
                prompt += f"  {i}. {ev}\n"
            prompt += "\n"

        prompt += (
            "\nINSTRUCCIONES PARA LA REFUTACION:\n"
            "1. Enumera TODOS los supuestos implicitos en la hipotesis.\n"
            "2. Para cada supuesto, explica como podria ser FALSO.\n"
            "3. Identifica si hay falacias logicas en el razonamiento.\n"
            "4. Propone al menos 3 hipotesis alternativas que expliquen los mismos datos.\n"
            "5. Evalua si hay correlacion confundida con causalidad.\n"
            "6. Determina si la muestra de datos es representativa.\n"
            "7. Veredicto final: CONFIRMADA, REFUTADA, o INCONCLUSA.\n"
            "8. Nivel de confianza en el veredicto (0.0 a 1.0).\n"
            "9. Justificacion detallada del veredicto.\n\n"
            "Responde en JSON con esta estructura exacta:\n"
            "{\n"
            '  "supuestos": ["supuesto 1", "supuesto 2"],\n'
            '  "evidencia_contraria": ["contra 1", "contra 2"],\n'
            '  "falacias": ["falacia 1"],\n'
            '  "hipotesis_alternativas": ["alternativa 1", "alternativa 2", "alternativa 3"],\n'
            '  "correlacion_vs_causalidad": "explicacion",\n'
            '  "muestra_representativa": true/false,\n'
            '  "veredicto": "CONFIRMADA"|"REFUTADA"|"INCONCLUSA",\n'
            '  "confianza": 0.0-1.0,\n'
            '  "razonamiento": "justificacion detallada"\n'
            "}"
        )
        return prompt

    def _analizar_falacias(self, texto_hipotesis: str) -> List[str]:
        """
        Detecta falacias logicas comunes mediante patrones heuristicos + LLM.

        Primero aplica patrones regex rapidos, luego intenta refinar con LLM
        si esta disponible.

        Args:
            texto_hipotesis: Texto de la hipotesis a analizar.

        Returns:
            List[str]: Lista de falacias detectadas con descripcion.
        """
        falacias: List[str] = []
        texto_lower = texto_hipotesis.lower()

        for tipo_falacia, patrones in self.PATRONES_FALACIAS.items():
            for patron in patrones:
                if re.search(patron, texto_lower):
                    falacias.append(
                        f"{tipo_falacia.value}: posible falacia '{tipo_falacia.name}' "
                        f"detectada por patron linguistico."
                    )
                    break  # Una deteccion por tipo es suficiente

        # Refinar con LLM si disponible
        if self.llm_client.disponible and len(texto_hipotesis) > 20:
            try:
                prompt_falacias = (
                    f"Analiza el siguiente texto en busca de falacias logicas. "
                    f"Devuelve SOLO un JSON array de strings con las falacias encontradas. "
                    f"Si no hay falacias, devuelve un array vacio.\n\n"
                    f"TEXTO: \"{texto_hipotesis}\"\n\n"
                    f"Falacias a buscar: post hoc, ad hominem, falso dilema, "
                    f"apelacion a autoridad, pendiente resbaladiza, generalizacion apresurada, "
                    f"razonamiento circular, hombre de paja."
                )
                respuesta = self.llm_client.completar(
                    prompt_sistema="Eres un logico experto en falacias. Responde solo con JSON.",
                    prompt_usuario=prompt_falacias,
                    temperature=0.1,
                )
                falacias_llm = self._extraer_json_de_texto(respuesta)
                if isinstance(falacias_llm, list):
                    for f in falacias_llm:
                        if isinstance(f, str) and f not in falacias:
                            falacias.append(f)
            except Exception as exc:
                self.logger.debug("[AgenteCientifico] No se pudo refinar falacias con LLM: %s", exc)

        return falacias

    def _verificar_representatividad(self, evidencias: List[str]) -> Dict[str, Any]:
        """
        Evalua si la muestra de evidencias es representativa y sin sesgo.

        Heuristicas:
        - Diversidad de tipos de fuente
        - Diversidad temporal
        - Tamano minimo de muestra
        - Ausencia de concentracion en una sola fuente

        Args:
            evidencias: Lista de evidencias citadas.

        Returns:
            Dict con: es_representativa (bool), score (float), detalles (str).
        """
        if not evidencias:
            return {
                "es_representativa": False,
                "score": 0.0,
                "detalles": "No se proporcionaron evidencias. Imposible evaluar representatividad.",
            }

        texto_completo = " ".join(evidencias).lower()
        score = 0.5  # Base neutral

        # Diversidad de tipos de fuente
        tipos_fuente = {
            "academica": ["revista", "journal", "universidad", "estudio", "paper", "articulo"],
            "institucional": ["gobierno", "ministerio", "oms", "who", "onu", "unesco", "banco mundial"],
            "empirica": ["experimento", "encuesta", "dato", "muestra", "n=", "n ="],
            "periodistica": ["periodico", "diario", "noticia", "reportaje"],
        }

        tipos_encontrados = sum(
            1 for indicadores in tipos_fuente.values()
            if any(ind in texto_completo for ind in indicadores)
        )

        if tipos_encontrados >= 3:
            score += 0.3
        elif tipos_encontrados >= 2:
            score += 0.15
        elif tipos_encontrados == 1:
            score -= 0.1

        # Diversidad temporal
        anos = re.findall(r"\b(19\d{2}|20\d{2})\b", texto_completo)
        if len(set(anos)) >= 3:
            score += 0.2
        elif len(set(anos)) >= 2:
            score += 0.1
        elif not anos:
            score -= 0.1  # No hay fechas, no se puede verificar actualidad

        # Tamano de muestra
        if len(evidencias) >= 5:
            score += 0.1
        elif len(evidencias) < 3:
            score -= 0.15

        # Concentracion en fuente unica
        fuentes_unicas = len(set(e.strip() for e in evidencias))
        if fuentes_unicas == 1 and len(evidencias) > 1:
            score -= 0.2  # Multiples citas de la misma fuente

        score = max(0.0, min(1.0, score))

        return {
            "es_representativa": score >= 0.5,
            "score": round(score, 3),
            "detalles": (
                f"Muestra con {len(evidencias)} evidencias, "
                f"{tipos_encontrados} tipos de fuente, "
                f"{len(set(anos)) if anos else 0} periodos temporales. "
                f"Score: {score:.2f}/1.0"
            ),
        }

    def _integrar_veredicto(
        self,
        supuestos: List[str],
        falacias: List[str],
        representatividad: Dict[str, Any],
        fuerza_evidencia: float,
        resultado_llm: Optional[Dict[str, Any]],
        hipotesis: Hipotesis,
    ) -> Tuple[VeredictoCientifico, float, str, List[str], float]:
        """
        Integra todos los hallazgos y produce un veredicto final.

        Logica de decision:
        - Si hay falacias graves + evidencia debil -> REFUTADA
        - Si el LLM refuta con evidencia solida -> REFUTADA
        - Si no hay falacias + evidencia fuerte -> CONFIRMADA (provisional)
        - Si hay incertidumbre significativa -> INCONCLUSA

        Args:
            supuestos: Supuestos identificados.
            falacias: Falacias detectadas.
            representatividad: Evaluacion de representatividad.
            fuerza_evidencia: Score de fuerza de evidencia.
            resultado_llm: Resultado del LLM (si disponible).
            hipotesis: La hipotesis original.

        Returns:
            Tupla: (veredicto, confianza, razonamiento, hipotesis_alternativas).
        """
        hipotesis_alt: List[str] = []

        # Si tenemos resultado del LLM, lo usamos como base
        if resultado_llm is not None:
            veredicto_str = resultado_llm.get("veredicto", "INCONCLUSA").upper()
            veredicto = VeredictoCientifico.INCONCLUSA
            if veredicto_str == "CONFIRMADA":
                veredicto = VeredictoCientifico.CONFIRMADA
            elif veredicto_str == "REFUTADA":
                veredicto = VeredictoCientifico.REFUTADA

            confianza = float(resultado_llm.get("confianza", 0.5))
            razonamiento = resultado_llm.get("razonamiento", "Sin razonamiento detallado del LLM.")
            hipotesis_alt = resultado_llm.get("hipotesis_alternativas", [])

            # Refinar confianza con heuristicas locales
            if falacias and veredicto == VeredictoCientifico.CONFIRMADA:
                confianza *= 0.7  # Penalizar si hay falacias
                razonamiento += f"\n\n[AVISO] Se detectaron {len(falacias)} posibles falacias que debilitan la confirmacion."
            if not representatividad.get("es_representativa", True):
                confianza *= 0.8
                razonamiento += "\n\n[AVISO] La muestra de evidencia no es representativa."

            confianza = max(0.0, min(1.0, confianza))
            # score_compuesto no aplica con LLM (usar confianza como proxy)
            score_compuesto = confianza
            return veredicto, round(confianza, 3), razonamiento, hipotesis_alt, score_compuesto

        # --- Fallback: evaluacion puramente heuristica ---
        self.logger.info("[AgenteCientifico] Usando evaluacion heuristica (sin LLM).")

        # Calcular score compuesto
        score = fuerza_evidencia

        # Penalizaciones
        penalizacion_falacias = min(len(falacias) * 0.15, 0.5)
        score -= penalizacion_falacias

        if not representatividad.get("es_representativa", True):
            score -= 0.15

        # Supuestos debiles penalizan
        score -= min(len(supuestos) * 0.05, 0.2)

        score = max(0.0, min(1.0, score))

        # Determinar veredicto
        if score < 0.3:
            veredicto = VeredictoCientifico.REFUTADA
            confianza = round(1.0 - score, 3)
            razonamiento = (
                f"La hipotesis es debil segun evaluacion heuristica. "
                f"Fuerza de evidencia: {fuerza_evidencia:.2f}. "
                f"Falacias detectadas: {len(falacias)}. "
                f"Supuestos cuestionables: {len(supuestos)}. "
                f"Representatividad: {representatividad.get('es_representativa', 'desconocida')}. "
                f"Se recomienda descartar o investigar mas a fondo."
            )
        elif score > 0.7:
            veredicto = VeredictoCientifico.CONFIRMADA
            confianza = round(score, 3)
            razonamiento = (
                f"La hipotesis muestra fortaleza segun evaluacion heuristica. "
                f"Fuerza de evidencia: {fuerza_evidencia:.2f}. "
                f"Sin falacias graves detectadas ({len(falacias)} menores). "
                f"La confirmacion es PROVISIONAL y sujeta a nueva evidencia."
            )
        else:
            veredicto = VeredictoCientifico.INCONCLUSA
            confianza = 0.5
            razonamiento = (
                f"No hay suficiente evidencia para confirmar ni refutar. "
                f"Score compuesto: {score:.2f}. "
                f"Se necesitan mas datos o un analisis mas profundo. "
                f"Falacias detectadas: {len(falacias)}. "
                f"Supuestos identificados: {len(supuestos)}."
            )

        # Hipotesis alternativas por defecto
        if not hipotesis_alt:
            hipotesis_alt = [
                "La correlacion observada podria ser espuria (tercer factor no considerado).",
                "El efecto podria ser bidireccional o de retroalimentacion.",
                "Los datos podrian explicarse por azar estadistico o sesgo de seleccion.",
            ]

        return veredicto, confianza, razonamiento, hipotesis_alt, score

    def _generar_recomendacion(
        self,
        veredicto: VeredictoCientifico,
        confianza: float,
        falacias: List[str],
    ) -> str:
        """Genera una recomendacion textual basada en el veredicto."""
        if veredicto == VeredictoCientifico.REFUTADA:
            return (
                "La hipotesis ha sido refutada por el metodo popperiano. "
                "Se recomienda DESCARTARLA y buscar explicaciones alternativas. "
                f"Confianza en la refutacion: {confianza:.1%}."
            )
        elif veredicto == VeredictoCientifico.CONFIRMADA:
            rec = (
                "La hipotesis ha resistido los intentos de refutacion. "
                f"Puede ACEPTARSE PROVISIONALMENTE con confianza {confianza:.1%}. "
                "NOTA: Toda confirmacion en ciencia es provisional y sujeta a nueva evidencia."
            )
            if falacias:
                rec += f"\nADVERTENCIA: Se detectaron {len(falacias)} posibles falacias menores."
            return rec
        else:
            return (
                "La evidencia es INSUFICIENTE para emitir un veredicto. "
                "Se requiere mas investigacion empirica antes de aceptar o rechazar. "
                "Recomendacion: disenar experimentos que puedan refutar la hipotesis."
            )

    def _parsear_respuesta_llm(self, respuesta: str) -> Optional[Dict[str, Any]]:
        """Extrae JSON de la respuesta del LLM, con limpieza de formato markdown."""
        try:
            # Intentar parsear directamente
            return json.loads(respuesta)
        except json.JSONDecodeError:
            pass

        # Limpiar formato markdown (```json ... ```)
        match = re.search(r"```(?:json)?\s*(\{.*\})\s*```", respuesta, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass

        # Buscar cualquier objeto JSON en el texto
        match = re.search(r"(\{.*\})", respuesta, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass

        self.logger.warning("[AgenteCientifico] No se pudo parsear JSON de la respuesta del LLM.")
        return None

    def _extraer_json_de_texto(self, texto: str) -> Any:
        """Extrae estructura JSON de texto, con manejo de errores."""
        try:
            return json.loads(texto)
        except json.JSONDecodeError:
            match = re.search(r"```(?:json)?\s*(\[.*\])\s*```", texto, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(1))
                except json.JSONDecodeError:
                    pass
            match = re.search(r"(\[.*\])", texto, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(1))
                except json.JSONDecodeError:
                    pass
        return None



# ============================================================================
# AGENTE ESCEPTICO (Cuestionamiento de Sesgos)
# ============================================================================

class AgenteEsceptico:
    """
    Agente que cuestiona sesgos cognitivos y limitaciones en hipotesis.

    El esceptico NO evalua si la hipotesis es verdadera o falsa;
    evalua si el proceso que la genero esta libre de distorsiones cognitivas.

    Sesgos evaluados:
    1. Sesgo de confirmacion
    2. Sesgo de disponibilidad
    3. Sesgo de anclaje
    4. Sesgo de grupo
    5. Sesgo de supervivencia
    6. Sesgo de causalidad inversa
    7. Generalizacion excesiva
    8. Sensacionalismo

    Attributes:
        config: Diccionario de configuracion.
        logger: Logger para seguimiento.
        llm_client: Cliente para comunicacion con el LLM.
    """

    def __init__(self, config: Dict[str, Any] = None, logger: Optional[logging.Logger] = None) -> None:
        """
        Inicializa el Agente Esceptico.

        Args:
            config: Configuracion con:
                - llm_api_url (str): URL base de la API del LLM.
                - llm_api_key (str, opcional): Clave de API.
                - llm_model (str, opcional): Modelo a usar.
            logger: Logger opcional.
        """
        self.config = config or {}
        self.logger = logger or logging.getLogger(self.__class__.__name__)
        self.llm_client = LLMClient(
            api_url=self.config.get("llm_api_url", ""),
            api_key=self.config.get("llm_api_key"),
            model=self.config.get("llm_model", "gpt-4o-mini"),
        )

    def cuestionar_hipotesis(
        self,
        hipotesis: Hipotesis,
        contexto: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Cuestiona sistematicamente los sesgos y limitaciones de una hipotesis.

        Evalua 8 dimensiones de sesgo:
        1. Sesgo de confirmacion: que evidencia falta que contradiga?
        2. Sesgo de disponibilidad: son las fuentes representativas?
        3. Sesgo de anclaje: la hipotesis esta anclada a datos recientes?
        4. Sesgo de grupo: las fuentes son diversas ideologicamente?
        5. Sesgo de supervivencia: se ignoran casos donde la hipotesis fallo?
        6. Sesgo de causalidad inversa: podria ser el efecto la causa?
        7. Generalizacion excesiva: se extrapola mas alla de lo justificado?
        8. Sensacionalismo: la hipotesis es mas dramatica de lo que los datos sugieren?

        Args:
            hipotesis: La hipotesis a cuestionar.
            contexto: Contexto adicional (fuentes disponibles, marco ideologico, etc.).

        Returns:
            Dict con cada sesgo evaluado:
                - presente (bool)
                - severidad (0.0 - 1.0)
                - explicacion (str)
        """
        self.logger.info("[AgenteEsceptico] Cuestionando sesgos de: %s", hipotesis.texto[:80])

        # Deteccion rapida via patrones heuristicos
        evaluaciones: Dict[str, Any] = {}

        # 1. Sesgo de confirmacion
        evaluaciones[TipoSesgo.CONFIRMACION.value] = self._evaluar_sesgo_confirmacion(hipotesis)

        # 2. Sesgo de disponibilidad
        evaluaciones[TipoSesgo.DISPONIBILIDAD.value] = self._evaluar_sesgo_disponibilidad(hipotesis)

        # 3. Sesgo de anclaje
        evaluaciones[TipoSesgo.ANCLAJE.value] = self._evaluar_sesgo_anclaje(hipotesis)

        # 4. Sesgo de grupo
        evaluaciones[TipoSesgo.GRUPO.value] = self._evaluar_sesgo_grupo(hipotesis, contexto)

        # 5. Sesgo de supervivencia
        evaluaciones[TipoSesgo.SUPERVIVENCIA.value] = self._evaluar_sesgo_supervivencia(hipotesis)

        # 6. Sesgo de causalidad inversa
        evaluaciones[TipoSesgo.CAUSALIDAD_INVERSA.value] = self._evaluar_causalidad_inversa(hipotesis)

        # 7. Generalizacion excesiva
        evaluaciones[TipoSesgo.GENERALIZACION_EXCESIVA.value] = self._evaluar_generalizacion(hipotesis)

        # 8. Sensacionalismo
        evaluaciones[TipoSesgo.SENSACIONALISMO.value] = self._evaluar_sensacionalismo(hipotesis)

        # Refinar con LLM si disponible
        if self.llm_client.disponible:
            try:
                evaluaciones = self._refinar_con_llm(hipotesis, evaluaciones, contexto)
                self.logger.info("[AgenteEsceptico] Evaluacion refinada con LLM.")
            except LLMError as exc:
                self.logger.warning("[AgenteEsceptico] LLM no disponible, usando heuristicas: %s", exc)

        # Calcular score agregado
        score_sesgo = self.calcular_score_sesgo({"evaluaciones": evaluaciones})

        self.logger.info(
            "[AgenteEsceptico] Score de sesgo global: %.2f (0=limpio, 1=muy sesgado)",
            score_sesgo,
        )

        return {
            "evaluaciones": evaluaciones,
            "score_global": round(score_sesgo, 3),
            "interpretacion": self._interpretar_score(score_sesgo),
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }

    def detectar_sesgos(self, texto: str) -> Dict[str, Any]:
        """
        Detecta sesgos en texto usando patrones linguisticos + LLM.

        Args:
            texto: Texto a analizar.

        Returns:
            Dict con sesgos detectados y sus metricas.
        """
        self.logger.info("[AgenteEsceptico] Detectando sesgos en texto.")

        texto_lower = texto.lower()
        sesgos_detectados: Dict[str, Dict[str, Any]] = {}

        # Patron: confirmacion (solo mencionar evidencia a favor)
        ind_confirmacion = 0.0
        if re.search(r"\b(obviamente|claramente|sin duda|est[aá] demostrado|est[aá] probado)\b", texto_lower):
            ind_confirmacion += 0.4
        if not re.search(r"\b(sin embargo|por otro lado|aunque|podr[ií]a ser|quiz[aá]s|tal vez)\b", texto_lower):
            ind_confirmacion += 0.3  # No hay matizacion = sesgo de confirmacion
        sesgos_detectados[TipoSesgo.CONFIRMACION.value] = {
            "presente": ind_confirmacion > 0.3,
            "severidad": round(min(ind_confirmacion, 1.0), 3),
            "explicacion": "El texto muestra fuerte certeza sin considerar alternativas." if ind_confirmacion > 0.3 else "Matizacion presente, menor sesgo de confirmacion.",
        }

        # Patron: disponibilidad (ejemplos vividos)
        ind_disp = 0.0
        if re.search(r"\b(recuerdo|vi|escuch[eé]|me pas[oó]|conozco a alguien)\b", texto_lower):
            ind_disp += 0.5
        if re.search(r"\b(últimamente|cada vez más|todo el mundo)\b", texto_lower):
            ind_disp += 0.3
        sesgos_detectados[TipoSesgo.DISPONIBILIDAD.value] = {
            "presente": ind_disp > 0.3,
            "severidad": round(min(ind_disp, 1.0), 3),
            "explicacion": "Uso de ejemplos personales/recientes sugiere sesgo de disponibilidad." if ind_disp > 0.3 else "Poco indicio de sesgo de disponibilidad.",
        }

        # Patron: sensacionalismo
        ind_sens = 0.0
        palabras_sensacionalistas = [
            "catastrofe", "crisis", "escandalo", "devastador", "tragico",
            "impactante", "increible", "shocking", "dramatico", "alarma",
            "urgente", "emergencia", "colapso", "apocalipsis", "fin del",
        ]
        for palabra in palabras_sensacionalistas:
            if palabra in texto_lower:
                ind_sens += 0.15
        ind_sens = min(ind_sens, 1.0)
        sesgos_detectados[TipoSesgo.SENSACIONALISMO.value] = {
            "presente": ind_sens > 0.3,
            "severidad": round(ind_sens, 3),
            "explicacion": f"Se detectaron {int(ind_sens/0.15)} terminos sensacionalistas." if ind_sens > 0 else "Sin indicios de sensacionalismo.",
        }

        # Patron: generalizacion excesiva
        ind_gen = 0.0
        if re.search(r"\b(todos|siempre|nunca|ninguno|cada|absolutamente)\b", texto_lower):
            ind_gen += 0.5
        if re.search(r"\b(en general|por lo general|la gente|las personas)\b", texto_lower):
            ind_gen += 0.25
        sesgos_detectados[TipoSesgo.GENERALIZACION_EXCESIVA.value] = {
            "presente": ind_gen > 0.3,
            "severidad": round(min(ind_gen, 1.0), 3),
            "explicacion": "Uso de generalizaciones universales detectado." if ind_gen > 0.3 else "Generalizacion controlada.",
        }

        # Refinar con LLM si disponible
        if self.llm_client.disponible:
            try:
                prompt = self._prompt_sesgos_para_texto(texto)
                respuesta = self.llm_client.completar(
                    prompt_sistema=(
                        "Eres un psicologo cognitivo experto en sesgos. "
                        "Detecta sesgos en el texto dado. Responde SOLO con JSON."
                    ),
                    prompt_usuario=prompt,
                    temperature=0.2,
                )
                sesgos_llm = self._parsear_json_sesgos(respuesta)
                if sesgos_llm:
                    sesgos_detectados.update(sesgos_llm)
            except Exception as exc:
                self.logger.debug("[AgenteEsceptico] No se pudo refinar con LLM: %s", exc)

        return {
            "sesgos": sesgos_detectados,
            "score_global": self.calcular_score_sesgo({"evaluaciones": sesgos_detectados}),
        }

    def _prompt_sesgos(self, hipotesis: Hipotesis) -> str:
        """
        Construye prompt especializado para deteccion de sesgos.

        Args:
            hipotesis: Hipotesis a evaluar.

        Returns:
            str: Prompt detallado para el LLM.
        """
        prompt = (
            f"Analiza la siguiente hipotesis en busca de SESGOS COGNITIVOS.\n\n"
            f"HIPOTESIS: \"{hipotesis.texto}\"\n"
        )
        if hipotesis.contexto:
            prompt += f"CONTEXTO: {hipotesis.contexto}\n"
        if hipotesis.autor:
            prompt += f"AUTOR: {hipotesis.autor}\n"
        if hipotesis.fuentes:
            prompt += f"FUENTES: {', '.join(hipotesis.fuentes)}\n"
        if hipotesis.evidencia_a_favor:
            prompt += f"\nEVIDENCIA A FAVOR:\n"
            for ev in hipotesis.evidencia_a_favor:
                prompt += f"  - {ev}\n"

        prompt += (
            "\nEvalua CADA uno de estos 8 sesgos y devuelve SOLO un JSON:\n"
            "{\n"
            f'  "{TipoSesgo.CONFIRMACION.value}": {{\n'
            f'    "presente": true/false,\n'
            f'    "severidad": 0.0-1.0,\n'
            f'    "explicacion": "justificacion"\n'
            f'  }},\n'
            f'  "{TipoSesgo.DISPONIBILIDAD.value}": {{...}},\n'
            f'  "{TipoSesgo.ANCLAJE.value}": {{...}},\n'
            f'  "{TipoSesgo.GRUPO.value}": {{...}},\n'
            f'  "{TipoSesgo.SUPERVIVENCIA.value}": {{...}},\n'
            f'  "{TipoSesgo.CAUSALIDAD_INVERSA.value}": {{...}},\n'
            f'  "{TipoSesgo.GENERALIZACION_EXCESIVA.value}": {{...}},\n'
            f'  "{TipoSesgo.SENSACIONALISMO.value}": {{...}}\n'
            "}\n\n"
            "INSTRUCCIONES:\n"
            "- severidad: 0.0 = no hay sesgo, 1.0 = sesgo extremo\n"
            "- explicacion: justifica tu evaluacion con referencias al texto\n"
            "- presente: true solo si la severidad es > 0.5\n"
            "Responde SOLO con el JSON, sin texto adicional."
        )
        return prompt

    def _prompt_sesgos_para_texto(self, texto: str) -> str:
        """Prompt para detectar sesgos en texto libre."""
        return (
            f"Detecta sesgos cognitivos en el siguiente texto:\n\n"
            f"\"{texto}\"\n\n"
            f"Devuelve JSON con las mismas 8 categorias de sesgos. "
            f"Responde SOLO con el JSON."
        )

    def calcular_score_sesgo(self, evaluacion: Dict[str, Any]) -> float:
        """
        Calcula un score agregado de sesgo (0 = limpio, 1 = muy sesgado).

        Metodo: promedio ponderado de las severidades de cada sesgo.
        Los sesgos de confirmacion y supervivencia tienen mayor peso.

        Args:
            evaluacion: Dict con la evaluacion de sesgos (formato de cuestionar_hipotesis).

        Returns:
            float: Score global de sesgo entre 0.0 y 1.0.
        """
        evaluaciones = evaluacion.get("evaluaciones", evaluacion.get("sesgos", {}))
        if not evaluaciones:
            return 0.0

        pesos: Dict[str, float] = {
            TipoSesgo.CONFIRMACION.value: 1.5,
            TipoSesgo.SUPERVIVENCIA.value: 1.3,
            TipoSesgo.GENERALIZACION_EXCESIVA.value: 1.2,
            TipoSesgo.CAUSALIDAD_INVERSA.value: 1.1,
            TipoSesgo.SENSACIONALISMO.value: 1.1,
            TipoSesgo.DISPONIBILIDAD.value: 1.0,
            TipoSesgo.ANCLAJE.value: 0.9,
            TipoSesgo.GRUPO.value: 0.9,
        }

        suma_ponderada = 0.0
        suma_pesos = 0.0

        for tipo_sesgo, datos in evaluaciones.items():
            if isinstance(datos, dict) and "severidad" in datos:
                peso = pesos.get(tipo_sesgo, 1.0)
                suma_ponderada += datos["severidad"] * peso
                suma_pesos += peso

        if suma_pesos == 0:
            return 0.0

        return min(1.0, suma_ponderada / suma_pesos)

    # ------------------------------------------------------------------------
    # Metodos privados de evaluacion de sesgos individuales (heuristicos)
    # ------------------------------------------------------------------------

    def _evaluar_sesgo_confirmacion(self, hipotesis: Hipotesis) -> Dict[str, Any]:
        """Evalua si solo se considera evidencia a favor y se ignora la contraria."""
        texto = hipotesis.texto.lower()
        severidad = 0.0

        # Si hay mucha evidencia a favor y poca en contra
        ratio = len(hipotesis.evidencia_a_favor) / max(len(hipotesis.evidencia_en_contra), 1)
        if ratio > 5:
            severidad += 0.4
        elif ratio > 2:
            severidad += 0.2

        # Lenguaje de certeza absoluta
        if re.search(r"\b(demuestra|prueba|confirma|est[aá] claro|es obvio)\b", texto):
            severidad += 0.3

        # Ausencia de matizaciones
        if not re.search(r"\b(podr[ií]a|quiz[aá]s|tal vez|es posible|podria ser)\b", texto):
            severidad += 0.2

        severidad = min(1.0, severidad)
        return {
            "presente": severidad > 0.5,
            "severidad": round(severidad, 3),
            "explicacion": (
                f"Ratio evidencia favor/contra: {ratio:.1f}. "
                f"{'Lenguaje de certeza absoluta detectado. ' if severidad > 0.5 else ''}"
                f"{'Falta matizacion epistemica. ' if severidad > 0.3 else ''}"
                f"Score: {severidad:.2f}"
            ),
        }

    def _evaluar_sesgo_disponibilidad(self, hipotesis: Hipotesis) -> Dict[str, Any]:
        """Evalua si las fuentes son representativas o solo las mas accessibles/memorables."""
        texto = hipotesis.texto.lower()
        severidad = 0.0

        # Uso de ejemplos vividos/personales
        if re.search(r"\b(recuerdo|vi|me contaron|escuch[eé] que|conozco a)\b", texto):
            severidad += 0.5

        # Referencias a medios de comunicacion masiva (disponibles pero no rigurosos)
        if any(medio in texto for medio in ["noticia", "twitter", "redes", "tv", "television", "viral"]):
            severidad += 0.3

        # Pocas fuentes diversas
        if len(hipotesis.fuentes) > 0 and len(hipotesis.fuentes) < 3:
            severidad += 0.2

        severidad = min(1.0, severidad)
        return {
            "presente": severidad > 0.5,
            "severidad": round(severidad, 3),
            "explicacion": (
                f"Fuentes citadas: {len(hipotesis.fuentes)}. "
                f"{'Uso de fuentes de facil acceso/memorables. ' if severidad > 0.3 else ''}"
                f"Score: {severidad:.2f}"
            ),
        }

    def _evaluar_sesgo_anclaje(self, hipotesis: Hipotesis) -> Dict[str, Any]:
        """Evalua si la hipotesis esta anclada a datos recientes o a un valor inicial."""
        texto = hipotesis.texto.lower()
        severidad = 0.0

        # Referencias temporales recientes
        if re.search(r"\b(este a[ñn]o|este mes|recientemente|[uú]ltimamente|ahora|hoy|actualmente)\b", texto):
            severidad += 0.4

        # Referencia a datos especificos que pueden ser ancla
        if re.search(r"\b(un \d+%|un total de \d+|seg[úu]n el [uú]ltimo)\b", texto):
            severidad += 0.3

        # Si tiene fecha, verificar si es muy reciente
        if hipotesis.fecha:
            severidad += 0.15

        severidad = min(1.0, severidad)
        return {
            "presente": severidad > 0.5,
            "severidad": round(severidad, 3),
            "explicacion": (
                f"{'Referencia temporal reciente detectada. ' if severidad > 0.3 else ''}"
                f"{'Datos especificos pueden actuar como ancla. ' if severidad > 0.4 else ''}"
                f"Score: {severidad:.2f}"
            ),
        }

    def _evaluar_sesgo_grupo(
        self,
        hipotesis: Hipotesis,
        contexto: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Evalua si las fuentes son diversas ideologicamente."""
        severidad = 0.0

        # Si el contexto indica fuentes homogeneas
        if contexto:
            fuentes = contexto.get("fuentes_ideologicas", [])
            if len(set(fuentes)) == 1 and len(fuentes) > 1:
                severidad += 0.6  # Todas las fuentes del mismo lado
            elif len(set(fuentes)) <= 2:
                severidad += 0.3

        # Lenguaje partidista en la hipotesis
        texto = hipotesis.texto.lower()
        terminos_partidistas = [
            "izquierda", "derecha", "liberal", "conservador", "progresista",
            "reaccionario", "neoliberal", "populista", "radical",
        ]
        for termino in terminos_partidistas:
            if termino in texto:
                severidad += 0.2

        # Si no se proporcionaron fuentes
        if not hipotesis.fuentes:
            severidad += 0.1

        severidad = min(1.0, severidad)
        return {
            "presente": severidad > 0.5,
            "severidad": round(severidad, 3),
            "explicacion": (
                f"{'Fuentes ideologicamente homogeneas. ' if severidad > 0.4 else ''}"
                f"{'Lenguaje potencialmente partidista detectado. ' if severidad > 0.3 else ''}"
                f"Score: {severidad:.2f}"
            ),
        }

    def _evaluar_sesgo_supervivencia(self, hipotesis: Hipotesis) -> Dict[str, Any]:
        """
        Evalua si se ignoran casos donde la hipotesis fallo (sesgo de supervivencia).

        Este sesgo ocurre cuando solo se consideran los casos 'exitosos'
        y se ignoran los casos donde la hipotesis no se cumplio.
        """
        severidad = 0.0
        texto = hipotesis.texto.lower()

        # Si NO hay evidencia en contra registrada
        if not hipotesis.evidencia_en_contra:
            severidad += 0.5

        # Lenguaje que solo presenta casos exitosos
        if re.search(r"\b(todos los casos|siempre funciona|en todos los estudios|sin excepci[oó]n)\b", texto):
            severidad += 0.3

        # Si solo hay evidencia a favor
        if hipotesis.evidencia_a_favor and not hipotesis.evidencia_en_contra:
            severidad += 0.2

        severidad = min(1.0, severidad)
        return {
            "presente": severidad > 0.5,
            "severidad": round(severidad, 3),
            "explicacion": (
                f"{'No se registran casos de fallo de la hipotesis. ' if severidad > 0.4 else ''}"
                f"{'Lenguaje de universalidad sin contrafactuales. ' if severidad > 0.3 else ''}"
                f"Score: {severidad:.2f}"
            ),
        }

    def _evaluar_causalidad_inversa(self, hipotesis: Hipotesis) -> Dict[str, Any]:
        """Evalua si podria ser el efecto la causa (causalidad inversa)."""
        severidad = 0.0
        texto = hipotesis.texto.lower()

        # Patrones de causalidad unidireccional
        if re.search(r"\b(.*)\s+(provoca|genera|causa|produce)\s+(.*)\b", texto):
            severidad += 0.4

        # Si la hipotesis postula una direccion causal
        if re.search(r"\b(por lo tanto|por eso|debido a|como resultado)\b", texto):
            severidad += 0.2

        # Si hay evidencia de que la relacion podria ser bidireccional
        if "retroalimentacion" in texto or "feedback" in texto or "bidireccional" in texto:
            severidad -= 0.3  # Reducir si ya se considera bidireccionalidad

        severidad = max(0.0, min(1.0, severidad))
        return {
            "presente": severidad > 0.5,
            "severidad": round(severidad, 3),
            "explicacion": (
                f"{'La hipotesis asume direccion causal unidireccional. ' if severidad > 0.3 else ''}"
                f"{'Podria existir causalidad inversa o bidireccionalidad. ' if severidad > 0.4 else ''}"
                f"Score: {severidad:.2f}"
            ),
        }

    def _evaluar_generalizacion(self, hipotesis: Hipotesis) -> Dict[str, Any]:
        """Evalua si se extrapola mas alla de lo justificado por los datos."""
        severidad = 0.0
        texto = hipotesis.texto.lower()

        # Cuantificadores universales
        if re.search(r"\b(todos|siempre|nunca|ninguno|cada uno|absolutamente todos)\b", texto):
            severidad += 0.5

        # Generalizacion temporal
        if re.search(r"\b(en todo el mundo|globalmente|universalmente|en todos los pa[ií]ses)\b", texto):
            severidad += 0.4

        # Generalizacion desde muestra pequena
        muestra = len(hipotesis.evidencia_a_favor)
        if muestra == 1:
            severidad += 0.3
        elif muestra == 2:
            severidad += 0.15

        # Ausencia de limitaciones declaradas
        if not re.search(r"\b(limitaci[oó]n|solo en|particularmente|espec[íi]ficamente|bajo ciertas condiciones)\b", texto):
            severidad += 0.2

        severidad = min(1.0, severidad)
        return {
            "presente": severidad > 0.5,
            "severidad": round(severidad, 3),
            "explicacion": (
                f"{'Uso de cuantificadores universales. ' if severidad > 0.4 else ''}"
                f"{f'Generalizacion desde muestra pequena ({muestra} evidencias). ' if muestra <= 2 else ''}"
                f"{'Sin limitaciones declaradas. ' if severidad > 0.3 else ''}"
                f"Score: {severidad:.2f}"
            ),
        }

    def _evaluar_sensacionalismo(self, hipotesis: Hipotesis) -> Dict[str, Any]:
        """Evalua si la hipotesis es mas dramatica de lo que los datos sugieren."""
        import unicodedata
        severidad = 0.0
        # Normalizar tildes para deteccion consistente
        texto = unicodedata.normalize('NFKD', hipotesis.texto.lower()).encode('ASCII', 'ignore').decode('ASCII')

        # Terminos sensacionalistas
        terminos_drama = [
            "catastrofe", "devastador", "tragico", "impactante", "increible",
            "shocking", "dramatico", "alarma", "urgente", "emergencia",
            "colapso", "apocalipsis", "fin del mundo", "crisis", "escandalo",
            "milagro", "revolucionario", "cambio radical", "sin precedentes",
        ]
        for termino in terminos_drama:
            if termino in texto:
                severidad += 0.2

        # Exageracion mediante intensificadores
        if re.search(r"\b(extremadamente|increiblemente|absolutamente|totalmente)\b", texto):
            severidad += 0.15

        # Mayusculas excesivas
        mayusculas = sum(1 for c in hipotesis.texto if c.isupper())
        if len(hipotesis.texto) > 0 and mayusculas / len(hipotesis.texto) > 0.15:
            severidad += 0.2

        severidad = min(1.0, severidad)
        return {
            "presente": severidad > 0.5,
            "severidad": round(severidad, 3),
            "explicacion": (
                f"{'Terminos sensacionalistas detectados. ' if severidad > 0.3 else ''}"
                f"{'Intensificadores linguisticos presentes. ' if severidad > 0.4 else ''}"
                f"Score: {severidad:.2f}"
            ),
        }

    def _refinar_con_llm(
        self,
        hipotesis: Hipotesis,
        evaluaciones: Dict[str, Any],
        contexto: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Refina las evaluaciones heuristicas con el LLM."""
        prompt = self._prompt_sesgos(hipotesis)

        # Incluir contexto adicional
        if contexto:
            prompt += f"\n\nCONTEXTO ADICIONAL:\n{json.dumps(contexto, ensure_ascii=False, indent=2)}\n"

        prompt += (
            "\n\nEVALUACION PREVIA (heuristica):\n"
            f"{json.dumps(evaluaciones, ensure_ascii=False, indent=2)}\n\n"
            "Refina las evaluaciones basandote en el analisis profundo. "
            "Mantén el mismo formato JSON de 8 sesgos."
        )

        respuesta = self.llm_client.completar(
            prompt_sistema=(
                "Eres un experto en psicologia cognitiva y sesgos. "
                "Evalua con rigor y objetividad. Responde SOLO con JSON valido."
            ),
            prompt_usuario=prompt,
            temperature=0.2,
        )

        resultado = self._parsear_json_sesgos(respuesta)
        if resultado:
            return resultado
        return evaluaciones

    def _parsear_json_sesgos(self, texto: str) -> Optional[Dict[str, Any]]:
        """Extrae evaluacion de sesgos en formato JSON del texto."""
        # Intentar parsear directamente
        try:
            parsed = json.loads(texto)
            # Validar que tiene las claves esperadas
            if any(k in parsed for k in [s.value for s in TipoSesgo]):
                return parsed
        except json.JSONDecodeError:
            pass

        # Limpiar markdown
        match = re.search(r"```(?:json)?\s*(\{.*\})\s*```", texto, re.DOTALL)
        if match:
            try:
                parsed = json.loads(match.group(1))
                if any(k in parsed for k in [s.value for s in TipoSesgo]):
                    return parsed
            except json.JSONDecodeError:
                pass

        # Buscar cualquier objeto JSON
        match = re.search(r"(\{.*\})", texto, re.DOTALL)
        if match:
            try:
                parsed = json.loads(match.group(1))
                if any(k in parsed for k in [s.value for s in TipoSesgo]):
                    return parsed
            except json.JSONDecodeError:
                pass

        return None

    def _interpretar_score(self, score: float) -> str:
        """Interpreta el score de sesgo en lenguaje natural."""
        if score < 0.2:
            return "La hipotesis muestra bajo nivel de sesgo cognitivo. El proceso de razonamiento parece relativamente equilibrado."
        elif score < 0.4:
            return "Se detectan sesgos leves. Se recomienda verificar la evidencia contraria antes de aceptar."
        elif score < 0.6:
            return "Sesgos moderados detectados. La hipotesis debe revisarse con escepticismo saludable."
        elif score < 0.8:
            return "Sesgos significativos. El razonamiento esta claramente distorsionado. No recomendable aceptar sin revision profunda."
        else:
            return "Sesgos graves. La hipotesis es altamente sospechosa de distorsion cognitiva. Rechazo recomendado."



# ============================================================================
# COORDINADOR DE VALIDACION (Integracion Dual)
# ============================================================================

class CoordinadorValidacion:
    """
    Coordina la validacion dual: Agente Cientifico + Agente Esceptico.

    Produce un veredicto integrado basado en las reglas:
    - Si Cientifico dice "refutada" + Esceptico detecta sesgos altos   -> DESCARTAR
    - Si Cientifico dice "confirmada" + Esceptico detecta sesgos bajos -> ACEPTAR
    - Si Cientifico dice "inconclusa"                                  -> NECESITA_MAS_EVIDENCIA
    - Si hay DISCREPANCIA significativa                                -> REVISION_MANUAL

    Attributes:
        agente_cientifico: Instancia de AgenteCientifico.
        agente_esceptico: Instancia de AgenteEsceptico.
        logger: Logger para seguimiento.
    """

    # Umbrales para decision integrada
    UMBRAL_SESGO_ALTO: float = 0.6
    UMBRAL_SESGO_BAJO: float = 0.3
    UMBRAL_CONFIANZA_MINIMA: float = 0.5

    def __init__(
        self,
        agente_cientifico: AgenteCientifico = None,
        agente_esceptico: AgenteEsceptico = None,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        """
        Inicializa el coordinador con ambos agentes.

        Args:
            agente_cientifico: Agente que aplica refutacion popperiana.
            agente_esceptico: Agente que cuestiona sesgos.
            logger: Logger opcional.
        """
        if agente_cientifico is None:
            agente_cientifico = AgenteCientifico(config={})
        if agente_esceptico is None:
            agente_esceptico = AgenteEsceptico(config={})
        self.agente_cientifico = agente_cientifico
        self.agente_esceptico = agente_esceptico
        self.logger = logger or logging.getLogger(self.__class__.__name__)

    def validar(self, hipotesis: Hipotesis) -> Dict[str, Any]:
        """
        Ejecuta ambos agentes (simulando paralelismo) y produce veredicto integrado.

        El flujo:
        1. Ejecuta AgenteCientifico.refutar_hipotesis()
        2. Ejecuta AgenteEsceptico.cuestionar_hipotesis()
        3. Integra resultados segun las reglas de decision
        4. Genera recomendacion final

        Args:
            hipotesis: Hipotesis a validar.

        Returns:
            Dict con:
                - veredicto_final: ACEPTAR / DESCARTAR / NECESITA_MAS_EVIDENCIA / REVISION_MANUAL
                - confianza: nivel de confianza global (0.0 - 1.0)
                - razonamiento_cientifico: resultado del agente cientifico
                - evaluacion_sesgos: resultado del agente esceptico
                - recomendacion: texto de recomendacion
                - metadatos: informacion del proceso
        """
        self.logger.info("[Coordinador] Iniciando validacion dual de: %s", hipotesis.texto[:80])

        # --- Ejecucion de ambos agentes ---
        # Nota: usamos ThreadPoolExecutor para simular paralelismo.
        # En produccion, si los agentes hacen I/O con LLM, el paralelismo real ayuda.

        resultado_cientifico: Optional[ResultadoValidacion] = None
        resultado_esceptico: Optional[Dict[str, Any]] = None
        error_cientifico: Optional[str] = None
        error_esceptico: Optional[str] = None

        try:
            resultado_cientifico = self.agente_cientifico.refutar_hipotesis(hipotesis)
        except Exception as exc:
            error_cientifico = str(exc)
            self.logger.error("[Coordinador] Error en AgenteCientifico: %s", exc)

        try:
            resultado_esceptico = self.agente_esceptico.cuestionar_hipotesis(hipotesis)
        except Exception as exc:
            error_esceptico = str(exc)
            self.logger.error("[Coordinador] Error en AgenteEsceptico: %s", exc)

        # --- Fallback si un agente fallo ---
        if resultado_cientifico is None:
            self.logger.warning("[Coordinador] AgenteCientifico fallo, usando fallback.")
            resultado_cientifico = self._fallback_cientifico(hipotesis, error_cientifico)

        if resultado_esceptico is None:
            self.logger.warning("[Coordinador] AgenteEsceptico fallo, usando fallback.")
            resultado_esceptico = self._fallback_esceptico(hipotesis, error_esceptico)

        # --- Integracion de veredictos ---
        veredicto_final, confianza_final, recomendacion = self._integrar_veredictos(
            resultado_cientifico, resultado_esceptico
        )

        self.logger.info(
            "[Coordinador] Veredicto final: %s | Confianza: %.2f",
            veredicto_final.value,
            confianza_final,
        )

        return {
            "veredicto_final": veredicto_final.value,
            "confianza": round(confianza_final, 3),
            "razonamiento_cientifico": {
                "veredicto": resultado_cientifico.veredicto.value,
                "confianza": resultado_cientifico.confianza,
                "razonamiento": resultado_cientifico.razonamiento,
                "supuestos_identificados": resultado_cientifico.supuestos_identificados,
                "falacias_detectadas": resultado_cientifico.falacias_detectadas,
                "hipotesis_alternativas": resultado_cientifico.hipotesis_alternativas,
                "muestra_representativa": resultado_cientifico.muestra_representativa,
                "metadatos": resultado_cientifico.metadatos,
            },
            "evaluacion_sesgos": resultado_esceptico,
            "recomendacion": recomendacion,
            "metadatos": {
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "error_cientifico": error_cientifico,
                "error_esceptico": error_esceptico,
                "hipotesis_texto": hipotesis.texto,
                "hipotesis_autor": hipotesis.autor,
            },
        }

    def comparar_validaciones(self, h1: Hipotesis, h2: Hipotesis) -> Dict[str, Any]:
        """
        Compara dos hipotesis y recomienda cual es mas robusta cientificamente.

        Evalua:
        - Fortaleza del razonamiento cientifico
        - Ausencia de sesgos
        - Calidad de evidencia
        - Falsabilidad

        Args:
            h1: Primera hipotesis.
            h2: Segunda hipotesis.

        Returns:
            Dict con comparacion y recomendacion.
        """
        self.logger.info("[Coordinador] Comparando dos hipotesis.")

        resultado1 = self.validar(h1)
        resultado2 = self.validar(h2)

        # Extraer metricas comparables
        score1 = self._calcular_score_robustez(resultado1)
        score2 = self._calcular_score_robustez(resultado2)

        # Determinar ganadora
        if score1 > score2 + 0.15:
            ganadora = "h1"
            justificacion = (
                f"La Hipotesis 1 es significativamente mas robusta "
                f"(score: {score1:.2f} vs {score2:.2f})."
            )
        elif score2 > score1 + 0.15:
            ganadora = "h2"
            justificacion = (
                f"La Hipotesis 2 es significativamente mas robusta "
                f"(score: {score2:.2f} vs {score1:.2f})."
            )
        else:
            ganadora = "empate"
            justificacion = (
                f"Ambas hipotesis tienen similar robustez "
                f"(score: {score1:.2f} vs {score2:.2f}). "
                f"Se requiere revision manual."
            )

        return {
            "hipotesis_ganadora": ganadora,
            "justificacion": justificacion,
            "score_h1": round(score1, 3),
            "score_h2": round(score2, 3),
            "veredicto_h1": resultado1["veredicto_final"],
            "veredicto_h2": resultado2["veredicto_final"],
            "detalle_h1": resultado1,
            "detalle_h2": resultado2,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }

    def _integrar_veredictos(
        self,
        cientifico: ResultadoValidacion,
        esceptico: Dict[str, Any],
    ) -> Tuple[VeredictoFinal, float, str]:
        """
        Integra los veredictos de ambos agentes segun las reglas de decision.

        Reglas:
        1. Cientifico REFUTADA + Esceptico sesgo ALTO  (>0.6)  -> DESCARTAR
        2. Cientifico REFUTADA + Esceptico sesgo BAJO  (<0.3)  -> REVISION_MANUAL
        3. Cientifico CONFIRMADA + Esceptico sesgo BAJO (<0.3) -> ACEPTAR
        4. Cientifico CONFIRMADA + Esceptico sesgo ALTO (>0.6) -> REVISION_MANUAL
        5. Cientifico INCONCLUSA                                 -> NECESITA_MAS_EVIDENCIA
        6. Cualquier otra combinacion con discrepancia           -> REVISION_MANUAL

        Args:
            cientifico: Resultado del Agente Cientifico.
            esceptico: Resultado del Agente Esceptico.

        Returns:
            Tupla: (veredicto_final, confianza_global, recomendacion).
        """
        score_sesgo = esceptico.get("score_global", 0.0)
        veredicto_c = cientifico.veredicto
        confianza_c = cientifico.confianza

        # Regla 5: Inconclusa siempre necesita mas evidencia
        if veredicto_c == VeredictoCientifico.INCONCLUSA:
            # La confianza refleja la incertidumbre inherente: falta información
            # para cualquier veredicto firme. Se conserva confianza_c (=0.5).
            confianza = confianza_c
            recomendacion = (
                "El analisis cientifico es INCONCLUSO. No hay suficiente evidencia "
                "para confirmar ni refutar la hipotesis. RECOMENDACION: Diseñar "
                "experimentos controlados que puedan refutar la hipotesis de manera "
                "rigurosa. Recolectar mas datos representativos."
            )
            return VeredictoFinal.NECESITA_MAS_EVIDENCIA, round(confianza, 3), recomendacion

        # Regla 1: Refutada + sesgo alto -> DESCARTAR
        # Convergencia negativa: ambos agentes concuerdan en que la hipotesis es debil.
        # La confianza global = confianza del agente cientifico (sin penalizacion
        # por sesgo, porque el sesgo CONFIRMA la debilidad, no la contradice).
        if veredicto_c == VeredictoCientifico.REFUTADA and score_sesgo > self.UMBRAL_SESGO_ALTO:
            confianza = confianza_c
            recomendacion = (
                "DESCARTAR: La hipotesis ha sido refutada cientificamente Y presenta "
                f"altos niveles de sesgo cognitivo (score: {score_sesgo:.2f}). "
                "Doble confirmacion de debilidad. No debe considerarse valida."
            )
            return VeredictoFinal.DESCARTAR, round(confianza, 3), recomendacion

        # Regla 2: Refutada + sesgo bajo -> REVISION_MANUAL
        # Discrepancia: el agente cientifico refuta pero el escéptico no detecta
        # sesgos que confirmen la debilidad. La refutacion podria ser tecnica y
        # correcta, pero sin convergencia con el analisis de sesgos, el sistema
        # no puede descartar automaticamente. La confianza se reduce proporcional-
        # mente al sesgo detectado (menos sesgo = mas incertidumbre de convergencia).
        if veredicto_c == VeredictoCientifico.REFUTADA and score_sesgo < self.UMBRAL_SESGO_BAJO:
            confianza = confianza_c * (1.0 - score_sesgo)
            recomendacion = (
                "REVISION MANUAL: El agente cientifico refuto la hipotesis, pero el "
                "agente esceptico no detecto sesgos significativos. Esto sugiere que "
                "la refutacion podria basarse en detalles tecnicos que requieren "
                "evaluacion humana experta."
            )
            return VeredictoFinal.REVISION_MANUAL, round(confianza, 3), recomendacion

        # Regla 3: Confirmada + sesgo bajo -> ACEPTAR
        # Convergencia positiva: el agente cientifico confirma y el escéptico
        # no detecta sesgos significativos. La confianza global = confianza del
        # agente cientifico (sin penalizacion, proceso limpio).
        if veredicto_c == VeredictoCientifico.CONFIRMADA and score_sesgo < self.UMBRAL_SESGO_BAJO:
            confianza = confianza_c
            recomendacion = (
                "ACEPTAR PROVISIONALMENTE: La hipotesis resistio los intentos de "
                f"refutacion (confianza: {confianza_c:.2f}) y presenta bajos niveles "
                f"de sesgo (score: {score_sesgo:.2f}). Es aceptable trabajar con ella "
                "de forma provisional. NOTA: Toda confirmacion cientifica es revisable."
            )
            return VeredictoFinal.ACEPTAR, round(confianza, 3), recomendacion

        # Regla 4: Confirmada + sesgo alto -> REVISION_MANUAL
        # Discrepancia: el agente cientifico confirma pero el escéptico detecta
        # sesgos significativos. La confirmacion podria ser artificial debido a
        # sesgos en el diseno o seleccion de evidencia. La confianza se reduce
        # proporcionalmente al sesgo detectado.
        if veredicto_c == VeredictoCientifico.CONFIRMADA and score_sesgo > self.UMBRAL_SESGO_ALTO:
            confianza = confianza_c * (1.0 - score_sesgo)
            recomendacion = (
                "REVISION MANUAL: La hipotesis parece confirmada cientificamente, pero "
                f"presenta SESGOS SIGNIFICATIVOS (score: {score_sesgo:.2f}). Es posible "
                "que la 'confirmacion' sea artificial debido a sesgos en el diseno del "
                "estudio o en la seleccion de evidencia. Requiere auditoria experta."
            )
            return VeredictoFinal.REVISION_MANUAL, round(confianza, 3), recomendacion

        # Casos intermedios (discrepancia) -> REVISION_MANUAL
        # Ni convergencia positiva ni negativa clara. La confianza se reduce
        # proporcionalmente al sesgo detectado.
        confianza = confianza_c * (1.0 - score_sesgo)
        recomendacion = (
            "REVISION MANUAL: Los agentes no alcanzan consenso claro. "
            f"Veredicto cientifico: {veredicto_c.value}, "
            f"Score de sesgo: {score_sesgo:.2f}. "
            "La decision requiere juicio humano experto."
        )
        return VeredictoFinal.REVISION_MANUAL, round(confianza, 3), recomendacion

    def _calcular_score_robustez(self, resultado_validacion: Dict[str, Any]) -> float:
        """
        Calcula un score unico de robustez cientifica para comparacion.

        Formula ponderada:
        - Veredicto final: 40% (ACEPTAR=1.0, DESCARTAR=0.0, otros=0.5)
        - Confianza: 30%
        - Inverso del sesgo: 30%

        Args:
            resultado_validacion: Resultado completo de validar().

        Returns:
            float: Score de robustez (0.0 - 1.0).
        """
        veredicto = resultado_validacion.get("veredicto_final", "")
        confianza = resultado_validacion.get("confianza", 0.0)
        eval_sesgos = resultado_validacion.get("evaluacion_sesgos", {})
        score_sesgo = eval_sesgos.get("score_global", 0.5)

        # Score del veredicto
        if veredicto == VeredictoFinal.ACEPTAR.value:
            score_veredicto = 1.0
        elif veredicto == VeredictoFinal.DESCARTAR.value:
            score_veredicto = 0.0
        else:
            score_veredicto = 0.5

        # Score inverso de sesgo (menos sesgo = mejor)
        score_inverso_sesgo = 1.0 - score_sesgo

        # Formula ponderada
        robustez = (
            score_veredicto * 0.4
            + confianza * 0.3
            + score_inverso_sesgo * 0.3
        )

        return round(max(0.0, min(1.0, robustez)), 3)

    def _fallback_cientifico(
        self,
        hipotesis: Hipotesis,
        error: Optional[str],
    ) -> ResultadoValidacion:
        """
        Genera un resultado cientifico de fallback ante fallo del agente.

        Args:
            hipotesis: Hipotesis evaluada.
            error: Mensaje de error (si hubo).

        Returns:
            ResultadoValidacion con veredicto inconcluso por defecto.
        """
        supuestos = extraer_supuestos(hipotesis.texto)
        return ResultadoValidacion(
            veredicto=VeredictoCientifico.INCONCLUSA,
            confianza=0.3,
            razonamiento=(
                f"[FALLBACK] El Agente Cientifico no pudo completar su analisis. "
                f"Error: {error or 'desconocido'}. "
                f"Se aplico evaluacion basica. Supuestos identificados: {len(supuestos)}. "
                "Se recomienda revision manual."
            ),
            supuestos_identificados=supuestos,
            recomendacion="Revision manual requerida debido a fallo del sistema.",
            metadatos={"fallback": True, "error": error},
        )

    def _fallback_esceptico(
        self,
        hipotesis: Hipotesis,
        error: Optional[str],
    ) -> Dict[str, Any]:
        """
        Genera un resultado esceptico de fallback ante fallo del agente.

        Args:
            hipotesis: Hipotesis evaluada.
            error: Mensaje de error (si hubo).

        Returns:
            Dict con evaluacion de sesgos por defecto (neutral).
        """
        return {
            "evaluaciones": {},
            "score_global": 0.5,
            "interpretacion": (
                f"[FALLBACK] El Agente Esceptico no pudo completar su analisis. "
                f"Error: {error or 'desconocido'}. "
                "Score neutral por defecto. Se recomienda revision manual."
            ),
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }


# ============================================================================
# FUNCIONES DE UTILIDAD Y FACILITADORES
# ============================================================================

def crear_configuracion(
    llm_api_url: str = "",
    llm_api_key: Optional[str] = None,
    llm_model: str = "gpt-4o-mini",
) -> Dict[str, Any]:
    """
    Crea un diccionario de configuracion estandar para los agentes.

    Args:
        llm_api_url: URL base de la API del LLM (ej: https://api.openai.com/v1).
        llm_api_key: Clave de API (opcional).
        llm_model: Nombre del modelo (default: gpt-4o-mini).

    Returns:
        Dict con la configuracion formateada.
    """
    return {
        "llm_api_url": llm_api_url,
        "llm_api_key": llm_api_key,
        "llm_model": llm_model,
    }


def inicializar_sistema(config: Dict[str, Any]) -> CoordinadorValidacion:
    """
    Inicializa el sistema VEO completo con un solo llamado.

    Args:
        config: Configuracion del sistema (ver crear_configuracion).

    Returns:
        CoordinadorValidacion listo para usar.
    """
    logger = logging.getLogger("VEO")
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            "%(asctime)s [%(name)s] %(levelname)s: %(message)s"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)

    agente_cientifico = AgenteCientifico(config, logger)
    agente_esceptico = AgenteEsceptico(config, logger)
    coordinador = CoordinadorValidacion(agente_cientifico, agente_esceptico, logger)

    return coordinador


# ============================================================================
# EJECUCION DE DEMOSTRACION (solo si se ejecuta directamente)
# ============================================================================


# ============================================================================
# VEO v2: Funciones de integracion con hermes_commander / veo_core
# ============================================================================
# NOTA: Estas funciones fueron anadidas en la migracion de VEO v1 a VEO v2.
# Proporcionan observabilidad, auditoria y health-checks sin modificar
# la logica existente del sistema de validacion dual.
# ============================================================================

import time as _time

# --- Estado observable del modulo (VEO v2) ---
_agent_execution_count: int = 0
_agent_last_execution_time: float = 0.0
_agent_validation_results: list = []


def get_trust_score() -> float:
    """
    VEO v2: Devuelve el score de confianza del agente cientifico.

    Calcula un score basado en la relacion entre confirmaciones y refutaciones
    historicas registradas por el modulo de auditoria.

    Returns:
        float: Score de confianza en [0.0, 1.0].
               1.0 = maxima confianza, 0.0 = sin confianza.
    """
    global _agent_validation_results
    if not _agent_validation_results:
        return 0.75  # Valor por defecto para agente no calibrado

    confirmaciones = sum(
        1 for r in _agent_validation_results
        if r.get("veredicto") == "CONFIRMADA"
    )
    refutaciones = sum(
        1 for r in _agent_validation_results
        if r.get("veredicto") == "REFUTADA"
    )
    total = confirmaciones + refutaciones
    if total == 0:
        return 0.5

    # Penalizar ligeramente las refutaciones
    score = confirmaciones / (confirmaciones + refutaciones * 1.2 + 1)
    return round(min(max(score, 0.0), 1.0), 4)


def get_last_execution_time() -> str:
    """
    VEO v2: Devuelve el timestamp ISO de la ultima ejecucion del agente.

    Returns:
        str: Timestamp en formato ISO 8601, o cadena vacia si no ha ejecutado.
    """
    global _agent_last_execution_time
    if _agent_last_execution_time == 0.0:
        return ""
    return _time.strftime("%Y-%m-%dT%H:%M:%SZ", _time.gmtime(_agent_last_execution_time))


def get_health_status() -> dict:
    """
    VEO v2: Devuelve el estado de salud del modulo de validacion cientifica.

    Evalua:
        - Disponibilidad de LLM
        - Ejecuciones recientes
        - Tasa de exito en validaciones

    Returns:
        dict: {"status": "healthy|degraded|unhealthy", "score": 0-100}
    """
    global _agent_last_execution_time, _agent_validation_results

    score = 100
    status = "healthy"

    # Penalizar si no ha ejecutado recientemente (> 24h)
    tiempo_actual = _time.time()
    if _agent_last_execution_time > 0:
        horas_desde_ejecucion = (tiempo_actual - _agent_last_execution_time) / 3600
        if horas_desde_ejecucion > 24:
            score -= 30
        elif horas_desde_ejecucion > 12:
            score -= 15

    # Penalizar por baja tasa de exito
    if _agent_validation_results:
        trust = get_trust_score()
        if trust < 0.3:
            score -= 40
        elif trust < 0.5:
            score -= 20

    # Penalizar por falta de ejecuciones
    if _agent_execution_count == 0:
        score -= 20

    score = max(0, min(100, score))

    if score >= 80:
        status = "healthy"
    elif score >= 50:
        status = "degraded"
    else:
        status = "unhealthy"

    return {"status": status, "score": score}


def _log_audit_validation(
    hipotesis_texto: str,
    veredicto: str,
    confianza: float,
    sesgo_score: float = 0.0,
) -> None:
    """
    VEO v2: Registra una entrada de auditoria para cada validacion realizada.

    La auditoria permite trazabilidad completa de las decisiones del sistema
    y alimenta el trust score del agente.

    Args:
        hipotesis_texto: Texto resumido de la hipotesis validada.
        veredicto: Veredicto emitido (CONFIRMADA/REFUTADA/INCONCLUSA).
        confianza: Nivel de confianza en el veredicto [0.0, 1.0].
        sesgo_score: Score de sesgo detectado [0.0, 1.0].
    """
    global _agent_execution_count, _agent_last_execution_time, _agent_validation_results

    _agent_execution_count += 1
    _agent_last_execution_time = _time.time()

    entry = {
        "timestamp": get_last_execution_time(),
        "hipotesis": hipotesis_texto[:200] if hipotesis_texto else "",
        "veredicto": veredicto,
        "confianza": round(confianza, 4),
        "sesgo_score": round(sesgo_score, 4),
        "execution_count": _agent_execution_count,
    }
    _agent_validation_results.append(entry)

    # Mantener solo las ultimas 1000 entradas para evitar crecimiento ilimitado
    if len(_agent_validation_results) > 1000:
        _agent_validation_results = _agent_validation_results[-1000:]

if __name__ == "__main__":
    # Configurar logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )
    logger_demo = logging.getLogger("SOIS-Demo")

    logger_demo.info("=" * 60)
    logger_demo.info("VEO: Sistema de Validacion Dual")
    logger_demo.info("=" * 60)

    # Configuracion (sin LLM para demo - funciona en modo heuristico)
    config_demo = crear_configuracion()

    # Inicializar sistema
    sois = inicializar_sistema(config_demo)

    # Hipotesis de ejemplo 1: Correlacion espuria
    h1 = Hipotesis(
        texto=(
            "El aumento de ventas de helado causa un incremento de ahogamientos en la playa, "
            "por lo tanto las heladerias deberian ser reguladas para reducir accidentes acuaticos."
        ),
        contexto="Analisis de politica publica basado en datos veraniegos.",
        autor="Ciudadano Concernido",
        evidencia_a_favor=[
            "Datos municipales: ventas de helado y rescates acuaticos suben 40% en julio-agosto",
            "Grafico de lineas que muestra ambas curvas ascendentes simultaneamente",
        ],
        evidencia_en_contra=[],
    )

    logger_demo.info("\n--- DEMO 1: Correlacion espuria ---")
    logger_demo.info("Hipotesis: %s", h1.texto)
    resultado1 = sois.validar(h1)
    logger_demo.info("Veredicto: %s", resultado1["veredicto_final"])
    logger_demo.info("Confianza: %.2f", resultado1["confianza"])
    logger_demo.info("Recomendacion: %s", resultado1["recomendacion"])
    logger_demo.info("Sesgos detectados (score): %.2f", resultado1["evaluacion_sesgos"]["score_global"])

    # Hipotesis de ejemplo 2: Generalizacion excesiva
    h2 = Hipotesis(
        texto=(
            "Todos los politicos son corruptos porque el alcalde de mi ciudad fue arrestado "
            "por desfalco el mes pasado."
        ),
        contexto="Debate ciudadano sobre politica local.",
        autor="Vecino Indignado",
        evidencia_a_favor=[
            "El alcalde fue arrestado por desfalco de fondos publicos",
            "Noticia del arresto publicada en el diario local",
        ],
        evidencia_en_contra=[],
    )

    logger_demo.info("\n--- DEMO 2: Generalizacion excesiva ---")
    logger_demo.info("Hipotesis: %s", h2.texto)
    resultado2 = sois.validar(h2)
    logger_demo.info("Veredicto: %s", resultado2["veredicto_final"])
    logger_demo.info("Confianza: %.2f", resultado2["confianza"])
    logger_demo.info("Recomendacion: %s", resultado2["recomendacion"])

    # Comparacion de hipotesis
    logger_demo.info("\n--- COMPARACION ---")
    comparacion = sois.comparar_validaciones(h1, h2)
    logger_demo.info("Ganadora: %s", comparacion["hipotesis_ganadora"])
    logger_demo.info("Justificacion: %s", comparacion["justificacion"])

    logger_demo.info("\n" + "=" * 60)
    logger_demo.info("Demo completada. El sistema funciona en modo heuristico.")
    logger_demo.info("Conecta un LLM para validaciones mas profundas.")
    logger_demo.info("=" * 60)
