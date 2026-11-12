# backup_manager.py - VEO v2 Operations
"""
Gestor de backups automaticos para VEO v2.

La clase BackupManager gestiona backups de la base de datos SQLite,
configuracion y otros archivos criticos. Soporta:
    - Backups automaticos programados
    - Backups manuales
    - Restauracion desde backup
    - Limpieza de backups antiguos
    - Rotacion automatica (maximo N backups)
    - Verificacion de integridad

Ejemplo de uso:
    >>> from operations.backup_manager import BackupManager
    >>> bm = BackupManager(db_path="sois.db", backup_dir="backups")
    >>> await bm.create_backup(tipo="manual")
    {'timestamp': '2025-01-01T00:00:00', 'archivo': 'sois_20250101_000000.db', ...}
    >>> backups = await bm.list_backups()
    >>> await bm.restore_backup('20250101_000000')
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

from operations.logger import get_logger

try:
    from core.db import (
        registrar_backup,
        listar_backups,
        marcar_backup_restaurado,
        obtener_conexion,
        cerrar_conexion,
    )
    _DB_DISPONIBLE = True
except ImportError:
    _DB_DISPONIBLE = False

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

DEFAULT_MAX_BACKUPS = 20
DEFAULT_MAX_AGE_DAYS = 30
DEFAULT_DB_NAME = "sois.db"
DEFAULT_CONFIG_FILES = ["config.json", ".env", "settings.yaml"]

# ---------------------------------------------------------------------------
# Logger
# ---------------------------------------------------------------------------

_log = get_logger("operations.backup")


# ---------------------------------------------------------------------------
# Clase BackupManager
# ---------------------------------------------------------------------------

class BackupManager:
    """
    Gestor de backups para VEO v2.

    Gestiona backups de la base de datos SQLite, archivos de
    configuracion y otros archivos criticos del sistema.

    Attributes:
        db_path: Ruta a la base de datos SQLite.
        backup_dir: Directorio donde se almacenan los backups.
        max_backups: Numero maximo de backups a mantener.
        max_age_days: Edad maxima de los backups en dias.
    """

    def __init__(
        self,
        db_path: str | Path = DEFAULT_DB_NAME,
        backup_dir: str | Path = "backups",
        config_dir: str | Path | None = None,
        max_backups: int = DEFAULT_MAX_BACKUPS,
        max_age_days: int = DEFAULT_MAX_AGE_DAYS,
    ) -> None:
        """
        Inicializa el gestor de backups.

        Args:
            db_path: Ruta a la base de datos SQLite.
            backup_dir: Directorio para almacenar backups.
            config_dir: Directorio con archivos de configuracion.
            max_backups: Maximo numero de backups.
            max_age_days: Edad maxima en dias.
        """
        self.db_path = Path(db_path)
        self.backup_dir = Path(backup_dir)
        self.config_dir = Path(config_dir) if config_dir else None
        self.max_backups = max_backups
        self.max_age_days = max_age_days

        # Crear directorio de backups si no existe
        self.backup_dir.mkdir(parents=True, exist_ok=True)

    # -----------------------------------------------------------------------
    # Creacion de backups
    # -----------------------------------------------------------------------

    async def create_backup(
        self,
        tipo: str = "auto",
        nombre_custom: str | None = None,
        notas: str | None = None,
    ) -> dict[str, Any]:
        """
        Crea un backup timestamped de la base de datos.

        Args:
            tipo: Tipo de backup ('auto', 'manual', 'pre_update', 'emergency').
            nombre_custom: Nombre personalizado (opcional).
            notas: Notas sobre el backup.

        Returns:
            Diccionario con informacion del backup creado.

        Raises:
            FileNotFoundError: Si la base de datos no existe.
            RuntimeError: Si falla la creacion del backup.
        """
        if not self.db_path.exists():
            raise FileNotFoundError(f"Base de datos no encontrada: {self.db_path}")

        inicio = time.time()
        timestamp = datetime.now(tz=timezone.utc)
        timestamp_str = timestamp.strftime("%Y%m%d_%H%M%S")

        # Nombre del backup
        if nombre_custom:
            nombre_backup = f"{nombre_custom}_{timestamp_str}.db"
        else:
            nombre_backup = f"sois_{timestamp_str}.db"

        ruta_backup = self.backup_dir / nombre_backup

        try:
            # Copiar archivo de base de datos
            shutil.copy2(str(self.db_path), str(ruta_backup))

            # Verificar integridad del backup
            if not await self._verificar_integridad(ruta_backup):
                ruta_backup.unlink(missing_ok=True)
                raise RuntimeError("El backup generado es corrupto")

            # Calcular checksum
            checksum = await self._calcular_checksum(ruta_backup)

            # Copiar configuracion si existe
            tablas_incluidas = ["completa"]
            config_backup = None
            if self.config_dir and self.config_dir.exists():
                config_backup = await self._backup_configuracion(timestamp_str)

            duracion_ms = int((time.time() - inicio) * 1000)
            tamano_bytes = ruta_backup.stat().st_size

            resultado = {
                "timestamp": timestamp.isoformat(),
                "nombre_backup": nombre_backup,
                "ruta_backup": str(ruta_backup),
                "tamano_bytes": tamano_bytes,
                "tamano_mb": round(tamano_bytes / (1024 * 1024), 2),
                "tipo": tipo,
                "estado": "ok",
                "checksum": checksum,
                "duracion_ms": duracion_ms,
                "tablas_incluidas": tablas_incluidas,
                "config_backup": config_backup,
                "notas": notas,
            }

            # Persistir en DB
            if _DB_DISPONIBLE:
                try:
                    await registrar_backup(
                        nombre_backup=nombre_backup,
                        ruta_backup=str(ruta_backup),
                        tamano_bytes=tamano_bytes,
                        tipo=tipo,
                        tablas_incluidas=tablas_incluidas,
                        duracion_ms=duracion_ms,
                        checksum=checksum,
                        notas=notas,
                    )
                except Exception as exc:
                    _log.warning(f"No se pudo registrar backup en DB: {exc}")

            # Rotacion automatica
            await self._aplicar_rotacion()

            _log.info(
                f"Backup creado: {nombre_backup} ({resultado['tamano_mb']} MB) "
                f"en {duracion_ms}ms"
            )

            return resultado

        except Exception as exc:
            raise RuntimeError(f"Error al crear backup: {exc}") from exc

    async def create_backup_configuracion(self, timestamp_str: str | None = None) -> dict[str, Any] | None:
        """
        Crea un backup exclusivo de archivos de configuracion.

        Args:
            timestamp_str: Timestamp para el nombre del backup.

        Returns:
            Informacion del backup de configuracion, o None.
        """
        if not self.config_dir or not self.config_dir.exists():
            return None

        if timestamp_str is None:
            timestamp_str = datetime.now(tz=timezone.utc).strftime("%Y%m%d_%H%M%S")

        nombre = f"config_{timestamp_str}.zip"
        ruta_backup = self.backup_dir / nombre

        try:
            # Crear zip con archivos de configuracion
            shutil.make_archive(
                base_name=str(ruta_backup.with_suffix("")),
                format="zip",
                root_dir=str(self.config_dir),
            )

            tamano_bytes = ruta_backup.stat().st_size if ruta_backup.exists() else 0

            return {
                "nombre": nombre,
                "ruta": str(ruta_backup),
                "tamano_bytes": tamano_bytes,
                "tamano_mb": round(tamano_bytes / (1024 * 1024), 2),
            }

        except Exception as exc:
            _log.warning(f"Error al backup de configuracion: {exc}")
            return None

    # -----------------------------------------------------------------------
    # Listado de backups
    # -----------------------------------------------------------------------

    async def list_backups(
        self,
        tipo: str | None = None,
        max_resultados: int = 100,
    ) -> list[dict[str, Any]]:
        """
        Lista los backups disponibles.

        Args:
            tipo: Filtrar por tipo ('auto', 'manual', 'pre_update', 'emergency').
            max_resultados: Maximo de resultados.

        Returns:
            Lista de backups ordenados por fecha descendente.
        """
        # Intentar obtener de DB primero
        if _DB_DISPONIBLE:
            try:
                db_backups = await listar_backups(tipo=tipo, limite=max_resultados)
                if db_backups:
                    return db_backups
            except Exception as e:
                logger.warning("[BackupManager] Error al listar backups DB: %s", e)

        # Fallback: escanear directorio
        backups: list[dict[str, Any]] = []

        if not self.backup_dir.exists():
            return backups

        for archivo in sorted(self.backup_dir.glob("sois_*.db"), reverse=True):
            try:
                stat = archivo.stat()
                backups.append({
                    "nombre_backup": archivo.name,
                    "ruta_backup": str(archivo),
                    "tamano_bytes": stat.st_size,
                    "tamano_mb": round(stat.st_size / (1024 * 1024), 2),
                    "timestamp": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
                    "tipo": "auto",  # No podemos saber el tipo sin DB
                })
            except Exception:
                continue

        if tipo:
            backups = [b for b in backups if b.get("tipo") == tipo]

        return backups[:max_resultados]

    # -----------------------------------------------------------------------
    # Restauracion
    # -----------------------------------------------------------------------

    async def restore_backup(
        self,
        timestamp: str,
        confirmar: bool = False,
    ) -> dict[str, Any]:
        """
        Restaura la base de datos desde un backup.

        Args:
            timestamp: Timestamp del backup (formato: YYYYMMDD_HHMMSS).
            confirmar: Si True, no pide confirmacion.

        Returns:
            Informacion de la restauracion.

        Raises:
            FileNotFoundError: Si no se encuentra el backup.
            RuntimeError: Si falla la restauracion.
        """
        # Buscar el backup
        ruta_backup = self.backup_dir / f"sois_{timestamp}.db"
        if not ruta_backup.exists():
            # Buscar con patron mas amplio
            candidatos = list(self.backup_dir.glob(f"*{timestamp}*.db"))
            if candidatos:
                ruta_backup = candidatos[0]
            else:
                raise FileNotFoundError(f"Backup no encontrado: {timestamp}")

        # Verificar integridad antes de restaurar
        if not await self._verificar_integridad(ruta_backup):
            raise RuntimeError(f"El backup {timestamp} es corrupto")

        # Crear backup de seguridad antes de restaurar
        if confirmar:
            backup_seguridad = None
            if self.db_path.exists():
                ts_seg = datetime.now(tz=timezone.utc).strftime("%Y%m%d_%H%M%S")
                nombre_seg = f"sois_pre_restore_{ts_seg}.db"
                ruta_seg = self.backup_dir / nombre_seg
                shutil.copy2(str(self.db_path), str(ruta_seg))
                backup_seguridad = str(ruta_seg)

            # Cerrar conexion a DB si esta abierta
            if _DB_DISPONIBLE:
                try:
                    await cerrar_conexion()
                except Exception as e:
                    _log.warning("[BackupManager] Error al cerrar conexion DB: %s", e)

            # Restaurar
            shutil.copy2(str(ruta_backup), str(self.db_path))

            resultado = {
                "timestamp": _ahora(),
                "backup_restaurado": ruta_backup.name,
                "ruta_original": str(self.db_path),
                "backup_seguridad": backup_seguridad,
                "estado": "ok",
            }

            # Marcar como restaurado en DB
            if _DB_DISPONIBLE:
                try:
                    # Reconectar
                    from core.db import obtener_conexion
                    await obtener_conexion(str(self.db_path))

                    # Buscar ID del backup
                    db = await obtener_conexion()
                    cursor = await db.execute(
                        "SELECT id FROM backups_registro WHERE nombre_backup = ?",
                        (ruta_backup.name,),
                    )
                    fila = await cursor.fetchone()
                    await cursor.close()
                    if fila:
                        await marcar_backup_restaurado(fila["id"])
                except Exception as exc:
                    _log.warning(f"No se pudo marcar backup como restaurado: {exc}")

            _log.info(f"Backup restaurado: {ruta_backup.name}")
            return resultado
        else:
            return {
                "estado": "pendiente_confirmacion",
                "backup": ruta_backup.name,
                "tamano_mb": round(ruta_backup.stat().st_size / (1024 * 1024), 2),
                "mensaje": "Use confirmar=True para ejecutar la restauracion",
            }

    # -----------------------------------------------------------------------
    # Limpieza
    # -----------------------------------------------------------------------

    async def cleanup_old_backups(
        self,
        max_age_days: int | None = None,
    ) -> dict[str, Any]:
        """
        Elimina backups mas antiguos que el limite especificado.

        Args:
            max_age_days: Edad maxima en dias (usa el del constructor si None).

        Returns:
            Informacion de la limpieza realizada.
        """
        max_age = max_age_days or self.max_age_days
        fecha_limite = datetime.now(tz=timezone.utc) - timedelta(days=max_age)
        limite_timestamp = fecha_limite.timestamp()

        eliminados = []
        espacio_liberado = 0

        for archivo in self.backup_dir.glob("sois_*.db"):
            try:
                stat = archivo.stat()
                if stat.st_mtime < limite_timestamp:
                    tamano = stat.st_size
                    archivo.unlink()
                    eliminados.append({
                        "nombre": archivo.name,
                        "tamano_bytes": tamano,
                        "fecha": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
                    })
                    espacio_liberado += tamano
            except Exception as exc:
                _log.warning(f"No se pudo eliminar {archivo}: {exc}")

        # Tambien limpiar backups de config antiguos
        for archivo in self.backup_dir.glob("config_*.zip"):
            try:
                stat = archivo.stat()
                if stat.st_mtime < limite_timestamp:
                    tamano = stat.st_size
                    archivo.unlink()
                    espacio_liberado += tamano
            except Exception as e:
                _log.warning("[BackupManager] Error al limpiar backup config %s: %s", archivo.name, e)

        _log.info(
            f"Limpieza completada: {len(eliminados)} backups eliminados, "
            f"{espacio_liberado / (1024 * 1024):.2f} MB liberados"
        )

        return {
            "eliminados": len(eliminados),
            "espacio_liberado_bytes": espacio_liberado,
            "espacio_liberado_mb": round(espacio_liberado / (1024 * 1024), 2),
            "detalle": eliminados,
            "fecha_limite": fecha_limite.isoformat(),
        }

    async def _aplicar_rotacion(self) -> None:
        """Aplica rotacion de backups si se excede el maximo."""
        backups = sorted(
            self.backup_dir.glob("sois_*.db"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )

        if len(backups) > self.max_backups:
            a_eliminar = backups[self.max_backups:]
            for archivo in a_eliminar:
                try:
                    archivo.unlink()
                    _log.debug(f"Backup eliminado por rotacion: {archivo.name}")
                except Exception as exc:
                    _log.warning(f"Error eliminando backup en rotacion: {exc}")

    # -----------------------------------------------------------------------
    # Verificacion
    # -----------------------------------------------------------------------

    async def _verificar_integridad(self, ruta: Path) -> bool:
        """
        Verifica la integridad de un archivo de base de datos.

        Args:
            ruta: Ruta al archivo SQLite.

        Returns:
            True si el archivo es valido.
        """
        try:
            conn = sqlite3.connect(str(ruta))
            cursor = conn.cursor()
            cursor.execute("PRAGMA integrity_check")
            resultado = cursor.fetchone()
            conn.close()
            return resultado is not None and resultado[0] == "ok"
        except Exception as exc:
            _log.warning(f"Error verificando integridad de {ruta}: {exc}")
            return False

    async def _calcular_checksum(self, ruta: Path) -> str:
        """
        Calcula el checksum SHA-256 de un archivo.

        Args:
            ruta: Ruta al archivo.

        Returns:
            Hash SHA-256 en hexadecimal.
        """
        sha256 = hashlib.sha256()
        with open(ruta, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)
        return sha256.hexdigest()

    async def _backup_configuracion(self, timestamp_str: str) -> dict[str, Any] | None:
        """Crea backup de archivos de configuracion."""
        return await self.create_backup_configuracion(timestamp_str)

    # -----------------------------------------------------------------------
    # Utilidades
    # -----------------------------------------------------------------------

    async def verificar_backup(self, timestamp: str) -> dict[str, Any]:
        """
        Verifica la integridad de un backup especifico.

        Args:
            timestamp: Timestamp del backup.

        Returns:
            Resultado de la verificacion.
        """
        ruta_backup = self.backup_dir / f"sois_{timestamp}.db"
        if not ruta_backup.exists():
            return {"estado": "no_encontrado", "timestamp": timestamp}

        integridad_ok = await self._verificar_integridad(ruta_backup)
        checksum_actual = await self._calcular_checksum(ruta_backup)

        return {
            "timestamp": timestamp,
            "ruta": str(ruta_backup),
            "tamano_mb": round(ruta_backup.stat().st_size / (1024 * 1024), 2),
            "integridad_ok": integridad_ok,
            "checksum": checksum_actual,
            "estado": "ok" if integridad_ok else "corrupto",
        }

    async def espacio_utilizado(self) -> dict[str, Any]:
        """
        Calcula el espacio utilizado por los backups.

        Returns:
            Informacion de espacio.
        """
        total_bytes = 0
        num_backups = 0

        for archivo in self.backup_dir.glob("sois_*.db"):
            total_bytes += archivo.stat().st_size
            num_backups += 1

        return {
            "directorio": str(self.backup_dir),
            "num_backups": num_backups,
            "total_bytes": total_bytes,
            "total_mb": round(total_bytes / (1024 * 1024), 2),
            "total_gb": round(total_bytes / (1024 * 1024 * 1024), 3),
            "max_backups_configurado": self.max_backups,
            "max_age_days_configurado": self.max_age_days,
        }


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------

def _ahora() -> str:
    """Devuelve el timestamp actual en formato ISO 8601 UTC."""
    return datetime.now(tz=timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Demo
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import asyncio
    import tempfile

    async def demo():
        print("=" * 60)
        print("DEMO: Backup Manager VEO v2")
        print("=" * 60)

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            db_path = tmp / "test.db"
            backup_dir = tmp / "backups"

            # Crear DB de prueba
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()
            cursor.execute("CREATE TABLE test (id INTEGER PRIMARY KEY, data TEXT)")
            for i in range(100):
                cursor.execute("INSERT INTO test (data) VALUES (?)", (f"dato_{i}",))
            conn.commit()
            conn.close()

            bm = BackupManager(
                db_path=db_path,
                backup_dir=backup_dir,
                max_backups=10,
                max_age_days=30,
            )

            print(f"\n--- DB original: {db_path} ({db_path.stat().st_size} bytes) ---")

            print("\n--- Creando backup manual ---")
            backup1 = await bm.create_backup(tipo="manual", notas="Backup de prueba")
            print(f"  Backup: {backup1['nombre_backup']}")
            print(f"  Tamano: {backup1['tamano_mb']} MB")
            print(f"  Checksum: {backup1['checksum'][:16]}...")
            print(f"  Duracion: {backup1['duracion_ms']} ms")

            print("\n--- Creando backup automatico ---")
            backup2 = await bm.create_backup(tipo="auto")
            print(f"  Backup: {backup2['nombre_backup']}")

            print("\n--- Listando backups ---")
            backups = await bm.list_backups()
            for b in backups:
                print(f"  - {b['nombre_backup']:35s} | {b['tamano_mb']:6.2f} MB | {b['tipo']}")

            print("\n--- Verificando integridad ---")
            ts = backup1['timestamp'].split('T')[0].replace('-', '')
            verificacion = await bm.verificar_backup(backup1['nombre_backup'].replace('sois_', '').replace('.db', ''))
            print(f"  Integridad: {'OK' if verificacion['integridad_ok'] else 'FALLIDA'}")
            print(f"  Checksum: {verificacion['checksum'][:16]}...")

            print("\n--- Espacio utilizado ---")
            espacio = await bm.espacio_utilizado()
            print(f"  Backups: {espacio['num_backups']}")
            print(f"  Total: {espacio['total_mb']} MB")

            print("\n--- Restauracion (simulada) ---")
            resultado = await bm.restore_backup(
                backup1['nombre_backup'].replace('sois_', '').replace('.db', ''),
                confirmar=False,
            )
            print(f"  Estado: {resultado['estado']}")
            print(f"  Backup: {resultado['backup']}")
            print(f"  Nota: {resultado['mensaje']}")

            print("\n--- Limpieza ---")
            cleanup = await bm.cleanup_old_backups(max_age_days=0)
            print(f"  Eliminados: {cleanup['eliminados']}")
            print(f"  Espacio liberado: {cleanup['espacio_liberado_mb']} MB")

        print("\n" + "=" * 60)
        print("Demo completada.")
        print("=" * 60)

    asyncio.run(demo())
