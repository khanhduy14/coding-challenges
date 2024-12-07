from typing import Any

from fastapi import WebSocket


class WsConnection:

    def __init__(self) -> None:
        self._active_connections: dict[str, list[WebSocket]] = {}

    async def connect(self, quiz_id: str, websocket: WebSocket):
        await websocket.accept()
        if quiz_id not in self._active_connections:
            self._active_connections[quiz_id] = []
        self._active_connections[quiz_id].append(websocket)

    def disconnect(self, quiz_id: str, websocket: WebSocket):
        if quiz_id in self._active_connections:
            self._active_connections[quiz_id].remove(websocket)
            if not self._active_connections[quiz_id]:
                del self._active_connections[quiz_id]

    async def broadcast(self, quiz_id: str, message: dict[str, Any]):
        if quiz_id in self._active_connections:
            for connection in self._active_connections[quiz_id]:
                await connection.send_json(message)
