# -*- coding: utf-8 -*-
"""
================================================================================
VEO: Diario de Descubrimientos Semanal
================================================================================
Programa VEO (Vigilancia de Emergencias Observables).
Detecta que esta cambiando.

"VEO es una plataforma de inteligencia artificial cooperativa destinada a
detectar cambios emergentes en la realidad mediante el analisis continuo de
senales debiles, relaciones semanticas y conocimiento distribuido, generando
hipotesis explicables que ayuden a los analistas humanos a comprender sistemas
complejos bajo incertidumbre."

Este modulo implementa el Diario de Descubrimientos Semanal del sistema VEO.
Recopila, analiza y genera informes estructurados sobre la actividad semanal
del sistema, incluyendo hipotesis generadas, validadas, refutadas, tendencias
detectadas y lecciones aprendidas acumulativas.

Dependencias: numpy (para deteccion de anomalias), datetime, json, statistics
================================================================================
"""

from __future__ import annotations

import json
import re
import statistics
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from typing import (
    Any,
    Dict,
    List,
    Optional,
    Protocol,
    Tuple,
    runtime_checkable,
)

import numpy as np


# =============================================================================
# EXCEPCIONES CUSTOM
# =============================================================================

class DiarioError(Exception):
    """Excepcion base para errores del diario de descubrimientos."""


class SemanaInvalidaError(DiarioError):
    """Formato de semana ISO invalido."""


class DatosInsuficientesError(DiarioError):
    """No hay datos suficientes para realizar el analisis solicitado."""


# =============================================================================
# PROTOCOLOS (interfaces para inyeccion de dependencias)
# =============================================================================

@runtime_checkable
class BaseDatos(Protocol):
    """Protocolo para la capa de persistencia."""

    def guardar(self, coleccion: str, datos: Dict[str, Any]) -> str: ...
    def buscar(self, coleccion: str, filtros: Dict[str, Any]) -> List[Dict[str, Any]]: ...
    def obtener_por_id(self, coleccion: str, doc_id: str) -> Optional[Dict[str, Any]]: ...
    def actualizar(self, coleccion: str, doc_id: str, datos: Dict[str, Any]) -> bool: ...
    def contar(self, coleccion: str, filtros: Optional[Dict[str, Any]] = None) -> int: ...


@runtime_checkable
class Logger(Protocol):
    """Protocolo para el sistema de logging."""

    def debug(self, mensaje: str) -> None: ...
    def info(self, mensaje: str) -> None: ...
    def warning(self, mensaje: str) -> None: ...
    def error(self, mensaje: str) -> None: ...


# =============================================================================
# ESTRUCTURAS DE DATOS
# =============================================================================

@dataclass
class Descubrimiento:
    """
    Representa un descubrimiento o hallazgo del sistema en una semana.

    Atributos:
        semana: Identificador ISO de la semana (ej: "2026-W23").
        periodo_inicio: Fecha de inicio de la semana.
        periodo_fin: Fecha de fin de la semana.
        hipotesis_nuevas: Lista de nuevas hipotesis creadas.
        hipotesis_confirmadas: Hipotesis validadas por evidencia.
        hipotesis_refutadas: Hipotesis rechazadas por el agente cientifico.
        tendencias_detectadas: Cambios en tendencias observados.
        cambios_narrativa: Cambios de direccion narrativa identificados.
        predicciones_acertadas: Conteo de predicciones correctas del mercado.
        predicciones_falladas: Conteo de predicciones incorrectas.
        nuevas_relaciones_causales: Relaciones causales descubiertas.
        confianza_promedio: Nivel de confianza promedio del sistema [0, 1].
        nivel_actividad: Indice de actividad semanal [0, 1].
        metricas_crudas: Datos numericos brutos para series temporales.
        lecciones_aprendidas: Lista de lecciones extraidas esta semana.
        markdown_generado: Version en markdown del informe.
        timestamp_generacion: Instante de generacion del informe.
    """
    semana: str
    periodo_inicio: datetime
    periodo_fin: datetime
    hipotesis_nuevas: List[Dict[str, Any]] = field(default_factory=list)
    hipotesis_confirmadas: List[Dict[str, Any]] = field(default_factory=list)
    hipotesis_refutadas: List[Dict[str, Any]] = field(default_factory=list)
    tendencias_detectadas: List[Dict[str, Any]] = field(default_factory=list)
    cambios_narrativa: List[Dict[str, Any]] = field(default_factory=list)
    predicciones_acertadas: int = 0
    predicciones_falladas: int = 0
    nuevas_relaciones_causales: List[Dict[str, Any]] = field(default_factory=list)
    confianza_promedio: float = 0.0
    nivel_actividad: float = 0.0
    metricas_crudas: Dict[str, Any] = field(default_factory=dict)
    lecciones_aprendidas: List[str] = field(default_factory=list)
    markdown_generado: str = ""
    timestamp_generacion: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Serializa el descubrimiento a diccionario JSON-friendly."""
        return {
            "semana": self.semana,
            "periodo_inicio": self.periodo_inicio.isoformat(),
            "periodo_fin": self.periodo_fin.isoformat(),
            "hipotesis_nuevas": self.hipotesis_nuevas,
            "hipotesis_confirmadas": self.hipotesis_confirmadas,
            "hipotesis_refutadas": self.hipotesis_refutadas,
            "tendencias_detectadas": self.tendencias_detectadas,
            "cambios_narrativa": self.cambios_narrativa,
            "predicciones_acertadas": self.predicciones_acertadas,
            "predicciones_falladas": self.predicciones_falladas,
            "nuevas_relaciones_causales": self.nuevas_relaciones_causales,
            "confianza_promedio": round(self.confianza_promedio, 4),
            "nivel_actividad": round(self.nivel_actividad, 4),
            "metricas_crudas": self.metricas_crudas,
            "lecciones_aprendidas": self.lecciones_aprendidas,
            "markdown_generado": self.markdown_generado,
            "timestamp_generacion": self.timestamp_generacion.isoformat(),
        }


@dataclass
class Aprendizaje:
    """
    Representa una leccion aprendida por el sistema, almacenada en memoria.

    Atributos:
        id: Identificador unico.
        leccion: Texto descriptivo de la leccion.
        categoria: Categoria tematica (ej: "causalidad", "prediccion", "tendencia").
        confianza: Nivel de confianza [0, 1] basado en validaciones posteriores.
        conteo_usos: Numero de veces que se ha aplicado esta leccion.
        validaciones_positivas: Veces que se confirmo la leccion.
        validaciones_negativas: Veces que se refuto la leccion.
        semana_origen: Semana ISO en que se aprendio.
        fecha_creacion: Instante de creacion.
        activo: Si la leccion sigue siendo considerada valida.
    """
    id: str
    leccion: str
    categoria: str
    confianza: float = 0.5
    conteo_usos: int = 0
    validaciones_positivas: int = 0
    validaciones_negativas: int = 0
    semana_origen: str = ""
    fecha_creacion: datetime = field(default_factory=datetime.now)
    activo: bool = True

    def to_dict(self) -> Dict[str, Any]:
        """Serializa el aprendizaje a diccionario."""
        return {
            "id": self.id,
            "leccion": self.leccion,
            "categoria": self.categoria,
            "confianza": round(self.confianza, 4),
            "conteo_usos": self.conteo_usos,
            "validaciones_positivas": self.validaciones_positivas,
            "validaciones_negativas": self.validaciones_negativas,
            "semana_origen": self.semana_origen,
            "fecha_creacion": self.fecha_creacion.isoformat(),
            "activo": self.activo,
        }


# =============================================================================
# DIARIO DE DESCUBRIMIENTOS
# =============================================================================

class DiarioDescubrimientos:
    """
    Diario de Descubrimientos Semanal del programa VEO.

    Recopila, analiza y genera informes estructurados sobre la actividad
    semanal del sistema. Su funcion es proporcionar visibilidad al analista
    humano sobre que esta descubriendo el sistema, que hipotesis estan
    ganando o perdiendo fuerza, y que patrones emergen del conocimiento
    acumulado.

    Funcionalidades principales:
        - Generacion automatica de informes semanales (JSON + Markdown).
        - Comparacion de semanas para identificar cambios.
        - Serie temporal de metricas de rendimiento.
        - Deteccion de patrones recurrentes.
        - Resumen ejecutivo con el estado actual.

    Ejemplo:
        >>> diario = DiarioDescubrimientos(db, logger)
        >>> informe = diario.generar_informe_semanal("2026-W23")
        >>> print(informe.markdown_generado)
        >>> evolucion = diario.evolucion_temporal(n_semanas=8)
    """

    COLECCION_DESCUBRIMIENTOS: str = "descubrimientos_semanales"
    COLECCION_APRENDIZAJES: str = "aprendizajes_sistema"
    COLECCION_HIPOTESIS: str = "hipotesis"
    COLECCION_TENDENCIAS: str = "tendencias"
    COLECCION_PREDICCIONES: str = "predicciones"
    COLECCION_RELACIONES: str = "relaciones_causales"
    VERSION: str = "1.0.0"

    def __init__(self, db: BaseDatos, logger: Logger) -> None:
        """
        Inicializa el diario de descubrimientos.

        Args:
            db: Capa de persistencia para consultar datos del sistema.
            logger: Sistema de logging para auditoria.
        """
        self._db = db
        self._logger = logger
        self._memoria = MemoriaSistema(db)

        self._logger.info(
            f"[VEO] DiarioDescubrimientos v{self.VERSION} inicializado."
        )

    # -------------------------------------------------------------------------
    # Informe Semanal Principal
    # -------------------------------------------------------------------------

    def generar_informe_semanal(
        self,
        semana: Optional[str] = None,
    ) -> Descubrimiento:
        """
        Genera el informe semanal automatico de descubrimientos.

        Recopila datos de multiples colecciones de la base de datos:
            1. Hipotesis nuevas creadas en la semana.
            2. Hipotesis confirmadas (por validacion).
            3. Hipotesis refutadas (por agente cientifico).
            4. Tendencias detectadas (por narrative_shift).
            5. Cambios de direccion narrativa.
            6. Predicciones acertadas/falladas del mercado.
            7. Nuevas relaciones causales descubiertas.

        Calcula confianza promedio y nivel de actividad del sistema.

        Args:
            semana: Semana ISO (ej: "2026-W23"). Si es None, usa la semana actual.

        Returns:
            Instancia de Descubrimiento con todos los datos recopilados.
            El atributo 'markdown_generado' contiene la version legible.

        Raises:
            SemanaInvalidaError: Si el formato de semana es incorrecto.
        """
        if semana is None:
            semana = semana_iso(datetime.now())

        if not _validar_formato_semana(semana):
            raise SemanaInvalidaError(
                f"Formato de semana invalido: '{semana}'. Use 'YYYY-WNN'."
            )

        inicio, fin = inicio_fin_semana(semana)

        self._logger.info(
            f"[VEO] Generando informe semanal {semana} "
            f"({inicio.date()} a {fin.date()})"
        )

        # 1. Hipotesis nuevas
        hipotesis_nuevas = self._db.buscar(
            self.COLECCION_HIPOTESIS,
            {"semana_creacion": semana}
        )

        # 2. Hipotesis confirmadas
        hipotesis_confirmadas = self._db.buscar(
            self.COLECCION_HIPOTESIS,
            {"estado": "confirmada", "semana_validacion": semana}
        )

        # 3. Hipotesis refutadas
        hipotesis_refutadas = self._db.buscar(
            self.COLECCION_HIPOTESIS,
            {"estado": "refutada", "semana_refutacion": semana}
        )

        # 4. Tendencias detectadas
        tendencias_detectadas = self._db.buscar(
            self.COLECCION_TENDENCIAS,
            {"semana": semana}
        )

        # 5. Cambios de narrativa (dentro de tendencias con tipo 'narrative_shift')
        cambios_narrativa = [
            t for t in tendencias_detectadas
            if t.get("tipo") == "narrative_shift" or t.get("cambio_narrativa", False)
        ]

        # 6. Predicciones
        predicciones = self._db.buscar(
            self.COLECCION_PREDICCIONES,
            {"semana": semana}
        )
        predicciones_acertadas = sum(
            1 for p in predicciones if p.get("resultado") == "acertada"
        )
        predicciones_falladas = sum(
            1 for p in predicciones if p.get("resultado") == "fallada"
        )

        # 7. Nuevas relaciones causales
        nuevas_relaciones = self._db.buscar(
            self.COLECCION_RELACIONES,
            {"semana_descubrimiento": semana}
        )

        # Calcular metricas agregadas
        todas_hipotesis = hipotesis_nuevas + hipotesis_confirmadas + hipotesis_refutadas
        if todas_hipotesis:
            confianzas = [
                h.get("confianza", 0.5) for h in todas_hipotesis
                if isinstance(h.get("confianza"), (int, float))
            ]
            confianza_promedio = statistics.mean(confianzas) if confianzas else 0.5
        else:
            confianza_promedio = 0.5

        # Nivel de actividad: normalizado [0, 1] basado en volumen de eventos
        volumen_eventos = (
            len(hipotesis_nuevas) * 2 +
            len(hipotesis_confirmadas) * 3 +
            len(hipotesis_refutadas) * 1 +
            len(tendencias_detectadas) * 2 +
            len(cambios_narrativa) * 3 +
            predicciones_acertadas * 1 +
            predicciones_falladas * 1 +
            len(nuevas_relaciones) * 2
        )
        nivel_actividad = min(1.0, volumen_eventos / 50.0)  # Normalizar a 50 como max

        # Extraer lecciones automaticas
        lecciones = self._extraer_lecciones_automaticas(
            hipotesis_confirmadas=hipotesis_confirmadas,
            hipotesis_refutadas=hipotesis_refutadas,
            predicciones_acertadas=predicciones_acertadas,
            predicciones_falladas=predicciones_falladas,
            tendencias=tendencias_detectadas,
        )

        # Guardar lecciones en memoria
        for leccion_texto, categoria in lecciones:
            self._memoria.guardar_aprendizaje(
                leccion=leccion_texto,
                categoria=categoria,
                confianza=confianza_promedio,
            )

        # Construir metricas crudas para series temporales
        metricas_crudas = {
            "n_hipotesis_nuevas": len(hipotesis_nuevas),
            "n_hipotesis_confirmadas": len(hipotesis_confirmadas),
            "n_hipotesis_refutadas": len(hipotesis_refutadas),
            "n_tendencias": len(tendencias_detectadas),
            "n_cambios_narrativa": len(cambios_narrativa),
            "predicciones_acertadas": predicciones_acertadas,
            "predicciones_falladas": predicciones_falladas,
            "n_relaciones_nuevas": len(nuevas_relaciones),
            "volumen_total": volumen_eventos,
        }

        # Crear el descubrimiento
        descubrimiento = Descubrimiento(
            semana=semana,
            periodo_inicio=inicio,
            periodo_fin=fin,
            hipotesis_nuevas=hipotesis_nuevas,
            hipotesis_confirmadas=hipotesis_confirmadas,
            hipotesis_refutadas=hipotesis_refutadas,
            tendencias_detectadas=tendencias_detectadas,
            cambios_narrativa=cambios_narrativa,
            predicciones_acertadas=predicciones_acertadas,
            predicciones_falladas=predicciones_falladas,
            nuevas_relaciones_causales=nuevas_relaciones,
            confianza_promedio=confianza_promedio,
            nivel_actividad=nivel_actividad,
            metricas_crudas=metricas_crudas,
            lecciones_aprendidas=[l[0] for l in lecciones],
        )

        # Generar markdown
        descubrimiento.markdown_generado = self._generar_markdown_informe(descubrimiento)

        # Persistir
        self._db.guardar(self.COLECCION_DESCUBRIMIENTOS, descubrimiento.to_dict())

        self._logger.info(
            f"[VEO] Informe semanal {semana} generado: "
            f"{len(hipotesis_nuevas)} hipotesis nuevas, "
            f"{len(hipotesis_confirmadas)} confirmadas, "
            f"{len(hipotesis_refutadas)} refutadas, "
            f"confianza={confianza_promedio:.3f}, actividad={nivel_actividad:.3f}"
        )

        return descubrimiento

    # -------------------------------------------------------------------------
    # Comparacion de Semanas
    # -------------------------------------------------------------------------

    def comparar_semanas(self, semana_a: str, semana_b: str) -> Dict[str, Any]:
        """
        Compara dos semanas para identificar cambios, tendencias y diferencias.

        Args:
            semana_a: Primera semana ISO (referencia).
            semana_b: Segunda semana ISO (comparacion).

        Returns:
            Diccionario con:
                - semana_a, semana_b: Identificadores.
                - metricas_a, metricas_b: Metricas de cada semana.
                - diferencias: Cambios absolutos y relativos por metrica.
                - conclusion: Interpretacion textual del cambio.
                - tendencia: Direccion general ("mejora", "degradacion", "estable").
                - alertas: Lista de alertas si hay cambios significativos.
        """
        if not (_validar_formato_semana(semana_a) and _validar_formato_semana(semana_b)):
            raise SemanaInvalidaError("Formato de semana invalido. Use 'YYYY-WNN'.")

        # Recuperar descubrimientos
        desc_a = self._recuperar_descubrimiento(semana_a)
        desc_b = self._recuperar_descubrimiento(semana_b)

        metricas_a = desc_a.metricas_crudas if desc_a else self._metricas_vacio()
        metricas_b = desc_b.metricas_crudas if desc_b else self._metricas_vacio()

        # Calcular diferencias
        diferencias: Dict[str, Dict[str, Any]] = {}
        metricas_clave = [
            "n_hipotesis_nuevas", "n_hipotesis_confirmadas",
            "n_hipotesis_refutadas", "n_tendencias",
            "n_cambios_narrativa", "predicciones_acertadas",
            "predicciones_falladas", "n_relaciones_nuevas",
            "volumen_total",
        ]

        for metrica in metricas_clave:
            val_a = metricas_a.get(metrica, 0)
            val_b = metricas_b.get(metrica, 0)
            diff = val_b - val_a
            pct = (diff / val_a * 100) if val_a > 0 else (100 if val_b > 0 else 0)
            diferencias[metrica] = {
                "semana_a": val_a,
                "semana_b": val_b,
                "diferencia_absoluta": diff,
                "diferencia_porcentual": round(pct, 2),
            }

        # Determinar tendencia general
        conf_a = desc_a.confianza_promedio if desc_a else 0.5
        conf_b = desc_b.confianza_promedio if desc_b else 0.5

        if conf_b > conf_a + 0.1:
            tendencia = "mejora"
        elif conf_b < conf_a - 0.1:
            tendencia = "degradacion"
        else:
            tendencia = "estable"

        # Generar alertas
        alertas: List[str] = []
        if metricas_b.get("n_hipotesis_refutadas", 0) > metricas_a.get("n_hipotesis_refutadas", 0) + 2:
            alertas.append(
                "Aumento significativo en hipotesis refutadas. "
                "Revisar calidad del modelo de generacion."
            )
        if metricas_b.get("predicciones_falladas", 0) > metricas_a.get("predicciones_falladas", 0) + 3:
            alertas.append(
                "Incremento notable en predicciones falladas. "
                "Posible cambio de regimen en el mercado."
            )
        if metricas_b.get("n_cambios_narrativa", 0) > 0 and metricas_a.get("n_cambios_narrativa", 0) == 0:
            alertas.append(
                "Nuevo cambio de narrativa detectado esta semana. "
                "Revisar senales debiles asociadas."
            )

        # Conclusion textual
        if tendencia == "mejora":
            conclusion = (
                f"La semana {semana_b} muestra MEJORA respecto a {semana_a}. "
                f"La confianza del sistema aumento de {conf_a:.2f} a {conf_b:.2f}. "
                f"Se confirmaron {metricas_b.get('n_hipotesis_confirmadas', 0)} hipotesis."
            )
        elif tendencia == "degradacion":
            conclusion = (
                f"La semana {semana_b} muestra DEGRADACION respecto a {semana_a}. "
                f"La confianza del sistema disminuyo de {conf_a:.2f} a {conf_b:.2f}. "
                f"Se refutaron {metricas_b.get('n_hipotesis_refutadas', 0)} hipotesis."
            )
        else:
            conclusion = (
                f"La semana {semana_b} es ESTABLE respecto a {semana_a}. "
                f"La confianza se mantiene en ~{conf_b:.2f}. "
                f"Sin cambios significativos en las metricas principales."
            )

        return {
            "semana_a": semana_a,
            "semana_b": semana_b,
            "metricas_a": metricas_a,
            "metricas_b": metricas_b,
            "confianza_a": round(conf_a, 4),
            "confianza_b": round(conf_b, 4),
            "diferencias": diferencias,
            "tendencia": tendencia,
            "alertas": alertas,
            "conclusion": conclusion,
            "timestamp": datetime.now().isoformat(),
        }

    # -------------------------------------------------------------------------
    # Evolucion Temporal
    # -------------------------------------------------------------------------

    def evolucion_temporal(self, n_semanas: int = 8) -> List[Dict[str, Any]]:
        """
        Genera una serie temporal de metricas a lo largo de las ultimas N semanas.

        Args:
            n_semanas: Numero de semanas hacia atras a incluir (default 8).

        Returns:
            Lista de diccionarios, uno por semana, ordenados cronologicamente.
            Cada diccionario contiene todas las metricas de esa semana.
            Adicionalmente incluye 'anomalias_detectadas' con indices de
            semanas anomalas segun el metodo IQR.
        """
        semana_actual = semana_iso(datetime.now())
        semanas = self._generar_rango_semanas(semana_actual, n_semanas)

        serie: List[Dict[str, Any]] = []
        for sem in semanas:
            desc = self._recuperar_descubrimiento(sem)
            if desc:
                punto = {
                    "semana": sem,
                    "confianza_promedio": round(desc.confianza_promedio, 4),
                    "nivel_actividad": round(desc.nivel_actividad, 4),
                    **{
                        k: v for k, v in desc.metricas_crudas.items()
                        if isinstance(v, (int, float))
                    },
                }
            else:
                punto = {
                    "semana": sem,
                    "confianza_promedio": 0.0,
                    "nivel_actividad": 0.0,
                    "n_hipotesis_nuevas": 0,
                    "n_hipotesis_confirmadas": 0,
                    "n_hipotesis_refutadas": 0,
                    "n_tendencias": 0,
                    "predicciones_acertadas": 0,
                    "predicciones_falladas": 0,
                    "datos_disponibles": False,
                }
            serie.append(punto)

        # Detectar anomalias en la serie de confianza
        confianzas = [p.get("confianza_promedio", 0.0) for p in serie]
        indices_anomalias = detectar_anomalias_en_serie(confianzas)

        for idx in indices_anomalias:
            serie[idx]["anomalia"] = True

        # Anadir tendencia de la serie
        if len(confianzas) >= 2:
            # Regresion lineal simple (pendiente)
            x = np.arange(len(confianzas))
            y = np.array(confianzas)
            pendiente = np.polyfit(x, y, 1)[0] if len(set(confianzas)) > 1 else 0.0

            if pendiente > 0.02:
                direccion = "ascendente"
            elif pendiente < -0.02:
                direccion = "descendente"
            else:
                direccion = "lateral"

            serie.append({  # Metadatos como ultimo elemento
                "_metadatos": True,
                "pendiente_confianza": round(float(pendiente), 6),
                "direccion_tendencia": direccion,
                "semanas_con_datos": sum(1 for p in serie if p.get("datos_disponibles", True)),
                "anomalias_detectadas": [serie[i]["semana"] for i in indices_anomalias],
            })

        self._logger.info(
            f"[VEO] Serie temporal generada: {len(serie)} semanas, "
            f"{len(indices_anomalias)} anomalias detectadas."
        )

        return serie

    # -------------------------------------------------------------------------
    # Aprendizajes Acumulados
    # -------------------------------------------------------------------------

    def aprendizajes_acumulados(self) -> List[str]:
        """
        Extrae las lecciones aprendidas del historial completo.

        Recupera todos los aprendizajes almacenados en la memoria del sistema,
        filtra por confianza minima y devuelve las lecciones como texto.

        Returns:
            Lista de strings con las lecciones aprendidas, ordenadas por
            confianza descendente.
        """
        aprendizajes = self._memoria.recuperar_aprendizajes(min_confianza=0.3)

        # Ordenar por confianza descendente
        aprendizajes.sort(key=lambda a: a.get("confianza", 0), reverse=True)

        lecciones = []
        for a in aprendizajes:
            texto = a.get("leccion", "")
            conf = a.get("confianza", 0)
            cat = a.get("categoria", "general")
            usos = a.get("conteo_usos", 0)
            if texto:
                lecciones.append(
                    f"[{cat}] (conf={conf:.2f}, usos={usos}) {texto}"
                )

        self._logger.info(
            f"[VEO] {len(lecciones)} aprendizajes acumulados recuperados."
        )

        return lecciones

    # -------------------------------------------------------------------------
    # Resumen Ejecutivo
    # -------------------------------------------------------------------------

    def resumen_ejecutivo(self) -> str:
        """
        Genera un resumen ejecutivo textual del estado actual del sistema.

        Sintetiza informacion de la semana actual, la tendencia reciente
        y los aprendizajes clave en un texto legible para tomadores de decisiones.

        Returns:
            Texto en formato Markdown con el resumen ejecutivo.
        """
        semana_actual = semana_iso(datetime.now())
        desc = self._recuperar_descubrimiento(semana_actual)

        # Obtener evolucion reciente
        evolucion = self.evolucion_temporal(n_semanas=4)

        # Aprendizajes mas importantes
        aprendizajes_top = self._memoria.recuperar_aprendizajes(
            min_confianza=0.7
        )[:5]

        # Conteos globales
        total_hipotesis = self._db.contar(self.COLECCION_HIPOTESIS)
        total_tendencias = self._db.contar(self.COLECCION_TENDENCIAS)
        total_predicciones = self._db.contar(self.COLECCION_PREDICCIONES)
        total_relaciones = self._db.contar(self.COLECCION_RELACIONES)
        total_aprendizajes = self._db.contar(
            self.COLECCION_APRENDIZAJES, {"activo": True}
        )

        # Tasa de aprendizaje
        historial = self._cargar_historial_descubrimientos(8)
        tasa_aprendizaje = self._calcular_tasa_aprendizaje(historial)

        # Extraer metadatos de evolucion si existen
        metadatos = {}
        if evolucion and evolucion[-1].get("_metadatos"):
            metadatos = evolucion[-1]

        # Construir markdown
        md = f"""# Resumen Ejecutivo VEO

> **Semana**: {semana_actual}  
> **Generado**: {datetime.now().strftime("%Y-%m-%d %H:%M")}  
> **Tasa de aprendizaje**: {tasa_aprendizaje:.4f}  

## Estado del Sistema

| Metrica | Valor |
|---------|-------|
| Hipotesis totales | {total_hipotesis:,} |
| Tendencias detectadas | {total_tendencias:,} |
| Predicciones realizadas | {total_predicciones:,} |
| Relaciones causales | {total_relaciones:,} |
| Aprendizajes activos | {total_aprendizajes:,} |

"""

        if desc:
            md += f"""## Semana Actual ({semana_actual})

- **Confianza promedio**: {desc.confianza_promedio:.2%}
- **Nivel de actividad**: {desc.nivel_actividad:.2%}
- Hipotesis nuevas: **{len(desc.hipotesis_nuevas)}**
- Hipotesis confirmadas: **{len(desc.hipotesis_confirmadas)}**
- Hipotesis refutadas: **{len(desc.hipotesis_refutadas)}**
- Tendencias detectadas: **{len(desc.tendencias_detectadas)}**
- Cambios de narrativa: **{len(desc.cambios_narrativa)}**
- Predicciones: {desc.predicciones_acertadas} acertadas / {desc.predicciones_falladas} falladas

"""
        else:
            md += f"""## Semana Actual ({semana_actual})

> No hay datos disponibles para esta semana. Genere un informe semanal
> con `generar_informe_semanal()` primero.

"""

        if metadatos:
            md += f"""## Tendencia Reciente (4 semanas)

- Direccion: **{metadatos.get('direccion_tendencia', 'desconocida').upper()}**
- Pendiente de confianza: {metadatos.get('pendiente_confianza', 0):.6f}
- Semanas con datos: {metadatos.get('semanas_con_datos', 0)}/4
"""
            if metadatos.get("anomalias_detectadas"):
                md += f"- Anomalias detectadas: {', '.join(metadatos['anomalias_detectadas'])}\n"
            md += "\n"

        if aprendizajes_top:
            md += "## Aprendizajes Clave (Top 5)\n\n"
            for i, ap in enumerate(aprendizajes_top, 1):
                md += (
                    f"{i}. **[{ap.get('categoria', 'general')}]** "
                    f"(conf: {ap.get('confianza', 0):.0%}) "
                    f"{ap.get('leccion', '')}\n\n"
                )

        # Patrones recurrentes
        patrones = self.detectar_patrones_recurrentes()
        if patrones:
            md += "## Patrones Recurrentes Detectados\n\n"
            for patron in patrones[:3]:
                md += (
                    f"- **{patron['tipo']}**: {patron['descripcion']} "
                    f"(frecuencia: {patron.get('frecuencia', 'desconocida')})\n"
                )
            md += "\n"

        md += f"""---
*Resumen generado automaticamente por VEO v{self.VERSION}*
*SOIS es una plataforma de inteligencia artificial cooperativa destinada a*
*detectar cambios emergentes en la realidad mediante el analisis continuo*
*de senales debiles, relaciones semanticas y conocimiento distribuido.*
"""

        self._logger.info(
            f"[VEO] Resumen ejecutivo generado ({len(md)} caracteres)."
        )

        return md

    # -------------------------------------------------------------------------
    # Deteccion de Patrones Recurrentes
    # -------------------------------------------------------------------------

    def detectar_patrones_recurrentes(self) -> List[Dict[str, Any]]:
        """
        Detecta patrones que se repiten semana a semana en el historial.

        Analiza las ultimas 8 semanas buscando:
            - Categorias de hipotesis recurrentes.
            - Tendencias que aparecen en multiples semanas.
            - Ciclos en la confianza del sistema.
            - Relaciones entre confirmaciones y refutaciones.

        Returns:
            Lista de patrones detectados, cada uno con tipo, descripcion,
            frecuencia y confianza del patron.
        """
        historial = self._cargar_historial_descubrimientos(8)

        if len(historial) < 2:
            return []

        patrones: List[Dict[str, Any]] = []

        # 1. Patron: Actividad sostenida
        semanas_activas = sum(
            1 for d in historial if d.get("nivel_actividad", 0) > 0.3
        )
        if semanas_activas >= len(historial) * 0.75:
            patrones.append({
                "tipo": "actividad_sostenida",
                "descripcion": (
                    f"El sistema ha mantenido alta actividad durante "
                    f"{semanas_activas} de las ultimas {len(historial)} semanas."
                ),
                "frecuencia": f"{semanas_activas}/{len(historial)} semanas",
                "confianza": round(semanas_activas / len(historial), 4),
            })

        # 2. Patron: Confirmaciones consistentes
        confirmaciones = [
            d.get("metricas_crudas", {}).get("n_hipotesis_confirmadas", 0)
            for d in historial
        ]
        if all(c >= 1 for c in confirmaciones) and sum(confirmaciones) >= 3:
            patrones.append({
                "tipo": "confirmaciones_consistentes",
                "descripcion": (
                    f"Se han confirmado hipotesis en {sum(1 for c in confirmaciones if c > 0)} "
                    f"semanas consecutivas (total: {sum(confirmaciones)}). "
                    f"El modelo de validacion esta funcionando consistentemente."
                ),
                "frecuencia": f"{sum(1 for c in confirmaciones if c > 0)}/{len(historial)} semanas",
                "confianza": 0.8,
            })

        # 3. Patron: Predicciones mejorando
        acertadas = [
            d.get("metricas_crudas", {}).get("predicciones_acertadas", 0)
            for d in historial
        ]
        falladas = [
            d.get("metricas_crudas", {}).get("predicciones_falladas", 0)
            for d in historial
        ]
        total_acertadas = sum(acertadas)
        total_falladas = sum(falladas)
        if total_acertadas + total_falladas > 5:
            tasa = total_acertadas / (total_acertadas + total_falladas)
            if tasa > 0.6:
                patrones.append({
                    "tipo": "predicciones_efectivas",
                    "descripcion": (
                        f"La tasa de acierto de predicciones es del {tasa:.1%} "
                        f"({total_acertadas}/{total_acertadas + total_falladas}). "
                        f"El modelo predictivo esta por encima del azar."
                    ),
                    "frecuencia": f"{total_acertadas} aciertos en {len(historial)} semanas",
                    "confianza": round(tasa, 4),
                })
            elif tasa < 0.4 and total_acertadas + total_falladas > 10:
                patrones.append({
                    "tipo": "predicciones_degradadas",
                    "descripcion": (
                        f"La tasa de acierto ha caido al {tasa:.1%}. "
                        f"Considerar recalibracion del modelo predictivo."
                    ),
                    "frecuencia": f"{total_acertadas} aciertos / {total_falladas} fallos",
                    "confianza": round(1 - tasa, 4),
                })

        # 4. Patron: Cambios de narrativa frecuentes
        cambios_narr = [
            d.get("metricas_crudas", {}).get("n_cambios_narrativa", 0)
            for d in historial
        ]
        if sum(cambios_narr) >= 2:
            patrones.append({
                "tipo": "inestabilidad_narrativa",
                "descripcion": (
                    f"Se detectaron {sum(cambios_narr)} cambios de narrativa "
                    f"en {sum(1 for c in cambios_narr if c > 0)} semanas. "
                    f"El entorno informativo muestra volatilidad narrativa."
                ),
                "frecuencia": f"{sum(cambios_narr)} cambios en {len(historial)} semanas",
                "confianza": min(0.9, sum(cambios_narr) / len(historial)),
            })

        # 5. Patron: Confianza en tendencia
        confianzas = [d.get("confianza_promedio", 0.5) for d in historial]
        if len(confianzas) >= 3:
            pendiente = np.polyfit(np.arange(len(confianzas)), np.array(confianzas), 1)[0] \
                if len(set(confianzas)) > 1 else 0.0
            if pendiente > 0.05:
                patrones.append({
                    "tipo": "confianza_creciente",
                    "descripcion": (
                        f"La confianza del sistema muestra tendencia ASCENDENTE "
                        f"(pendiente={pendiente:.4f}). El sistema esta aprendiendo "
                        f"y mejorando su precision."
                    ),
                    "frecuencia": f"{len(historial)} semanas analizadas",
                    "confianza": 0.75,
                })
            elif pendiente < -0.05:
                patrones.append({
                    "tipo": "confianza_decreciente",
                    "descripcion": (
                        f"La confianza del sistema muestra tendencia DESCENDENTE "
                        f"(pendiente={pendiente:.4f}). Puede indicar un cambio "
                        f"de regimen o degradacion del modelo."
                    ),
                    "frecuencia": f"{len(historial)} semanas analizadas",
                    "confianza": 0.75,
                })

        self._logger.info(
            f"[VEO] {len(patrones)} patrones recurrentes detectados."
        )

        return patrones

    # -------------------------------------------------------------------------
    # Metodos Privados
    # -------------------------------------------------------------------------

    def _recuperar_descubrimiento(self, semana: str) -> Optional[Descubrimiento]:
        """Recupera un descubrimiento por semana desde la base de datos."""
        resultados = self._db.buscar(
            self.COLECCION_DESCUBRIMIENTOS,
            {"semana": semana}
        )
        if not resultados:
            return None

        datos = resultados[-1]  # El mas reciente si hay multiples
        return self._reconstruir_descubrimiento(datos)

    def _reconstruir_descubrimiento(self, datos: Dict[str, Any]) -> Descubrimiento:
        """Reconstruye un Descubrimiento desde datos de la base de datos."""
        return Descubrimiento(
            semana=datos["semana"],
            periodo_inicio=datetime.fromisoformat(datos["periodo_inicio"]),
            periodo_fin=datetime.fromisoformat(datos["periodo_fin"]),
            hipotesis_nuevas=datos.get("hipotesis_nuevas", []),
            hipotesis_confirmadas=datos.get("hipotesis_confirmadas", []),
            hipotesis_refutadas=datos.get("hipotesis_refutadas", []),
            tendencias_detectadas=datos.get("tendencias_detectadas", []),
            cambios_narrativa=datos.get("cambios_narrativa", []),
            predicciones_acertadas=datos.get("predicciones_acertadas", 0),
            predicciones_falladas=datos.get("predicciones_falladas", 0),
            nuevas_relaciones_causales=datos.get("nuevas_relaciones_causales", []),
            confianza_promedio=datos.get("confianza_promedio", 0.0),
            nivel_actividad=datos.get("nivel_actividad", 0.0),
            metricas_crudas=datos.get("metricas_crudas", {}),
            lecciones_aprendidas=datos.get("lecciones_aprendidas", []),
            markdown_generado=datos.get("markdown_generado", ""),
            timestamp_generacion=datetime.fromisoformat(
                datos.get("timestamp_generacion", datetime.now().isoformat())
            ),
        )

    def _extraer_lecciones_automaticas(
        self,
        hipotesis_confirmadas: List[Dict],
        hipotesis_refutadas: List[Dict],
        predicciones_acertadas: int,
        predicciones_falladas: int,
        tendencias: List[Dict],
    ) -> List[Tuple[str, str]]:
        """
        Extrae lecciones automaticas de los datos de la semana.

        Returns:
            Lista de tuplas (leccion, categoria).
        """
        lecciones: List[Tuple[str, str]] = []

        # Leccion de confirmaciones
        if len(hipotesis_confirmadas) >= 2:
            temas = [h.get("categoria", "general") for h in hipotesis_confirmadas]
            tema_comun = max(set(temas), key=temas.count) if temas else "general"
            lecciones.append((
                f"Las hipotesis en el area de '{tema_comun}' han mostrado "
                f"alta fiabilidad esta semana ({len(hipotesis_confirmadas)} confirmadas). "
                f"Considerar aumentar el peso de senales relacionadas con esta categoria.",
                "prediccion"
            ))

        # Leccion de refutaciones
        if len(hipotesis_refutadas) >= 2:
            lecciones.append((
                f"Se refutaron {len(hipotesis_refutadas)} hipotesis esta semana. "
                f"El sistema debe ser mas conservador en la generacion de hipotesis similares "
                f"hasta obtener mayor evidencia de soporte.",
                "calibracion"
            ))

        # Leccion de predicciones
        total_preds = predicciones_acertadas + predicciones_falladas
        if total_preds > 0:
            tasa = predicciones_acertadas / total_preds
            if tasa > 0.7:
                lecciones.append((
                    f"El modelo predictivo ha funcionado excepcionalmente bien "
                    f"esta semana ({tasa:.0%} de acierto). Los parametros actuales "
                    f"parecen bien calibrados para el regimen actual del mercado.",
                    "prediccion"
                ))
            elif tasa < 0.4 and total_preds >= 3:
                lecciones.append((
                    f"La precision predictiva ha caido al {tasa:.0%} esta semana. "
                    f"Es posible que el mercado haya cambiado de regimen. "
                    f"Recomendacion: reducir confianza en predicciones a corto plazo.",
                    "prediccion"
                ))

        # Leccion de tendencias
        if len(tendencias) >= 2:
            lecciones.append((
                f"Se detectaron {len(tendencias)} tendencias nuevas en la semana. "
                f"La convergencia de multiples senales sugiere un periodo de cambio "
                f"estructural en el entorno monitoreado.",
                "tendencia"
            ))

        return lecciones

    def _generar_markdown_informe(self, desc: Descubrimiento) -> str:
        """Genera la version Markdown del informe semanal."""
        precision = 0.0
        total_preds = desc.predicciones_acertadas + desc.predicciones_falladas
        if total_preds > 0:
            precision = desc.predicciones_acertadas / total_preds

        md = f"""# Informe Semanal VEO

## Periodo: {desc.semana}

**Desde**: {desc.periodo_inicio.strftime("%Y-%m-%d")}  
**Hasta**: {desc.periodo_fin.strftime("%Y-%m-%d")}  
**Generado**: {desc.timestamp_generacion.strftime("%Y-%m-%d %H:%M")}

---

## Resumen de Metricas

| Indicador | Valor |
|-----------|-------|
| Confianza promedio | {desc.confianza_promedio:.2%} |
| Nivel de actividad | {desc.nivel_actividad:.2%} |
| Precision predictiva | {precision:.2%} ({desc.predicciones_acertadas}/{total_preds}) |

---

## Hipotesis

### Nuevas ({len(desc.hipotesis_nuevas)})
"""
        if desc.hipotesis_nuevas:
            for h in desc.hipotesis_nuevas[:10]:  # Limitar a 10
                nombre = h.get("nombre", "Sin nombre")
                conf = h.get("confianza", 0)
                md += f"- **{nombre}** (conf: {conf:.0%})\n"
            if len(desc.hipotesis_nuevas) > 10:
                md += f"- ... y {len(desc.hipotesis_nuevas) - 10} mas\n"
        else:
            md += "_Sin hipotesis nuevas esta semana._\n"

        md += f"\n### Confirmadas ({len(desc.hipotesis_confirmadas)})\n"
        if desc.hipotesis_confirmadas:
            for h in desc.hipotesis_confirmadas[:10]:
                md += f"- **{h.get('nombre', 'Sin nombre')}**\n"
        else:
            md += "_Sin confirmaciones esta semana._\n"

        md += f"\n### Refutadas ({len(desc.hipotesis_refutadas)})\n"
        if desc.hipotesis_refutadas:
            for h in desc.hipotesis_refutadas[:10]:
                md += f"- **{h.get('nombre', 'Sin nombre')}**\n"
        else:
            md += "_Sin refutaciones esta semana._\n"

        md += f"""
---

## Tendencias y Narrativa

### Tendencias Detectadas ({len(desc.tendencias_detectadas)})
"""
        if desc.tendencias_detectadas:
            for t in desc.tendencias_detectadas[:10]:
                md += f"- {t.get('descripcion', 'Sin descripcion')}\n"
        else:
            md += "_Sin tendencias nuevas._\n"

        md += f"\n### Cambios de Narrativa ({len(desc.cambios_narrativa)})\n"
        if desc.cambios_narrativa:
            for c in desc.cambios_narrativa[:10]:
                md += f"- {c.get('descripcion', 'Sin descripcion')}\n"
        else:
            md += "_Sin cambios de narrativa._\n"

        md += f"""
---

## Relaciones Causales Nuevas ({len(desc.nuevas_relaciones_causales)})
"""
        if desc.nuevas_relaciones_causales:
            for r in desc.nuevas_relaciones_causales[:10]:
                origen = r.get("origen", "?")
                destino = r.get("destino", "?")
                peso = r.get("peso", 0)
                md += f"- **{origen}** -> **{destino}** (peso: {peso:.3f})\n"
        else:
            md += "_Sin nuevas relaciones causales._\n"

        if desc.lecciones_aprendidas:
            md += "\n---\n\n## Lecciones Aprendidas\n\n"
            for leccion in desc.lecciones_aprendidas:
                md += f"- {leccion}\n"

        md += f"""
---

*Informe generado automaticamente por VEO v{self.VERSION}*
*SOIS es una plataforma de inteligencia artificial cooperativa destinada a*
*detectar cambios emergentes en la realidad mediante el analisis continuo*
*de senales debiles, relaciones semanticas y conocimiento distribuido,*
*generando hipotesis explicables que ayuden a los analistas humanos a*
*comprender sistemas complejos bajo incertidumbre.*
"""

        return md

    def _cargar_historial_descubrimientos(self, n_semanas: int) -> List[Dict[str, Any]]:
        """Carga el historial de descubrimientos de las ultimas N semanas."""
        semana_actual = semana_iso(datetime.now())
        semanas = self._generar_rango_semanas(semana_actual, n_semanas)

        historial = []
        for sem in semanas:
            desc = self._recuperar_descubrimiento(sem)
            if desc:
                historial.append(desc.to_dict())

        return historial

    def _generar_rango_semanas(
        self,
        semana_fin: str,
        n_semanas: int,
    ) -> List[str]:
        """Genera una lista de semanas ISO hacia atras desde semana_fin."""
        semanas = []
        inicio, _ = inicio_fin_semana(semana_fin)

        for i in range(n_semanas):
            fecha = inicio - timedelta(weeks=i)
            semanas.append(semana_iso(fecha))

        return list(reversed(semanas))

    def _calcular_tasa_aprendizaje(
        self,
        historial: List[Dict[str, Any]],
    ) -> float:
        """
        Calcula la tasa de mejora del sistema a partir del historial.

        Mide el cambio en la relacion confirmaciones/refutaciones y la
        precision predictiva a lo largo del tiempo.

        Args:
            historial: Lista de descubrimientos previos.

        Returns:
            Valor en [-1, 1] indicando la tasa de aprendizaje.
            Valores positivos = el sistema esta mejorando.
        """
        if len(historial) < 2:
            return 0.0

        # Metrica compuesta: ratio de confirmaciones vs refutaciones + precision
        metricas = []
        for desc in historial:
            mc = desc.get("metricas_crudas", {})
            confirmadas = mc.get("n_hipotesis_confirmadas", 0)
            refutadas = mc.get("n_hipotesis_refutadas", 0)
            acertadas = mc.get("predicciones_acertadas", 0)
            falladas = mc.get("predicciones_falladas", 0)

            ratio_validacion = confirmadas / (confirmadas + refutadas + 1)
            ratio_prediccion = acertadas / (acertadas + falladas + 1)

            metricas.append(0.5 * ratio_validacion + 0.5 * ratio_prediccion)

        # Pendiente de la tendencia
        x = np.arange(len(metricas))
        y = np.array(metricas)

        if len(set(metricas)) <= 1:
            return 0.0

        pendiente = np.polyfit(x, y, 1)[0]

        # Normalizar a [-1, 1]
        tasa = max(-1.0, min(1.0, pendiente * len(metricas)))

        return float(tasa)

    @staticmethod
    def _metricas_vacio() -> Dict[str, int]:
        """Retorna un diccionario de metricas con valores cero."""
        return {
            "n_hipotesis_nuevas": 0,
            "n_hipotesis_confirmadas": 0,
            "n_hipotesis_refutadas": 0,
            "n_tendencias": 0,
            "n_cambios_narrativa": 0,
            "predicciones_acertadas": 0,
            "predicciones_falladas": 0,
            "n_relaciones_nuevas": 0,
            "volumen_total": 0,
        }


# =============================================================================
# MEMORIA DEL SISTEMA
# =============================================================================

class MemoriaSistema:
    """
    Sistema de memoria acumulativa para lecciones aprendidas.

    Almacena, recupera y actualiza lecciones que el sistema va aprendiendo
    a lo largo del tiempo. Cada leccion tiene una confianza asociada que
    se actualiza dinamicamente segun validaciones posteriores.

    La memoria es el componente que permite al sistema SOIS "aprender de
    sus errores" y mejorar continuamente.

    Ejemplo:
        >>> memoria = MemoriaSistema(db)
        >>> memoria.guardar_aprendizaje(
        ...     "Las senales de redes sociales anticipan cambios politicos",
        ...     "tendencia",
        ...     0.7
        ... )
        >>> lecciones = memoria.recuperar_aprendizajes(categoria="tendencia")
        >>> memoria.actualizar_confianza_aprendizaje("id_leccion", resultado=True)
    """

    COLECCION: str = "aprendizajes_sistema"
    VERSION: str = "1.0.0"

    def __init__(self, db: BaseDatos) -> None:
        """
        Inicializa la memoria del sistema.

        Args:
            db: Capa de persistencia para almacenar aprendizajes.
        """
        self._db = db

    def guardar_aprendizaje(
        self,
        leccion: str,
        categoria: str,
        confianza: float,
    ) -> str:
        """
        Guarda una nueva leccion aprendida en la memoria.

        Si ya existe una leccion similar (misma categoria y texto cercano),
        se actualiza en lugar de crear una nueva.

        Args:
            leccion: Texto descriptivo de la leccion.
            categoria: Categoria tematica (ej: "causalidad", "prediccion").
            confianza: Nivel de confianza inicial [0, 1].

        Returns:
            ID del aprendizaje guardado.
        """
        # Buscar lecciones similares para evitar duplicados
        existentes = self._db.buscar(
            self.COLECCION,
            {"categoria": categoria, "activo": True}
        )

        for existente in existentes:
            # Similitud simple: 80% de palabras en comun
            palabras_nueva = set(leccion.lower().split())
            palabras_existente = set(existente.get("leccion", "").lower().split())
            if palabras_nueva and palabras_existente:
                interseccion = palabras_nueva & palabras_existente
                union = palabras_nueva | palabras_existente
                similitud = len(interseccion) / len(union) if union else 0

                if similitud > 0.7:
                    # Actualizar existente en lugar de crear nuevo
                    doc_id = existente.get("id", "")
                    nueva_confianza = (
                        existente.get("confianza", 0.5) * 0.7 + confianza * 0.3
                    )
                    self._db.actualizar(
                        self.COLECCION,
                        doc_id,
                        {
                            "confianza": round(nueva_confianza, 4),
                            "conteo_usos": existente.get("conteo_usos", 0) + 1,
                        }
                    )
                    return doc_id

        # Crear nuevo aprendizaje
        semana_actual = semana_iso(datetime.now())
        aprendizaje = Aprendizaje(
            id=f"apz-{int(datetime.now().timestamp())}-{hash(leccion) & 0xFFFF:04x}",
            leccion=leccion,
            categoria=categoria,
            confianza=max(0.0, min(1.0, confianza)),
            semana_origen=semana_actual,
        )

        doc_id = self._db.guardar(self.COLECCION, aprendizaje.to_dict())
        return doc_id

    def recuperar_aprendizajes(
        self,
        categoria: Optional[str] = None,
        min_confianza: float = 0.5,
        solo_activos: bool = True,
        limite: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Recupera lecciones relevantes de la memoria.

        Args:
            categoria: Filtrar por categoria (None = todas).
            min_confianza: Confianza minima para incluir.
            solo_activos: Solo aprendizajes activos.
            limite: Maximo numero de resultados.

        Returns:
            Lista de aprendizajes ordenados por confianza descendente.
        """
        filtros: Dict[str, Any] = {}
        if categoria:
            filtros["categoria"] = categoria
        if solo_activos:
            filtros["activo"] = True

        resultados = self._db.buscar(self.COLECCION, filtros)

        # Filtrar por confianza minima y ordenar
        filtrados = [
            r for r in resultados
            if r.get("confianza", 0) >= min_confianza
        ]
        filtrados.sort(key=lambda x: x.get("confianza", 0), reverse=True)

        return filtrados[:limite]

    def actualizar_confianza_aprendizaje(
        self,
        leccion_id: str,
        resultado: bool,
    ) -> None:
        """
        Aumenta o disminuye la confianza de una leccion segun su validez posterior.

        Si la leccion se confirma (resultado=True), aumenta la confianza.
        Si se refuta (resultado=False), disminuye la confianza y eventualmente
        desactiva la leccion.

        Args:
            leccion_id: ID del aprendizaje a actualizar.
            resultado: True si se confirmo, False si se refuto.
        """
        datos = self._db.obtener_por_id(self.COLECCION, leccion_id)
        if datos is None:
            return

        confianza_actual = datos.get("confianza", 0.5)
        positivas = datos.get("validaciones_positivas", 0)
        negativas = datos.get("validaciones_negativas", 0)
        usos = datos.get("conteo_usos", 0)

        if resultado:
            # Aumentar confianza con decaimiento (Bayesiano aproximado)
            nueva_confianza = (confianza_actual * usos + 1.0) / (usos + 1)
            positivas += 1
        else:
            # Disminuir confianza
            nueva_confianza = (confianza_actual * usos + 0.0) / (usos + 1)
            negativas += 1

        # Desactivar si la confianza cae demasiado
        activo = nueva_confianza > 0.2

        self._db.actualizar(
            self.COLECCION,
            leccion_id,
            {
                "confianza": round(max(0.0, nueva_confianza), 4),
                "validaciones_positivas": positivas,
                "validaciones_negativas": negativas,
                "conteo_usos": usos + 1,
                "activo": activo,
            }
        )

    def exportar_memoria(self) -> Dict[str, Any]:
        """
        Exporta toda la memoria del sistema.

        Returns:
            Diccionario con todos los aprendizajes, estadisticas por categoria
            y metadatos de la memoria.
        """
        todos = self._db.buscar(self.COLECCION, {})

        # Estadisticas por categoria
        categorias: Dict[str, Dict[str, Any]] = {}
        for ap in todos:
            cat = ap.get("categoria", "sin_categoria")
            if cat not in categorias:
                categorias[cat] = {
                    "total": 0,
                    "activos": 0,
                    "confianza_promedio": 0.0,
                    "confianza_maxima": 0.0,
                    "confianza_minima": 1.0,
                }
            categorias[cat]["total"] += 1
            if ap.get("activo", True):
                categorias[cat]["activos"] += 1
            conf = ap.get("confianza", 0)
            categorias[cat]["confianza_promedio"] += conf
            categorias[cat]["confianza_maxima"] = max(categorias[cat]["confianza_maxima"], conf)
            categorias[cat]["confianza_minima"] = min(categorias[cat]["confianza_minima"], conf)

        for cat in categorias:
            total = categorias[cat]["total"]
            if total > 0:
                categorias[cat]["confianza_promedio"] = round(
                    categorias[cat]["confianza_promedio"] / total, 4
                )

        # Estadisticas globales
        activos = sum(1 for a in todos if a.get("activo", True))
        confianzas = [a.get("confianza", 0) for a in todos]

        return {
            "version": self.VERSION,
            "timestamp_exportacion": datetime.now().isoformat(),
            "estadisticas_globales": {
                "total_aprendizajes": len(todos),
                "aprendizajes_activos": activos,
                "aprendizajes_inactivos": len(todos) - activos,
                "confianza_promedio_global": round(statistics.mean(confianzas), 4) if confianzas else 0,
                "confianza_mediana_global": round(statistics.median(confianzas), 4) if confianzas else 0,
            },
            "estadisticas_por_categoria": categorias,
            "aprendizajes": todos,
        }


# =============================================================================
# FUNCIONES AUXILIARES
# =============================================================================

def semana_iso(fecha: datetime) -> str:
    """
    Convierte una fecha a su representacion en semana ISO.

    Formato de salida: "YYYY-WNN" donde NN es el numero de semana [01-53].

    Args:
        fecha: Fecha a convertir.

    Returns:
        Cadena en formato "YYYY-WNN".

    Ejemplo:
        >>> semana_iso(datetime(2026, 6, 9))
        '2026-W24'
    """
    year, week, _ = fecha.isocalendar()
    return f"{year}-W{week:02d}"


def inicio_fin_semana(semana_iso_str: str) -> Tuple[datetime, datetime]:
    """
    Convierte una semana ISO a su fecha de inicio y fin.

    Args:
        semana_iso_str: Cadena en formato "YYYY-WNN".

    Returns:
        Tupla (fecha_inicio, fecha_fin) donde fin es domingo 23:59:59.

    Raises:
        SemanaInvalidaError: Si el formato es incorrecto.

    Ejemplo:
        >>> inicio, fin = inicio_fin_semana("2026-W24")
        >>> print(inicio.date())
        2026-06-08
    """
    if not _validar_formato_semana(semana_iso_str):
        raise SemanaInvalidaError(
            f"Formato invalido: '{semana_iso_str}'. Use 'YYYY-WNN'."
        )

    # Parsear ano y semana
    match = re.match(r"^(\d{4})-W(\d{2})$", semana_iso_str)
    if not match:
        raise SemanaInvalidaError(f"No se pudo parsear: '{semana_iso_str}'")

    year = int(match.group(1))
    week = int(match.group(2))

    # El jueves de la semana ISO es el que determina el ano
    # Usar el metodo: encontrar el lunes de esa semana ISO
    # Estrategia: crear fecha para el 4 de enero del ano (siempre en semana 1)
    # y calcular desde ahi

    # Metodo alternativo mas robusto: usar fromisocalendar si disponible
    try:
        # Python 3.8+ tiene fromisocalendar
        lunes = datetime.fromisocalendar(year, week, 1)  # dia 1 = lunes
    except AttributeError:
        # Fallback para versiones anteriores
        # 4 de enero siempre esta en la semana 1
        cuatro_enero = datetime(year, 1, 4)
        # Lunes de la semana 1
        lunes_sem1 = cuatro_enero - timedelta(days=cuatro_enero.isoweekday() - 1)
        # Lunes de la semana deseada
        lunes = lunes_sem1 + timedelta(weeks=week - 1)

    # Domingo de esa semana
    domingo = lunes + timedelta(days=6, hours=23, minutes=59, seconds=59)

    return lunes, domingo


def detectar_anomalias_en_serie(serie: List[float]) -> List[int]:
    """
    Detecta puntos anomalos en una serie temporal usando el metodo IQR.

    El metodo del Rango Intercuartilico (IQR) define anomalias como valores
    que caen por debajo de Q1 - 1.5*IQR o por encima de Q3 + 1.5*IQR.

    Args:
        serie: Lista de valores numericos.

    Returns:
        Lista de indices (0-based) donde se detectaron anomalias.

    Ejemplo:
        >>> detectar_anomalias_en_serie([1, 2, 3, 2, 100, 2, 1])
        [4]  # El valor 100 es anomalo
    """
    if len(serie) < 4:
        return []

    arr = np.array(serie, dtype=float)

    q1 = np.percentile(arr, 25)
    q3 = np.percentile(arr, 75)
    iqr = q3 - q1

    if iqr == 0:
        return []

    limite_inferior = q1 - 1.5 * iqr
    limite_superior = q3 + 1.5 * iqr

    anomalias = [
        i for i, valor in enumerate(serie)
        if valor < limite_inferior or valor > limite_superior
    ]

    return anomalias


# =============================================================================
# FUNCIONES PRIVADAS AUXILIARES
# =============================================================================

def _validar_formato_semana(semana_str: str) -> bool:
    """Valida que una cadena tenga el formato correcto de semana ISO."""
    if not semana_str:
        return False
    patron = r"^\d{4}-W\d{2}$"
    return bool(re.match(patron, semana_str))


# =============================================================================
# EJECUCION COMO SCRIPT
# =============================================================================


# ============================================================================
# VEO v2: Funciones de integracion con hermes_commander / veo_core
# ============================================================================
# NOTA: Estas funciones fueron anadidas en la migracion de VEO v1 a VEO v2.
# Proporcionan observabilidad, auditoria y health-checks sin modificar
# la logica existente del Diario de Descubrimientos ni de MemoriaSistema.
# ============================================================================

import time as _time

# --- Estado observable del modulo (VEO v2) ---
_journal_execution_count: int = 0
_journal_last_execution_time: float = 0.0
_journal_operation_log: list = []


def get_trust_score() -> float:
    """
    VEO v2: Devuelve el score de confianza del diario de descubrimientos.

    Basado en la calidad de los informes generados y la utilidad de los
    aprendizajes acumulados.

    Returns:
        float: Score de confianza en [0.0, 1.0].
    """
    global _journal_operation_log
    if not _journal_operation_log:
        return 0.8

    exitosas = sum(
        1 for op in _journal_operation_log
        if op.get("exitosa", True)
    )
    total = len(_journal_operation_log)
    score = 0.3 + 0.7 * (exitosas / max(total, 1))
    return round(min(max(score, 0.0), 1.0), 4)


def get_last_execution_time() -> str:
    """
    VEO v2: Devuelve el timestamp ISO de la ultima operacion del diario.

    Returns:
        str: Timestamp ISO 8601, o cadena vacia si no ha ejecutado.
    """
    global _journal_last_execution_time
    if _journal_last_execution_time == 0.0:
        return ""
    return _time.strftime("%Y-%m-%dT%H:%M:%SZ", _time.gmtime(_journal_last_execution_time))


def get_health_status() -> dict:
    """
    VEO v2: Devuelve el estado de salud del diario de descubrimientos.

    Returns:
        dict: {"status": "healthy|degraded|unhealthy", "score": 0-100}
    """
    global _journal_last_execution_time, _journal_operation_log

    score = 100

    if _journal_last_execution_time > 0:
        horas = (_time.time() - _journal_last_execution_time) / 3600
        if horas > 168:  # 1 semana
            score -= 25
        elif horas > 72:
            score -= 10

    if _journal_operation_log:
        trust = get_trust_score()
        if trust < 0.5:
            score -= 20

    if _journal_execution_count == 0:
        score -= 5

    score = max(0, min(100, score))

    if score >= 80:
        status = "healthy"
    elif score >= 50:
        status = "degraded"
    else:
        status = "unhealthy"

    return {"status": status, "score": score}


def _log_audit_journal(
    operacion: str,
    semana: str = "",
    detalles: str = "",
    exitosa: bool = True,
) -> None:
    """
    VEO v2: Registra una entrada de auditoria para cada operacion del diario.

    Args:
        operacion: Tipo de operacion (informe_semanal, comparar_semanas, etc.).
        semana: Semana ISO relacionada.
        detalles: Detalles adicionales.
        exitosa: Si la operacion fue exitosa.
    """
    global _journal_execution_count, _journal_last_execution_time, _journal_operation_log

    _journal_execution_count += 1
    _journal_last_execution_time = _time.time()

    entry = {
        "timestamp": get_last_execution_time(),
        "operacion": operacion,
        "semana": semana,
        "detalles": detalles[:200] if detalles else "",
        "exitosa": exitosa,
    }
    _journal_operation_log.append(entry)

    if len(_journal_operation_log) > 500:
        _journal_operation_log = _journal_operation_log[-500:]

if __name__ == "__main__":
    print("=" * 70)
    print("VEO: Diario de Descubrimientos Semanal")
    print("=" * 70)
    print()
    print("Frase definitiva:")
    print('  "SOIS es una plataforma de inteligencia artificial cooperativa')
    print("   destinada a detectar cambios emergentes en la realidad...")
    print()
    print(f"Version del diario: {DiarioDescubrimientos.VERSION}")
    print()
    print("Clases exportadas:")
    print("  - DiarioDescubrimientos (motor principal)")
    print("  - MemoriaSistema (memoria acumulativa)")
    print("  - Descubrimiento, Aprendizaje (estructuras de datos)")
    print("  - Excepciones: DiarioError, SemanaInvalidaError,")
    print("                 DatosInsuficientesError")
    print()
    print("Funciones auxiliares:")
    print("  - semana_iso(fecha) -> 'YYYY-WNN'")
    print("  - inicio_fin_semana('YYYY-WNN') -> (datetime, datetime)")
    print("  - detectar_anomalias_en_serie([float]) -> [int]")
    print()
    print("=" * 70)
