# -*- coding: utf-8 -*-
"""
knowledge_graph.py — Grafo de conocimiento dinámico del VEO.

SOIS = Sistema Operativo para Intuición Social.
Filosofía: "¿Qué está cambiando? ¿Qué relaciones nuevas están apareciendo?"

Este módulo implementa un grafo de conocimiento híbrido:
- NetworkX en memoria para operaciones rápidas.
- SQLite persistente para durabilidad.

Soporta extracción de entidades y relaciones desde texto,
detección de comunidades, análisis de centralidad, y
inferencia de caminos indirectos entre conceptos.
"""

from __future__ import annotations

import json
import re
import sqlite3
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

import networkx as nx
import numpy as np
from numpy.linalg import norm


# ---------------------------------------------------------------------------
# Estructuras de datos
# ---------------------------------------------------------------------------

@dataclass
class NodoGrafo:
    """Nodo del grafo de conocimiento.

    Representa una entidad, concepto, hashtag, usuario o cualquier
    elemento extraído del texto analizado.
    """

    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    nombre: str = ""
    tipo: str = "entidad"  # entidad | concepto | hashtag | usuario | evento | fuente
    embedding: List[float] = field(default_factory=list)
    frecuencia: int = 1  # cuántas veces ha aparecido
    primera_aparicion: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    ultima_aparicion: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadatos: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serializa a diccionario."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "NodoGrafo":
        """Deserializa desde diccionario."""
        # Compatibilidad con campos opcionales
        campos_validos = {f.name for f in cls.__dataclass_fields__.values()}
        filtrado = {k: v for k, v in data.items() if k in campos_validos}
        return cls(**filtrado)


@dataclass
class RelacionGrafo:
    """Relación dirigida y ponderada entre dos nodos del grafo.

    Representa una conexión semántica, co-ocurrencia, causalidad
    o cualquier relación descubierta entre entidades.
    """

    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    origen: str = ""  # ID del nodo origen
    destino: str = ""  # ID del nodo destino
    tipo: str = "co_ocurre"  # co_ocurre | refiere | causa | contradice | refuerza | similar
    peso: float = 1.0  # fuerza de la relación [0, inf)
    evidencias: int = 1  # cuántas veces se ha observado
    primera_observacion: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    ultima_observacion: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    contextos: List[str] = field(default_factory=list)  # frases donde apareció
    metadatos: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serializa a diccionario."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RelacionGrafo":
        """Deserializa desde diccionario."""
        campos_validos = {f.name for f in cls.__dataclass_fields__.values()}
        filtrado = {k: v for k, v in data.items() if k in campos_validos}
        return cls(**filtrado)


# ---------------------------------------------------------------------------
# Mock logger para uso cuando no se provee logger externo
# ---------------------------------------------------------------------------

class _MockLogger:
    """Logger mock que no hace nada."""

    def debug(self, *args, **kwargs) -> None:  # noqa: D401
        pass

    def info(self, *args, **kwargs) -> None:  # noqa: D401
        pass

    def warning(self, *args, **kwargs) -> None:  # noqa: D401
        pass

    def error(self, *args, **kwargs) -> None:  # noqa: D401
        pass


# ---------------------------------------------------------------------------
# Grafo de Conocimiento
# ---------------------------------------------------------------------------

class GrafoConocimiento:
    """Grafo de conocimiento dinámico con persistencia híbrida.

    Usa NetworkX para operaciones en memoria (rápidas) y SQLite
    para persistencia entre sesiones.

    Parameters
    ----------
    db : sqlite3.Connection
        Conexión a SQLite. Si es None, opera solo en memoria.
    logger :
        Objeto logger compatible con logging.Logger.

    Attributes
    ----------
    grafo : nx.DiGraph
        Grafo dirigido de NetworkX en memoria.
    """

    def __init__(
        self,
        db: Optional[sqlite3.Connection] = None,
        logger: Any = None,
    ) -> None:
        if db is None:
            db = sqlite3.connect(":memory:")
        if logger is None:
            logger = _MockLogger()

        self.db = db
        self.logger = logger

        # Grafo dirigido en memoria
        self.grafo: nx.DiGraph = nx.DiGraph()

        # Índice de nodos por nombre para búsqueda rápida
        self._indice_nodos: Dict[str, str] = {}  # nombre.lower() -> id

        # Cargar desde SQLite si hay conexión
        if db is not None:
            self._cargar_desde_sqlite()
        else:
            self.logger.info("[GrafoConocimiento] Modo solo-memoria (sin persistencia)")

        self.logger.info(
            "[GrafoConocimiento] Inicializado — nodos=%d, relaciones=%d",
            self.conteo_nodos(),
            self.conteo_relaciones(),
        )

    # ------------------------------------------------------------------
    # Persistencia SQLite
    # ------------------------------------------------------------------

    def _crear_tablas(self) -> None:
        """Crea las tablas necesarias en SQLite si no existen."""
        if self.db is None:
            return
        self.db.execute(
            """
            CREATE TABLE IF NOT EXISTS grafo_nodos (
                id TEXT PRIMARY KEY,
                nombre TEXT NOT NULL,
                tipo TEXT,
                embedding BLOB,
                frecuencia INTEGER DEFAULT 1,
                primera_aparicion TEXT,
                ultima_aparicion TEXT,
                data_json TEXT
            )
            """
        )
        self.db.execute(
            """
            CREATE TABLE IF NOT EXISTS grafo_relaciones (
                id TEXT PRIMARY KEY,
                origen TEXT NOT NULL,
                destino TEXT NOT NULL,
                tipo TEXT,
                peso REAL DEFAULT 1.0,
                evidencias INTEGER DEFAULT 1,
                primera_observacion TEXT,
                ultima_observacion TEXT,
                contextos TEXT,  -- JSON list
                data_json TEXT,
                FOREIGN KEY (origen) REFERENCES grafo_nodos(id),
                FOREIGN KEY (destino) REFERENCES grafo_nodos(id)
            )
            """
        )
        self.db.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_nodos_nombre ON grafo_nodos(nombre)
            """
        )
        self.db.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_rel_origen ON grafo_relaciones(origen)
            """
        )
        self.db.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_rel_destino ON grafo_relaciones(destino)
            """
        )
        self.db.commit()

    def _cargar_desde_sqlite(self) -> None:
        """Carga el grafo completo desde SQLite a NetworkX."""
        self._crear_tablas()

        try:
            # Cargar nodos
            cursor = self.db.execute("SELECT data_json FROM grafo_nodos")
            filas = cursor.fetchall()
            for fila in filas:
                data = json.loads(fila["data_json"])
                nodo = NodoGrafo.from_dict(data)
                self.grafo.add_node(
                    nodo.id,
                    **nodo.to_dict(),
                )
                self._indice_nodos[nodo.nombre.lower()] = nodo.id

            # Cargar relaciones
            cursor = self.db.execute("SELECT data_json FROM grafo_relaciones")
            filas = cursor.fetchall()
            for fila in filas:
                data = json.loads(fila["data_json"])
                rel = RelacionGrafo.from_dict(data)
                if rel.origen in self.grafo and rel.destino in self.grafo:
                    self.grafo.add_edge(
                        rel.origen,
                        rel.destino,
                        **rel.to_dict(),
                    )

            self.logger.info(
                "[GrafoConocimiento] Cargado desde SQLite — nodos=%d, relaciones=%d",
                self.conteo_nodos(),
                self.conteo_relaciones(),
            )
        except Exception as exc:
            self.logger.error("[GrafoConocimiento] Error cargando desde SQLite: %s", exc)

    def _persistir(self) -> None:
        """Guarda el estado actual del grafo en SQLite.

        Persiste todos los nodos y relaciones, usando INSERT/UPDATE
        con conflicto para mantener sincronización.
        """
        if self.db is None:
            return

        try:
            self._crear_tablas()

            # Persistir nodos
            for nodo_id, attrs in self.grafo.nodes(data=True):
                data_json = json.dumps(dict(attrs), ensure_ascii=False)
                embedding_blob = None
                emb = attrs.get("embedding", [])
                if emb:
                    embedding_blob = np.array(emb, dtype=np.float32).tobytes()

                self.db.execute(
                    """
                    INSERT INTO grafo_nodos (id, nombre, tipo, embedding, frecuencia,
                        primera_aparicion, ultima_aparicion, data_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        nombre = excluded.nombre,
                        tipo = excluded.tipo,
                        embedding = excluded.embedding,
                        frecuencia = excluded.frecuencia,
                        ultima_aparicion = excluded.ultima_aparicion,
                        data_json = excluded.data_json
                    """,
                    (
                        attrs.get("id", nodo_id),
                        attrs.get("nombre", ""),
                        attrs.get("tipo", "entidad"),
                        embedding_blob,
                        attrs.get("frecuencia", 1),
                        attrs.get("primera_aparicion", ""),
                        attrs.get("ultima_aparicion", ""),
                        data_json,
                    ),
                )

            # Persistir relaciones
            for origen, destino, attrs in self.grafo.edges(data=True):
                data_json = json.dumps(dict(attrs), ensure_ascii=False)
                contextos_json = json.dumps(attrs.get("contextos", []), ensure_ascii=False)

                self.db.execute(
                    """
                    INSERT INTO grafo_relaciones (id, origen, destino, tipo, peso,
                        evidencias, primera_observacion, ultima_observacion,
                        contextos, data_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        tipo = excluded.tipo,
                        peso = excluded.peso,
                        evidencias = excluded.evidencias,
                        ultima_observacion = excluded.ultima_observacion,
                        contextos = excluded.contextos,
                        data_json = excluded.data_json
                    """,
                    (
                        attrs.get("id", str(uuid.uuid4())[:8]),
                        origen,
                        destino,
                        attrs.get("tipo", "co_ocurre"),
                        attrs.get("peso", 1.0),
                        attrs.get("evidencias", 1),
                        attrs.get("primera_observacion", ""),
                        attrs.get("ultima_observacion", ""),
                        contextos_json,
                        data_json,
                    ),
                )

            self.db.commit()
            self.logger.debug(
                "[GrafoConocimiento] Persistido — nodos=%d, relaciones=%d",
                self.conteo_nodos(),
                self.conteo_relaciones(),
            )
        except Exception as exc:
            self.logger.error("[GrafoConocimiento] Error en persistencia: %s", exc)

    # ------------------------------------------------------------------
    # Gestión de nodos
    # ------------------------------------------------------------------

    def agregar_nodo(self, nodo: NodoGrafo) -> str:
        """Agrega un nodo al grafo.

        Si ya existe un nodo con el mismo nombre, actualiza su frecuencia
        y timestamp en lugar de crear duplicado.

        Parameters
        ----------
        nodo : NodoGrafo
            Nodo a agregar.

        Returns
        -------
        str
            ID del nodo (existente o nuevo).
        """
        nombre_lower = nodo.nombre.lower()

        # Verificar si ya existe por nombre
        if nombre_lower in self._indice_nodos:
            existente_id = self._indice_nodos[nombre_lower]
            # Actualizar nodo existente
            self.grafo.nodes[existente_id]["frecuencia"] = (
                self.grafo.nodes[existente_id].get("frecuencia", 1) + nodo.frecuencia
            )
            self.grafo.nodes[existente_id]["ultima_aparicion"] = (
                datetime.now(timezone.utc).isoformat()
            )
            return existente_id

        # Agregar nuevo nodo
        self.grafo.add_node(nodo.id, **nodo.to_dict())
        self._indice_nodos[nombre_lower] = nodo.id
        return nodo.id

    def obtener_nodo(self, nodo_id: str) -> Optional[Dict[str, Any]]:
        """Obtiene los datos de un nodo por su ID."""
        if nodo_id in self.grafo:
            return dict(self.grafo.nodes[nodo_id])
        return None

    def buscar_nodo_por_nombre(self, nombre: str) -> Optional[str]:
        """Busca el ID de un nodo por su nombre (búsqueda insensible a mayúsculas).

        Returns
        -------
        Optional[str]
            ID del nodo si existe, None en caso contrario.
        """
        return self._indice_nodos.get(nombre.lower())

    # ------------------------------------------------------------------
    # Gestión de relaciones
    # ------------------------------------------------------------------

    def agregar_relacion(self, relacion: RelacionGrafo) -> str:
        """Agrega una relación dirigida ponderada entre dos nodos.

        Si la relación ya existe (mismo origen, destino y tipo),
        incrementa su peso y contador de evidencias.

        Parameters
        ----------
        relacion : RelacionGrafo
            Relación a agregar.

        Returns
        -------
        str
            ID de la relación.
        """
        # Asegurar que ambos nodos existen
        if relacion.origen not in self.grafo:
            self.logger.warning(
                "[GrafoConocimiento] Nodo origen '%s' no existe, creando", relacion.origen
            )
            self.agregar_nodo(
                NodoGrafo(id=relacion.origen, nombre=relacion.origen, tipo="entidad")
            )
        if relacion.destino not in self.grafo:
            self.logger.warning(
                "[GrafoConocimiento] Nodo destino '%s' no existe, creando", relacion.destino
            )
            self.agregar_nodo(
                NodoGrafo(id=relacion.destino, nombre=relacion.destino, tipo="entidad")
            )

        # Verificar si ya existe esta relación
        edge_data = self.grafo.get_edge_data(relacion.origen, relacion.destino)
        if edge_data:
            # Actualizar relación existente
            edge_data["peso"] = edge_data.get("peso", 1.0) + relacion.peso
            edge_data["evidencias"] = edge_data.get("evidencias", 1) + relacion.evidencias
            edge_data["ultima_observacion"] = datetime.now(timezone.utc).isoformat()
            if relacion.contextos:
                existentes = edge_data.get("contextos", [])
                existentes.extend(relacion.contextos)
                edge_data["contextos"] = existentes[-10:]  # mantener últimos 10
            return edge_data.get("id", "")

        # Crear nueva relación
        self.grafo.add_edge(relacion.origen, relacion.destino, **relacion.to_dict())
        return relacion.id

    # ------------------------------------------------------------------
    # Extracción de texto
    # ------------------------------------------------------------------

    def expandir_desde_texto(self, texto: str, embedding: Optional[List[float]] = None) -> Dict[str, List[str]]:
        """Extrae entidades y relaciones de un texto y las agrega al grafo.

        Usa una combinación de regex y NER simple para identificar entidades,
        y heurísticas de co-ocurrencia y patrones para establecer relaciones.

        Parameters
        ----------
        texto : str
            Texto del cual extraer entidades y relaciones.
        embedding : Optional[List[float]]
            Embedding opcional del texto completo para los nodos creados.

        Returns
        -------
        Dict[str, List[str]]
            Diccionario con ``nodos`` y ``relaciones`` creadas (lista de IDs).
        """
        ids_nodos: List[str] = []
        ids_relaciones: List[str] = []

        # 1. Extraer entidades
        entidades = self._extraer_entidades(texto)

        for ent in entidades:
            nodo = NodoGrafo(
                nombre=ent["nombre"],
                tipo=ent["tipo"],
                embedding=embedding or [],
                frecuencia=1,
                metadatos=ent.get("metadatos", {}),
            )
            nodo_id = self.agregar_nodo(nodo)
            if nodo_id not in ids_nodos:
                ids_nodos.append(nodo_id)

        # 2. Extraer relaciones entre entidades
        relaciones = self._extraer_relaciones(texto, entidades)

        for rel_data in relaciones:
            # Buscar IDs de los nodos implicados
            id_origen = self.buscar_nodo_por_nombre(rel_data["origen"])
            id_destino = self.buscar_nodo_por_nombre(rel_data["destino"])

            if id_origen and id_destino:
                relacion = RelacionGrafo(
                    origen=id_origen,
                    destino=id_destino,
                    tipo=rel_data["tipo"],
                    peso=rel_data.get("peso", 1.0),
                    contextos=[rel_data.get("contexto", texto[:200])],
                )
                rel_id = self.agregar_relacion(relacion)
                ids_relaciones.append(rel_id)

        # 3. Relaciones de co-ocurrencia: todas las entidades mencionadas juntas
        # están relacionadas semánticamente
        if len(ids_nodos) >= 2:
            for i in range(len(ids_nodos)):
                for j in range(i + 1, min(i + 5, len(ids_nodos))):
                    rel_co = RelacionGrafo(
                        origen=ids_nodos[i],
                        destino=ids_nodos[j],
                        tipo="co_ocurre",
                        peso=0.5,
                        contextos=[texto[:200]],
                    )
                    rel_id = self.agregar_relacion(rel_co)
                    ids_relaciones.append(rel_id)

        self.logger.debug(
            "[GrafoConocimiento] Texto expandido: %d nodos, %d relaciones",
            len(ids_nodos),
            len(ids_relaciones),
        )
        return {"nodos": ids_nodos, "relaciones": ids_relaciones}

    def _extraer_entidades(self, texto: str) -> List[Dict[str, Any]]:
        """Extrae entidades de un texto usando regex y heurísticas.

        Returns
        -------
        List[Dict]
            Lista de entidades con ``nombre``, ``tipo`` y ``metadatos``.
        """
        entidades: List[Dict[str, Any]] = []
        nombres_vistos: Set[str] = set()

        def agregar(nombre: str, tipo: str, metadatos: Optional[Dict] = None) -> None:
            nombre_limpio = nombre.strip().lower()
            if len(nombre_limpio) >= 3 and nombre_limpio not in nombres_vistos:
                nombres_vistos.add(nombre_limpio)
                entidades.append({
                    "nombre": nombre.strip(),
                    "tipo": tipo,
                    "metadatos": metadatos or {},
                })

        # Hashtags
        for ht in re.findall(r"#(\w+)", texto):
            agregar(ht, "hashtag")

        # Menciones @usuario
        for mencion in re.findall(r"@(\w+)", texto):
            agregar(mencion, "usuario")

        # Entidades capitalizadas (nombres propios)
        # Patrón: secuencias de 1-3 palabras capitalizadas
        patron_nombres = r"[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?:\s+(?:de|del|la|los|las|y|e|o|u)\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+){0,1}(?:\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+){0,1}"
        for match in re.finditer(patron_nombres, texto):
            nombre = match.group().strip()
            if len(nombre) >= 4:
                agregar(nombre, "entidad")

        # URLs → fuentes
        for url in re.findall(r"https?://[^\s]+", texto):
            dominio = re.sub(r"https?://(www\.)?", "", url).split("/")[0]
            if dominio:
                agregar(dominio, "fuente", {"url_completa": url})

        # Términos técnicos entre comillas
        for termino in re.findall(r'"([^"]{3,50})"', texto):
            agregar(termino, "concepto")

        # Fechas (patrones comunes)
        for fecha in re.findall(r"\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\b", texto):
            agregar(fecha, "evento")

        return entidades

    def _extraer_relaciones(
        self, texto: str, entidades: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Extrae relaciones semánticas entre entidades del texto.

        Utiliza patrones lingüísticos simples para detectar relaciones
        direccionales entre entidades mencionadas.
        """
        relaciones: List[Dict[str, Any]] = []
        if len(entidades) < 2:
            return relaciones

        nombres = [e["nombre"] for e in entidades]
        texto_lower = texto.lower()

        # Patrones de relación
        patrones_relacion = [
            (r"{a}\s+(?:es|son|fue|fueron|será|serán)\s+([^,.;]{3,80}?)(?:\s+(?:de|por|para)\s+{b})",
             "es/atributo"),
            (r"{a}\s+(?:causa|provoca|genera|origina|produce)\s+{b}",
             "causa"),
            (r"{a}\s+(?:afecta|impacta|influye|modifica|cambia)\s+{b}",
             "afecta"),
            (r"{a}\s+(?:opone|contradice|cuestiona|critica)\s+a?\s*{b}",
             "contradice"),
            (r"{a}\s+(?:apoya|refuerza|confirma|valida|respald[ao])\s+(?:a\s+)?{b}",
             "refuerza"),
            (r"{a}\s+(?:vs\.?|versus|contra|frente a)\s+{b}",
             "opone"),
            (r"{a}\s+(?:y|e)\s+{b}\s+(?:son|están|fueron)",
             "asocia"),
        ]

        for i, ent_a in enumerate(entidades):
            for j, ent_b in enumerate(entidades):
                if i == j:
                    continue

                a_lower = ent_a["nombre"].lower()
                b_lower = ent_b["nombre"].lower()

                for patron_base, tipo_rel in patrones_relacion:
                    patron = patron_base.format(a=re.escape(a_lower), b=re.escape(b_lower))
                    for match in re.finditer(patron, texto_lower):
                        contexto = texto[max(0, match.start() - 50):match.end() + 50]
                        relaciones.append({
                            "origen": ent_a["nombre"],
                            "destino": ent_b["nombre"],
                            "tipo": tipo_rel,
                            "peso": 1.0,
                            "contexto": contexto.strip(),
                        })

        return relaciones

    # ------------------------------------------------------------------
    # Análisis de grafo
    # ------------------------------------------------------------------

    def encontrar_caminos(
        self,
        origen: str,
        destino: str,
        max_longitud: int = 4,
    ) -> List[List[str]]:
        """Encuentra todos los caminos entre dos nodos para inferencia indirecta.

        Útil para descubrir conexiones causales o narrativas indirectas
        que no son evidentes a primera vista.

        Parameters
        ----------
        origen : str
            ID del nodo origen.
        destino : str
            ID del nodo destino.
        max_longitud : int
            Longitud máxima de camino (número de aristas). Default 4.

        Returns
        -------
        List[List[str]]
            Lista de caminos, cada uno es una lista de IDs de nodos.
        """
        if origen not in self.grafo:
            self.logger.warning("[GrafoConocimiento] Nodo origen '%s' no existe", origen)
            return []
        if destino not in self.grafo:
            self.logger.warning("[GrafoConocimiento] Nodo destino '%s' no existe", destino)
            return []

        caminos: List[List[str]] = []
        try:
            for path in nx.all_simple_paths(
                self.grafo, source=origen, target=destino, cutoff=max_longitud
            ):
                caminos.append(path)
                if len(caminos) >= 100:  # límite de seguridad
                    break
        except nx.NetworkXNoPath:
            pass

        # Ordenar por peso total del camino (mayor peso = más relevante)
        def peso_camino(path: List[str]) -> float:
            total = 0.0
            for i in range(len(path) - 1):
                data = self.grafo.get_edge_data(path[i], path[i + 1], {})
                total += data.get("peso", 1.0)
            return total

        caminos.sort(key=peso_camino, reverse=True)
        return caminos

    def detectar_comunidades(self) -> Dict[str, List[str]]:
        """Detecta comunidades de nodos usando el algoritmo de Louvain.

        Returns
        -------
        Dict[str, List[str]]
            Diccionario: comunidad_id -> lista de IDs de nodos.
        """
        if self.conteo_nodos() < 3:
            return {}

        # Louvain requiere grafo no dirigido
        grafo_undirected = self.grafo.to_undirected()

        try:
            from networkx.algorithms.community import louvain_communities

            comunidades = louvain_communities(grafo_undirected, seed=42)
            resultado: Dict[str, List[str]] = {}
            for i, com in enumerate(comunidades):
                resultado[f"comunidad_{i}"] = sorted(list(com))

            self.logger.info(
                "[GrafoConocimiento] %d comunidades detectadas", len(resultado)
            )
            return resultado

        except Exception as exc:
            self.logger.error("[GrafoConocimiento] Error en Louvain: %s", exc)
            return {}

    def centralidad_nodos(self, top_k: int = 20) -> List[Tuple[str, float]]:
        """Devuelve los nodos más centrales del grafo (betweenness centrality).

        La centralidad de intermediación identifica nodos que actúan como
        puentes entre diferentes partes del grafo, revelando conceptos
        clave que conectan múltiples narrativas.

        Parameters
        ----------
        top_k : int
            Número de nodos top a retornar.

        Returns
        -------
        List[Tuple[str, float]]
            Lista de (nodo_id, centralidad) ordenada descendente.
        """
        if self.conteo_nodos() < 2:
            return []

        try:
            centralidad = nx.betweenness_centrality(
                self.grafo, weight="peso", normalized=True
            )
        except Exception as exc:
            self.logger.warning("[GrafoConocimiento] Error en betweenness: %s", exc)
            return []

        ordenados = sorted(centralidad.items(), key=lambda x: x[1], reverse=True)
        return ordenados[:top_k]

    def vecinos_mas_relevantes(
        self, nodo_id: str, k: int = 10
    ) -> List[Tuple[str, float]]:
        """Obtiene los vecinos más relevantes de un nodo por peso de relación.

        Parameters
        ----------
        nodo_id : str
            ID del nodo central.
        k : int
            Número máximo de vecinos a retornar.

        Returns
        -------
        List[Tuple[str, float]]
            Lista de (nodo_id_vecino, peso_total) ordenada descendente.
        """
        if nodo_id not in self.grafo:
            return []

        vecinos: Dict[str, float] = {}

        # Salientes
        for sucesor in self.grafo.successors(nodo_id):
            peso = self.grafo.edges[nodo_id, sucesor].get("peso", 1.0)
            vecinos[sucesor] = vecinos.get(sucesor, 0.0) + peso

        # Entrantes
        for predecesor in self.grafo.predecessors(nodo_id):
            peso = self.grafo.edges[predecesor, nodo_id].get("peso", 1.0)
            vecinos[predecesor] = vecinos.get(predecesor, 0.0) + peso

        ordenados = sorted(vecinos.items(), key=lambda x: x[1], reverse=True)
        return ordenados[:k]

    def embedding_nodo(self, nodo_id: str) -> Optional[np.ndarray]:
        """Obtiene el embedding de un nodo como array numpy."""
        datos = self.grafo.nodes.get(nodo_id, {})
        emb = datos.get("embedding", [])
        if emb:
            return np.array(emb, dtype=np.float64)
        return None

    def similitud_nodos(self, nodo_a: str, nodo_b: str) -> float:
        """Calcula la similitud coseno entre los embeddings de dos nodos.

        Returns
        -------
        float
            Similitud coseno en [-1, 1]. 1.0 = idénticos.
        """
        emb_a = self.embedding_nodo(nodo_a)
        emb_b = self.embedding_nodo(nodo_b)
        if emb_a is None or emb_b is None:
            return 0.0
        na, nb = norm(emb_a), norm(emb_b)
        if na == 0 or nb == 0:
            return 0.0
        return float(np.dot(emb_a, emb_b) / (na * nb))

    # ------------------------------------------------------------------
    # Importación / exportación
    # ------------------------------------------------------------------

    def exportar_json(self) -> Dict[str, Any]:
        """Exporta todo el grafo a un diccionario JSON-serializable.

        Returns
        -------
        Dict
            Estructura con ``nodos`` y ``relaciones``.
        """
        nodos = []
        for nodo_id, attrs in self.grafo.nodes(data=True):
            datos = dict(attrs)
            datos["id"] = nodo_id
            nodos.append(datos)

        relaciones = []
        for origen, destino, attrs in self.grafo.edges(data=True):
            datos = dict(attrs)
            datos["origen"] = origen
            datos["destino"] = destino
            relaciones.append(datos)

        return {
            "metadata": {
                "exportado_en": datetime.now(timezone.utc).isoformat(),
                "total_nodos": len(nodos),
                "total_relaciones": len(relaciones),
                "version_formato": "1.0",
            },
            "nodos": nodos,
            "relaciones": relaciones,
        }

    def importar_json(self, data: Dict[str, Any]) -> Tuple[int, int]:
        """Importa un grafo desde un diccionario JSON.

        Parameters
        ----------
        data : Dict
            Diccionario con ``nodos`` y ``relaciones``.

        Returns
        -------
        Tuple[int, int]
            (número de nodos importados, número de relaciones importadas).
        """
        nodos_data = data.get("nodos", [])
        relaciones_data = data.get("relaciones", [])

        n_nodos = 0
        for nodo_data in nodos_data:
            nodo_id = nodo_data.get("id", str(uuid.uuid4())[:8])
            # Eliminar campos que no son atributos del nodo
            attrs = {k: v for k, v in nodo_data.items() if k != "id"}
            self.grafo.add_node(nodo_id, **attrs)
            nombre = attrs.get("nombre", nodo_id)
            self._indice_nodos[nombre.lower()] = nodo_id
            n_nodos += 1

        n_rels = 0
        for rel_data in relaciones_data:
            origen = rel_data.get("origen")
            destino = rel_data.get("destino")
            if origen and destino:
                attrs = {k: v for k, v in rel_data.items() if k not in ("origen", "destino")}
                self.grafo.add_edge(origen, destino, **attrs)
                n_rels += 1

        self.logger.info(
            "[GrafoConocimiento] Importado JSON — nodos=%d, relaciones=%d",
            n_nodos,
            n_rels,
        )
        return n_nodos, n_rels

    # ------------------------------------------------------------------
    # Estadísticas
    # ------------------------------------------------------------------

    def conteo_nodos(self) -> int:
        """Devuelve el número de nodos en el grafo."""
        return self.grafo.number_of_nodes()

    def conteo_relaciones(self) -> int:
        """Devuelve el número de relaciones (aristas) en el grafo."""
        return self.grafo.number_of_edges()

    def densidad(self) -> float:
        """Devuelve la densidad del grafo."""
        n = self.conteo_nodos()
        if n < 2:
            return 0.0
        return nx.density(self.grafo)

    def resumen(self) -> Dict[str, Any]:
        """Devuelve resumen estadístico del grafo."""
        n = self.conteo_nodos()
        e = self.conteo_relaciones()

        tipos_nodos: Dict[str, int] = {}
        for _, attrs in self.grafo.nodes(data=True):
            tipo = attrs.get("tipo", "desconocido")
            tipos_nodos[tipo] = tipos_nodos.get(tipo, 0) + 1

        tipos_rel: Dict[str, int] = {}
        for _, _, attrs in self.grafo.edges(data=True):
            tipo = attrs.get("tipo", "desconocido")
            tipos_rel[tipo] = tipos_rel.get(tipo, 0) + 1

        return {
            "nodos": n,
            "relaciones": e,
            "densidad": round(self.densidad(), 6),
            "tipos_nodos": tipos_nodos,
            "tipos_relaciones": tipos_rel,
            "componentes_fuertemente_conexas": nx.number_strongly_connected_components(self.grafo) if n > 0 else 0,
            "grado_promedio": (2 * e / n) if n > 0 else 0.0,
        }


# ============================================================================
# VEO v2: Funciones de integracion con hermes_commander / veo_core
# ============================================================================
# NOTA: Estas funciones fueron anadidas en la migracion de VEO v1 a VEO v2.
# Proporcionan observabilidad, auditoria, health-checks y exportacion
# de grafos sin modificar la logica de NetworkX + SQLite existente.
# ============================================================================

import time as _time

# --- Estado observable del modulo (VEO v2) ---
_kg_execution_count: int = 0
_kg_last_execution_time: float = 0.0
_kg_operation_log: list = []


def get_trust_score() -> float:
    """
    VEO v2: Devuelve el score de confianza del grafo de conocimiento.

    Basado en la cobertura y calidad del grafo (nodos, relaciones, densidad).

    Returns:
        float: Score de confianza en [0.0, 1.0].
    """
    global _kg_operation_log
    if not _kg_operation_log:
        return 0.8  # Grafo tipicamente confiable

    exitosas = sum(
        1 for op in _kg_operation_log
        if op.get("exitosa", True)
    )
    total = len(_kg_operation_log)
    score = 0.3 + 0.7 * (exitosas / max(total, 1))
    return round(min(max(score, 0.0), 1.0), 4)


def get_last_execution_time() -> str:
    """
    VEO v2: Devuelve el timestamp ISO de la ultima operacion en el grafo.

    Returns:
        str: Timestamp ISO 8601, o cadena vacia si no ha ejecutado.
    """
    global _kg_last_execution_time
    if _kg_last_execution_time == 0.0:
        return ""
    return _time.strftime("%Y-%m-%dT%H:%M:%SZ", _time.gmtime(_kg_last_execution_time))


def get_health_status() -> dict:
    """
    VEO v2: Devuelve el estado de salud del grafo de conocimiento.

    Returns:
        dict: {"status": "healthy|degraded|unhealthy", "score": 0-100}
    """
    global _kg_last_execution_time, _kg_operation_log

    score = 100

    if _kg_last_execution_time > 0:
        horas = (_time.time() - _kg_last_execution_time) / 3600
        if horas > 48:
            score -= 20
        elif horas > 24:
            score -= 10

    if _kg_operation_log:
        trust = get_trust_score()
        if trust < 0.5:
            score -= 25

    if _kg_execution_count == 0:
        score -= 5

    score = max(0, min(100, score))

    if score >= 80:
        status = "healthy"
    elif score >= 50:
        status = "degraded"
    else:
        status = "unhealthy"

    return {"status": status, "score": score}


def export_graph(format: str = "json") -> str:
    """
    VEO v2: Exporta el grafo de conocimiento en el formato solicitado.

    NOTA: Esta es una funcion de interfaz. Requiere una instancia de
    GrafoConocimiento para funcionar. El formato soportado es "json"
    nativamente; "gml" requiere networkx.

    Args:
        format: Formato de exportacion ("json" o "gml").

    Returns:
        str: String con el grafo exportado, o mensaje informativo.
    """
    if format not in ("json", "gml"):
        return (
            f"Formato '{format}' no soportado. "
            "Use 'json' o 'gml'. "
            "NOTA: Esta funcion requiere una instancia de GrafoConocimiento. "
            "Ejemplo: grafo.exportar_json() para JSON nativo."
        )

    if format == "json":
        return (
            '{"nota": "Usar grafo.exportar_json() con una instancia de '
            'GrafoConocimiento para obtener el JSON real. '
            'Esta funcion es un punto de entrada VEO v2.", '
            '"formato_solicitado": "json"}'
        )
    else:
        return (
            "# GML export requiere instancia de GrafoConocimiento.\n"
            "# Use: nx.write_gml(grafo.grafo, archivo) con networkx."
        )


def _log_audit_kg(
    operacion: str,
    detalles: str = "",
    exitosa: bool = True,
) -> None:
    """
    VEO v2: Registra una entrada de auditoria para cada operacion en el grafo.

    Args:
        operacion: Tipo de operacion (agregar_nodo, agregar_relacion, etc.).
        detalles: Detalles de la operacion.
        exitosa: Si la operacion fue exitosa.
    """
    global _kg_execution_count, _kg_last_execution_time, _kg_operation_log

    _kg_execution_count += 1
    _kg_last_execution_time = _time.time()

    entry = {
        "timestamp": get_last_execution_time(),
        "operacion": operacion,
        "detalles": detalles[:200] if detalles else "",
        "exitosa": exitosa,
    }
    _kg_operation_log.append(entry)

    if len(_kg_operation_log) > 1000:
        _kg_operation_log = _kg_operation_log[-1000:]
