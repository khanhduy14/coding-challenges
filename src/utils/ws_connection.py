import asyncio
import json
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from fastapi import WebSocket
from redis import Redis


class WsConnection:

    def __init__(self, redis_client: Redis):
        self.redis_client = redis_client
        self.local_connections = {}
        self.relay_tasks = {}
        self.executor = ThreadPoolExecutor()

    async def connect(self, quiz_id: str, user_id: str, websocket):
        await websocket.accept()

        if quiz_id not in self.local_connections:
            self.local_connections[quiz_id] = {}
        self.local_connections[quiz_id][user_id] = websocket

        if quiz_id not in self.relay_tasks:
            self.relay_tasks[quiz_id] = asyncio.create_task(self.relay_message(quiz_id))

    def disconnect(self, quiz_id: str, user_id: str):
        if quiz_id in self.local_connections and user_id in self.local_connections[quiz_id]:
            del self.local_connections[quiz_id][user_id]
            if not self.local_connections[quiz_id]:
                del self.local_connections[quiz_id]

        if quiz_id in self.local_connections and not self.local_connections[quiz_id]:
            task = self.relay_tasks.pop(quiz_id, None)
            if task:
                task.cancel()

    async def broadcast(self, quiz_id: str, message: dict[str, Any]):
        self.redis_client.publish(f"quiz:{quiz_id}:channel", json.dumps(message))

    def blocking_pubsub_listener(self, pubsub):
        for message in pubsub.listen():
            if message["type"] == "message":
                yield message

    async def relay_message(self, quiz_id: str):
        pubsub = self.redis_client.pubsub()
        pubsub.subscribe(f"quiz:{quiz_id}:channel")

        loop = asyncio.get_event_loop()

        async def handle_message(data):
            if quiz_id in self.local_connections:
                disconnected_clients = []
                for user_id, websocket in self.local_connections[quiz_id].items():
                    try:
                        await websocket.send_json(data)
                        print(f"Broadcasted to {user_id}: {data}")
                    except Exception as e:
                        print(f"Failed to send message to {user_id}: {e}")
                        disconnected_clients.append(user_id)
                for user_id in disconnected_clients:
                    del self.local_connections[quiz_id][user_id]

        try:
            while True:
                message = await loop.run_in_executor(self.executor, lambda: next(self.blocking_pubsub_listener(pubsub)))
                if message and message["type"] == "message":
                    data = json.loads(message["data"])
                    print(f"Received message from Redis: {data}")
                    await handle_message(data)
        except asyncio.CancelledError:
            await pubsub.unsubscribe(f"quiz:{quiz_id}:channel")
            pubsub.close()
