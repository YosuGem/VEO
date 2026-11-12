"""
================================================================================
Test de Integracion API → HermesCommander → Modulos Reales
================================================================================
Verifica que la API delega correctamente en HermesCommander y que este usa
los modulos reales de analysis/ (AgenteCientifico, AgenteEsceptico,
CoordinadorValidacion, SimuladorEscenarios) en lugar de generar datos
artificiales con random.

Estos tests requieren que HermesCommander esté disponible (no MockDatabase).
Si MockDatabase está activo, los tests se saltan con pytest.skip().
================================================================================
"""

import pytest
import asyncio
import sys
from pathlib import Path

script_dir = Path(__file__).resolve().parent
project_root = script_dir.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from api.api_server import HermesCommanderAdapter


async def _with_adapter(func):
    """Helper que crea, inicia y detiene el adapter para cada test."""
    adapter = HermesCommanderAdapter()
    if hasattr(adapter.commander, "start"):
        await adapter.commander.start()
    try:
        return await func(adapter)
    finally:
        if hasattr(adapter.commander, "stop"):
            await asyncio.wait_for(adapter.commander.stop(), timeout=5)


@pytest.mark.asyncio
async def test_adapter_delegates_to_real_commander():
    """Verifica que el adapter tenga un commander real (no MockDatabase)."""
    async def _test(adapter):
        assert type(adapter.commander).__name__ != "MockDatabase", (
            "HermesCommander no disponible; test requiere backend real"
        )
    await _with_adapter(_test)


@pytest.mark.asyncio
async def test_create_hypothesis_returns_real_analysis():
    """POST /api/v1/hipotesis → HermesCommander.create_hypothesis → AgenteCientifico + AgenteEsceptico"""
    async def _test(adapter):
        if type(adapter.commander).__name__ == "MockDatabase":
            pytest.skip("Requiere HermesCommander real")

        hypo = await adapter.crear_hipotesis(data={
            "texto": "El cambio climatico aumenta la frecuencia de huracanes",
            "contexto": {"dominio": "clima"},
            "confianza": 0.7,
        })

        # El adapter devuelve la hipotesis directamente (formato HipotesisResponse)
        assert isinstance(hypo, dict)
        assert hypo["id"].startswith("hyp_")
        assert "cientifico" in hypo
        assert "esceptico" in hypo
        assert "nei" in hypo
        # Verificar que NO es simulacion (no tiene campo modo=simulacion_demostracion)
        assert hypo.get("modo") != "simulacion_demostracion"

    await _with_adapter(_test)


@pytest.mark.asyncio
async def test_list_hypotheses_returns_real_data():
    """GET /api/v1/hipotesis → HermesCommander.list_hypotheses"""
    async def _test(adapter):
        if type(adapter.commander).__name__ == "MockDatabase":
            pytest.skip("Requiere HermesCommander real")

        await adapter.crear_hipotesis(data={
            "texto": "Prueba de listado de hipotesis",
            "contexto": {},
            "confianza": 0.5,
        })

        lista = await adapter.listar_hipotesis()
        assert isinstance(lista, list)
        assert len(lista) >= 1
        # Verificar que los items tienen estructura de hipotesis real
        for h in lista:
            assert "id" in h
            assert "texto" in h or "text" in h

    await _with_adapter(_test)


@pytest.mark.asyncio
async def test_get_hypothesis_by_id():
    """GET /api/v1/hipotesis/{id} → HermesCommander.get_hypothesis"""
    async def _test(adapter):
        if type(adapter.commander).__name__ == "MockDatabase":
            pytest.skip("Requiere HermesCommander real")

        created = await adapter.crear_hipotesis(data={
            "texto": "Recuperacion por ID",
            "contexto": {},
            "confianza": 0.6,
        })
        hid = created["id"]

        h = await adapter.get_hipotesis(hid)
        assert isinstance(h, dict)
        assert h.get("id") == hid

    await _with_adapter(_test)


@pytest.mark.asyncio
async def test_validate_hypothesis_returns_real_verdict():
    """POST /api/v1/hipotesis/{id}/validar → HermesCommander.validate_hypothesis → CoordinadorValidacion"""
    async def _test(adapter):
        if type(adapter.commander).__name__ == "MockDatabase":
            pytest.skip("Requiere HermesCommander real")

        created = await adapter.crear_hipotesis(data={
            "texto": "Validacion con CoordinadorValidacion real",
            "contexto": {},
            "confianza": 0.6,
        })
        hid = created["id"]

        # El adapter devuelve la hipotesis actualizada tras la validacion
        h = await adapter.validar_hipotesis(hid)
        assert isinstance(h, dict)
        assert h.get("id") == hid
        # La validacion actualiza el estado de la hipotesis
        assert "estado" in h

    await _with_adapter(_test)


@pytest.mark.asyncio
async def test_persistence_between_restarts():
    """Verifica que las hipotesis persistent entre reinicios de HermesCommander."""
    async def _test(adapter):
        if type(adapter.commander).__name__ == "MockDatabase":
            pytest.skip("Requiere HermesCommander real")

        # Crear hipotesis
        created = await adapter.crear_hipotesis(data={
            "texto": "Hipotesis para probar persistencia entre reinicios",
            "contexto": {},
            "confianza": 0.6,
        })
        assert isinstance(created, dict)
        assert "id" in created
        hid = created["id"]

        # Detener el commander (simula reinicio)
        if hasattr(adapter.commander, "stop"):
            await asyncio.wait_for(adapter.commander.stop(), timeout=5)

        # Crear un nuevo adapter (simula reinicio del proceso)
        new_adapter = HermesCommanderAdapter()
        if hasattr(new_adapter.commander, "start"):
            await new_adapter.commander.start()

        try:
            # Recuperar hipotesis desde el nuevo adapter
            h = await new_adapter.get_hipotesis(hid)
            assert isinstance(h, dict)
            assert h.get("id") == hid
        finally:
            if hasattr(new_adapter.commander, "stop"):
                await asyncio.wait_for(new_adapter.commander.stop(), timeout=5)

    # Este test maneja su propio ciclo de vida del adapter
    adapter = HermesCommanderAdapter()
    if hasattr(adapter.commander, "start"):
        await adapter.commander.start()
    try:
        await _test(adapter)
    finally:
        if hasattr(adapter.commander, "stop"):
            await asyncio.wait_for(adapter.commander.stop(), timeout=5)


@pytest.mark.asyncio
async def test_simulate_scenario_returns_real_simulation():
    """POST /api/v1/escenarios/{id}/simular → HermesCommander.simulate_scenario → SimuladorEscenarios"""
    async def _test(adapter):
        if type(adapter.commander).__name__ == "MockDatabase":
            pytest.skip("Requiere HermesCommander real")

        # Hipotesis con texto rico en variables causales para generar grafo real
        created = await adapter.crear_hipotesis(data={
            "texto": "El aumento de temperatura causa sequias y las sequias provocan escasez de alimentos",
            "contexto": {},
            "confianza": 0.7,
        })
        hid = created["id"]

        sim = await adapter.simular_escenario(hid)
        assert sim is not None
        assert isinstance(sim, dict)
        assert "error" not in sim

        # Verificar que la simulacion produjo resultados no triviales
        # (la varianza debe ser > 0 cuando hay propagacion causal real)
        assert sim.get("variance", 0) > 0, (
            "La varianza debe ser > 0 cuando el grafo causal tiene nodos y relaciones"
        )
        assert sim.get("escenarios_generados", 0) >= 1

    await _with_adapter(_test)


@pytest.mark.asyncio
async def test_simulate_scenario_without_causal_variables_falls_back():
    """Simulacion con texto vacio o sin variables debe manejarse sin error."""
    async def _test(adapter):
        if type(adapter.commander).__name__ == "MockDatabase":
            pytest.skip("Requiere HermesCommander real")

        created = await adapter.crear_hipotesis(data={
            "texto": "Texto muy corto sin causas",  # Texto sin patrones causales claros
            "contexto": {},
            "confianza": 0.5,
        })
        assert isinstance(created, dict) and "id" in created, f"Error creando hipotesis: {created}"
        hid = created["id"]

        sim = await adapter.simular_escenario(hid)
        assert sim is not None
        assert isinstance(sim, dict)
        # Debe devolver un resultado aunque sea con variables por defecto
        assert "monte_carlo_mean" in sim

    await _with_adapter(_test)
