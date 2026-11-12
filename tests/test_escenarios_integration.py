"""
Tests de integracion end-to-end para el ciclo completo de escenarios.

Estos tests reproducen el defecto real corregido:
- HermesCommander.list_scenarios() devuelve {"scenarios": []}
- El adapter retorna [] sin llegar al fallback de MockDatabase
- Resultado: escenarios creados en MockDatabase son invisibles

Y verifican que la correccion funciona:
- Cuando list_scenarios devuelve vacio, el adapter cae al mock
- Todas las operaciones usan el mismo almacenamiento
"""

import pytest
from unittest.mock import AsyncMock, MagicMock


class FakeHermesCommander:
    """Simula HermesCommander con list_scenarios que devuelve lista vacia
    (comportamiento real observado en ejecucion).

    Cuando no encuentra un escenario, devuelve None (comportamiento real
        cuando el worker no ha procesado el comando o el escenario no existe).
    """

    async def list_scenarios(self):
        return {"status": "ok", "scenarios": [], "total": 0}

    async def simulate_scenario(self, hyp_id, **kwargs):
        # Simula que el worker no ha procesado el comando → devuelve None
        return None

    async def get_scenario_results(self, scenario_id):
        # Simula que el escenario no existe en el almacenamiento del commander
        return None


class TestEscenariosFallback:
    """Prueba que el adapter cae correctamente al MockDatabase cuando
    HermesCommander devuelve datos vacios."""

    @pytest.fixture
    def adapter(self):
        """Adapter con FakeHermesCommander + MockDatabase real."""
        from api.api_server import HermesCommanderAdapter, MockDatabase
        adapter = HermesCommanderAdapter.__new__(HermesCommanderAdapter)
        adapter.commander = FakeHermesCommander()
        adapter._mock_db = MockDatabase()
        return adapter

    @pytest.mark.asyncio
    async def test_ciclo_completo_con_fallback(self, adapter):
        """Secuencia: CREAR -> LISTAR -> GET -> SIMULAR -> RESULTADOS."""
        # 1. CREAR (siempre va al mock porque commander no tiene crear_escenario)
        creado = await adapter.crear_escenario({
            "nombre": "Ciclo S", "variables": {"A": 0.6, "B": 0.4}
        })
        assert creado is not None
        sid = creado["id"]
        assert sid.startswith("S-")

        # 2. LISTAR — FakeHermesCommander devuelve [], debe caer al mock
        lista = await adapter.listar_escenarios()
        ids = [e["id"] for e in lista]
        assert sid in ids, f"Fallback fallo: {sid} no en {ids}"

        # 3. GET individual — FakeHermesCommander devuelve error, cae al mock
        e = await adapter.get_escenario(sid)
        assert e is not None
        assert e["id"] == sid

        # 4. SIMULAR — FakeHermesCommander devuelve error, cae al mock
        sim = await adapter.simular_escenario(sid)
        assert sim is not None
        assert sim.get("resultado") is not None

        # 5. RESULTADOS (via get_escenario + extraer resultado)
        e2 = await adapter.get_escenario(sid)
        assert e2.get("resultado") is not None
        assert "distribucion" in e2["resultado"]

    @pytest.mark.asyncio
    async def test_listar_escenarios_fallback_cuando_vacio(self, adapter):
        """Regression: list_scenarios vacio -> fallback a MockDatabase."""
        # Crear un escenario en el mock
        await adapter.crear_escenario({"nombre": "Test", "variables": {}})

        # list_scenarios del commander devuelve vacio
        result = await adapter.commander.list_scenarios()
        assert result.get("scenarios") == []

        # El adapter debe caer al mock y encontrar el escenario
        lista = await adapter.listar_escenarios()
        assert len(lista) >= 1

    @pytest.mark.asyncio
    async def test_simular_escenario_inexistente_no_500(self, adapter):
        """Simular escenario inexistente debe devolver None (no excepcion)."""
        result = await adapter.simular_escenario("S-INEXISTENTE")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_escenario_inexistente(self, adapter):
        """GET escenario inexistente devuelve None."""
        result = await adapter.get_escenario("S-INEXISTENTE")
        assert result is None

    @pytest.mark.asyncio
    async def test_varios_escenarios_persisten(self, adapter):
        """Crear 3 escenarios y verificar que todos aparecen en lista."""
        sids = []
        for i in range(3):
            e = await adapter.crear_escenario({
                "nombre": f"Multi {i}", "variables": {"X": 0.5}
            })
            sids.append(e["id"])

        lista = await adapter.listar_escenarios()
        ids = [e["id"] for e in lista]
        for sid in sids:
            assert sid in ids

    @pytest.mark.asyncio
    async def test_simular_distintos_escenarios(self, adapter):
        """Simular 2 escenarios y verificar resultados independientes."""
        for i, vars_dict in enumerate([{"A": 0.8, "B": 0.2}, {"C": 0.3, "D": 0.7}]):
            e = await adapter.crear_escenario({
                "nombre": f"Sim {i}", "variables": vars_dict
            })
            sid = e["id"]
            sim = await adapter.simular_escenario(sid)
            assert sim is not None
            assert sim.get("resultado") is not None


class TestEscenariosMismoAlmacenamiento:
    """Verifica que CREAR y LISTAR usan exactamente la misma instancia."""

    @pytest.mark.asyncio
    async def test_identity_mock_database(self):
        """El _mock_db del adapter es la misma instancia donde se crean escenarios."""
        from api.api_server import HermesCommanderAdapter, MockDatabase

        # Crear adapter forzando modo mock (sin HermesCommander real)
        adapter = HermesCommanderAdapter.__new__(HermesCommanderAdapter)
        adapter.commander = MockDatabase()  # modo fallback
        adapter._mock_db = adapter.commander  # misma instancia

        creado = await adapter.crear_escenario({"nombre": "Identity", "variables": {}})
        sid = creado["id"]

        # listar_escenarios usa commander (que es el mismo MockDatabase)
        lista = await adapter.listar_escenarios()
        ids = [e["id"] for e in lista]
        assert sid in ids

    @pytest.mark.asyncio
    async def test_identity_con_hermes_commander_falso(self):
        """Cuando commander es FakeHC y mock es MockDatabase, el fallback
        garantiza que se lea del mismo lugar donde se creo."""
        from api.api_server import HermesCommanderAdapter, MockDatabase

        adapter = HermesCommanderAdapter.__new__(HermesCommanderAdapter)
        adapter.commander = FakeHermesCommander()
        adapter._mock_db = MockDatabase()

        # Crear en mock
        creado = await adapter.crear_escenario({"nombre": "Identity2", "variables": {}})
        sid = creado["id"]

        # Verificar que listar cae al mock
        lista = await adapter.listar_escenarios()
        ids = [e["id"] for e in lista]
        assert sid in ids, "CREAR y LISTAR usan almacenamientos DIFERENTES"
