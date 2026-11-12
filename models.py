# models.py - VEO v2
"""
Modelos de datos del nucleo de VEO v2.

Este modulo define las clases de datos principales usadas por el sistema,
en particular por core/db.py para la capa de persistencia.

Los campos y valores de los enums estan alineados con el esquema SQL
definido en core/db.py (_ESQUEMA_SQL_V1 y _ESQUEMA_SQL_V2).
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List, Any


# ---------------------------------------------------------------------------
# Enums alineados con el esquema SQL de core/db.py
# ---------------------------------------------------------------------------

class EstadoHipotesis(str, Enum):
    """Estados validos para una hipotesis en la tabla 'hipotesis'."""
    activa = "activa"
    confirmada = "confirmada"
    refutada = "refutada"
    caduca = "caduca"


class EstadoPrediccion(str, Enum):
    """Estados validos para una prediccion en la tabla 'predicciones'."""
    abierta = "abierta"
    cerrada = "cerrada"
    suspendida = "suspendida"


class TipoDistribucion(str, Enum):
    """Tipos de distribucion para variables de escenario."""
    normal = "normal"
    uniforme = "uniforme"
    lognormal = "lognormal"


class TipoNodo(str, Enum):
    """Tipos validos para nodos del grafo en la tabla 'grafo_nodos'."""
    entidad = "entidad"
    concepto = "concepto"
    evento = "evento"


class VeredictoValidacion(str, Enum):
    """Veredictos validos para validaciones cientificas en 'validaciones'."""
    confirmada = "confirmada"
    refutada = "refutada"
    inconclusa = "inconclusa"


# ---------------------------------------------------------------------------
# Dataclasses alineados con el esquema SQL y funciones _fila_a_* de db.py
# ---------------------------------------------------------------------------

@dataclass
class Hipotesis:
    """Representa una hipotesis evaluable en la tabla 'hipotesis'."""
    id: str
    texto: str
    confianza: float = 0.0
    evidencias: List[str] = field(default_factory=list)
    refutaciones: List[str] = field(default_factory=list)
    estado: EstadoHipotesis = EstadoHipotesis.activa
    fecha_creacion: Any = None          # datetime o str ISO
    fecha_actualizacion: Any = None     # datetime o str ISO
    creador: str = "sistema"
    tags: List[str] = field(default_factory=list)
    peso_nei: float = 0.0


@dataclass
class Prediccion:
    """Representa una prediccion en el mercado interno ('predicciones')."""
    id: str
    hipotesis_id: str
    escenario: str
    probabilidad: float = 0.5
    fecha_prediccion: Any = None        # datetime o str ISO
    fecha_resolucion: Optional[Any] = None
    estado: EstadoPrediccion = EstadoPrediccion.abierta
    liquidez: float = 1000.0
    participaciones: int = 0


@dataclass
class Escenario:
    """Representa un escenario de simulacion en la tabla 'escenarios'."""
    id: str
    nombre: str
    descripcion: str = ""
    variables: List[Any] = field(default_factory=list)
    resultado_simulado: Any = field(default_factory=dict)
    confianza: float = 0.0
    fecha: Any = None                   # datetime o str ISO


@dataclass
class VariableEscenario:
    """Variable dentro de un escenario de simulacion."""
    nombre: str
    valor_base: float = 0.0
    rango_min: float = 0.0
    rango_max: float = 1.0
    distribucion: TipoDistribucion = TipoDistribucion.uniforme


@dataclass
class ResultadoValidacion:
    """Resultado de una validacion cientifica ('validaciones')."""
    hipotesis_id: str
    veredicto: VeredictoValidacion = VeredictoValidacion.inconclusa
    razonamiento: str = ""
    nivel_confianza: float = 0.0
    sesgos_detectados: List[str] = field(default_factory=list)
    test_realizados: List[str] = field(default_factory=list)


@dataclass
class CambioNarrativa:
    """Cambio detectado en una narrativa ('cambios_narrativa')."""
    id: str
    tema: str
    direccion_anterior: str = ""
    direccion_actual: str = ""
    magnitud_cambio: float = 0.0
    fecha_detectado: Any = None
    fuentes: List[str] = field(default_factory=list)
    confianza: float = 0.0


@dataclass
class Descubrimiento:
    """Reporte semanal de hallazgos ('descubrimientos_semanales')."""
    id: str
    semana: int = 1
    fecha_inicio: Any = None
    fecha_fin: Any = None
    hipotesis_nuevas: List[str] = field(default_factory=list)
    hipotesis_confirmadas: List[str] = field(default_factory=list)
    hipotesis_refutadas: List[str] = field(default_factory=list)
    tendencias_detectadas: List[str] = field(default_factory=list)
    aprendizajes: List[str] = field(default_factory=list)
    confianza_promedio: float = 0.0
    nivel_actividad: float = 0.0


@dataclass
class NodoGrafo:
    """Nodo del grafo de conocimiento ('grafo_nodos')."""
    id: str
    tipo: TipoNodo = TipoNodo.concepto
    nombre: str = ""
    propiedades: dict = field(default_factory=dict)
    embedding: List[float] = field(default_factory=list)
    peso: float = 1.0


@dataclass
class RelacionGrafo:
    """Relacion dirigida entre nodos del grafo ('grafo_relaciones')."""
    origen_id: str
    destino_id: str
    tipo: str = "relacion"
    peso: float = 0.5
    evidencias: List[str] = field(default_factory=list)
    confianza: float = 0.0
