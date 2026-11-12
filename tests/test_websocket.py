"""
Tests para WebSocket de VEO v2.0.4D.

Valida:
- Conexión y desconexión
- Envío y recepción de mensajes
- Estadísticas de WebSocket
- Manejo de errores
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

# WebSocket tests require FastAPI TestClient with websocket support
pytestmark = pytest.mark.asyncio


class TestWebSocketManager:
    """Tests para WebSocketManager."""

    async def test_connect_adds_client(self):
        """La conexión añade un cliente a la lista activa."""
        from api.api_server import ws_manager

        mock_ws = MagicMock()
        mock_ws.accept = AsyncMock()

        initial_count = len(ws_manager.active_connections)
        await ws_manager.connect(mock_ws)

        assert len(ws_manager.active_connections) == initial_count + 1
        mock_ws.accept.assert_called_once()

    async def test_disconnect_removes_client(self):
        """La desconexión elimina un cliente de la lista activa."""
        from api.api_server import ws_manager

        mock_ws = MagicMock()
        ws_manager.active_connections.append(mock_ws)
        initial_count = len(ws_manager.active_connections)

        await ws_manager.disconnect(mock_ws)

        assert len(ws_manager.active_connections) == initial_count - 1

    async def test_send_personal_message(self):
        """Envío de mensaje personalizado a un cliente."""
        from api.api_server import ws_manager

        mock_ws = MagicMock()
        mock_ws.send_json = AsyncMock()

        message = {"type": "test", "data": "hello"}
        await ws_manager.send_personal_message(message, mock_ws)

        mock_ws.send_json.assert_called_once_with(message)

    async def test_broadcast_queues_message(self):
        """Broadcast encola el mensaje en las colas de todos los clientes."""
        from api.api_server import ws_manager
        from unittest.mock import AsyncMock, MagicMock

        # Simular un cliente conectado
        mock_ws = MagicMock()
        mock_ws.client.host = "127.0.0.1"
        mock_ws.client.port = 54321
        mock_ws.accept = AsyncMock()
        mock_ws.send_json = AsyncMock()
        client_id = await ws_manager.connect(mock_ws)

        # Vaciar la cola del cliente para test limpio
        client_queue = ws_manager._queues.get(client_id)
        if client_queue:
            while not client_queue.empty():
                try:
                    client_queue.get_nowait()
                except asyncio.QueueEmpty:
                    break

        message = {"type": "broadcast", "data": "all"}
        await ws_manager.broadcast(message)

        # El mensaje debe estar en la cola del cliente (indexada por UUID, no por IP)
        client_queue = ws_manager._queues.get(client_id)
        assert client_queue is not None
        assert not client_queue.empty()
        queued = client_queue.get_nowait()
        assert queued == message

        await ws_manager.disconnect(mock_ws)

    async def test_broadcast_adds_to_history(self):
        """Broadcast guarda el mensaje en el historial de eventos."""
        from api.api_server import ws_manager

        message = {"type": "broadcast", "data": "test"}
        await ws_manager.broadcast(message)

        # El mensaje debe estar en el historial
        assert message in ws_manager._historial_eventos

    def test_ws_stats_attributes(self):
        """Estadísticas iniciales de WebSocket."""
        from api.api_server import ws_manager

        # WebSocketManager expone atributos directamente
        assert hasattr(ws_manager, "active_connections")
        assert hasattr(ws_manager, "mensajes_enviados")
        assert ws_manager.mensajes_enviados >= 0
        assert isinstance(ws_manager.active_connections, list)


class TestWebSocketEndpoint:
    """Tests para el endpoint WebSocket."""

    def test_websocket_endpoint_exists(self):
        """El endpoint /ws existe en la aplicación."""
        from api.api_server import app
        from fastapi.routing import APIWebSocketRoute

        ws_routes = [r for r in app.routes if isinstance(r, APIWebSocketRoute)]
        assert any(r.path == "/ws" for r in ws_routes), "Endpoint /ws no encontrado"

    def test_ws_stats_endpoint_exists(self):
        """El endpoint /api/v1/ws/stats existe."""
        from api.api_server import app

        routes = [r.path for r in app.routes if hasattr(r, 'path')]
        assert "/api/v1/ws/stats" in routes, "Endpoint /api/v1/ws/stats no encontrado"


class TestWebSocketMultiCliente:
    """Tests de integracion: multiples clientes desde la misma IP."""

    async def test_broadcast_a_tres_clientes_misma_ip(self):
        """Tres clientes desde 127.0.0.1 deben recibir TODOS los eventos.

        Regression test para el defecto critico donde la cola se indexaba
        por IP, haciendo que todos los clientes locales compartieran cola
        y los eventos se repartieran en lugar de broadcastearse.
        """
        from api.api_server import WebSocketManager
        from unittest.mock import AsyncMock, MagicMock

        ws_mgr = WebSocketManager()

        # Simular 3 clientes conectados desde la MISMA IP
        clients = []
        for _ in range(3):
            mock_ws = MagicMock()
            mock_ws.client.host = "127.0.0.1"
            mock_ws.client.port = 99999
            mock_ws.accept = AsyncMock()
            mock_ws.send_json = AsyncMock()
            await ws_mgr.connect(mock_ws)
            clients.append(mock_ws)

        # Broadcast de 3 eventos
        for i in range(3):
            await ws_mgr.broadcast({"evento": f"test_{i}"})

        # Verificar que cada cliente tiene su propia cola con los 3 eventos
        for i, mock_ws in enumerate(clients):
            client_id = getattr(mock_ws, "_veo_client_id", None)
            assert client_id is not None, f"Cliente {i} no tiene client_id"
            queue = ws_mgr._queues.get(client_id)
            assert queue is not None, f"Cliente {i} no tiene cola"
            count = 0
            while True:
                try:
                    queue.get_nowait()
                    count += 1
                except asyncio.QueueEmpty:
                    break
            assert count == 3, f"Cliente {i} recibio {count}/3 eventos"

        # Limpiar
        for mock_ws in clients:
            await ws_mgr.disconnect(mock_ws)

    async def test_broadcast_cinco_clientes_cinco_eventos(self):
        """Cinco clientes, cinco eventos: todos reciben los 5."""
        from api.api_server import WebSocketManager
        from unittest.mock import AsyncMock, MagicMock

        ws_mgr = WebSocketManager()
        clients = []
        for _ in range(5):
            mock_ws = MagicMock()
            mock_ws.client.host = "127.0.0.1"
            mock_ws.client.port = 99999
            mock_ws.accept = AsyncMock()
            mock_ws.send_json = AsyncMock()
            await ws_mgr.connect(mock_ws)
            clients.append(mock_ws)

        for i in range(5):
            await ws_mgr.broadcast({"evento": f"e_{i}"})

        for i, mock_ws in enumerate(clients):
            client_id = getattr(mock_ws, "_veo_client_id", None)
            queue = ws_mgr._queues.get(client_id)
            count = 0
            if queue:
                while True:
                    try:
                        queue.get_nowait()
                        count += 1
                    except asyncio.QueueEmpty:
                        break
            assert count == 5, f"Cliente {i} recibio {count}/5 eventos"

        for mock_ws in clients:
            await ws_mgr.disconnect(mock_ws)

    async def test_desconexion_durante_broadcast_no_interrumpe(self):
        """Desconectar un cliente durante broadcast no afecta a los demas."""
        from api.api_server import WebSocketManager
        from unittest.mock import AsyncMock, MagicMock

        ws_mgr = WebSocketManager()
        clients = []
        for _ in range(3):
            mock_ws = MagicMock()
            mock_ws.client.host = "127.0.0.1"
            mock_ws.client.port = 99999
            mock_ws.accept = AsyncMock()
            mock_ws.send_json = AsyncMock()
            await ws_mgr.connect(mock_ws)
            clients.append(mock_ws)

        # Desconectar el cliente del medio
        await ws_mgr.disconnect(clients[1])

        # Broadcast debe funcionar sin error
        await ws_mgr.broadcast({"evento": "post_disconnect"})

        # Los clientes restantes deben recibir el evento
        for idx in [0, 2]:
            client_id = getattr(clients[idx], "_veo_client_id", None)
            queue = ws_mgr._queues.get(client_id)
            count = 0
            if queue:
                while True:
                    try:
                        queue.get_nowait()
                        count += 1
                    except asyncio.QueueEmpty:
                        break
            assert count == 1, f"Cliente {idx} recibio {count}/1 eventos post-desconexion"

        await ws_mgr.disconnect(clients[0])
        await ws_mgr.disconnect(clients[2])
