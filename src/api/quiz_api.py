import logging

from fastapi import APIRouter, FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse

from utils.redis_connection import RedisConnection
from utils.ws_connection import WsConnection


def register_quiz_api(app: FastAPI, ws_connection: WsConnection, redis: RedisConnection):
    router = APIRouter(prefix="/quiz")

    @router.websocket("/ws/test")
    async def test(websocket: WebSocket):
        logging.debug("Attempting WebSocket connection")
        await websocket.accept()
        await websocket.send_text("Connection successful")
        logging.debug("Message sent: Connection successful")

    @router.websocket("/ws/{quiz_id}/{user_id}")
    async def websocket_endpoint(quiz_id: str, user_id: str, websocket: WebSocket):
        await ws_connection.connect(quiz_id, websocket)

        redis.client.hset(f"quiz:{quiz_id}:users", user_id, "connected")  # type: ignore

        user_score = redis.client.hget(f"quiz:{quiz_id}:scores", user_id)
        if not user_score:
            redis.client.hset(f"quiz:{quiz_id}:scores", user_id, 0)
            user_score = 0

        try:
            await websocket.send_json({
                "type": "reconnection_successful",
                "user_id": user_id,
                "current_score": int(user_score),
            })

            while True:
                data = await websocket.receive_json()
                if data["type"] == "submit_answer":
                    answer = data["answer"]
                    score = 10 if answer == "correct" else 0

                    redis.client.hincrby(f"quiz:{quiz_id}:scores", user_id, score)

                    leaderboard = redis.client.hgetall(f"quiz:{quiz_id}:scores")
                    sorted_leaderboard = sorted(leaderboard.items(), key=lambda x: int(x[1]), reverse=True)

                    await ws_connection.broadcast(quiz_id, {
                        "type": "leaderboard_update",
                        "leaderboard": sorted_leaderboard
                    })
        except WebSocketDisconnect:
            redis.client.hset(f"quiz:{quiz_id}:users", user_id, "disconnected")
            ws_connection.disconnect(quiz_id, websocket)
            logging.debug(f"User {user_id} disconnected from quiz {quiz_id}")
        except Exception as e:
            logging.error(f"Unexpected error: {e}")
            await websocket.close()

    @router.post("/join/{quiz_id}/{user_id}")
    async def join_quiz(quiz_id: str, user_id: str):
        if not redis.client.exists(f"quiz:{quiz_id}:scores"):
            redis.client.hset(f"quiz:{quiz_id}:scores", user_id, 0)
        else:
            redis.client.hsetnx(f"quiz:{quiz_id}:scores", user_id, 0)
        return JSONResponse({"message": f"User {user_id} joined quiz {quiz_id}"})

    @router.get("/reconnect/{quiz_id}/{user_id}")
    async def reconnect_user(quiz_id: str, user_id: str):
        if not redis.client.exists(f"quiz:{quiz_id}:scores"):
            raise HTTPException(status_code=404, detail="Quiz not found")

        user_score = redis.client.hget(f"quiz:{quiz_id}:scores", user_id)
        if not user_score:
            raise HTTPException(status_code=404, detail="User not found in the quiz")

        user_status = redis.client.hget(f"quiz:{quiz_id}:users", user_id)
        return JSONResponse({
            "message": "User state retrieved",
            "quiz_id": quiz_id,
            "user_id": user_id,
            "current_score": int(user_score),
            "connection_status": user_status,
        })

    @router.get("/leaderboard/{quiz_id}")
    async def get_leaderboard(quiz_id: str):
        if not redis.client.exists(f"quiz:{quiz_id}:scores"):
            raise HTTPException(status_code=404, detail="Quiz not found")

        leaderboard = redis.client.hgetall(f"quiz:{quiz_id}:scores")
        sorted_leaderboard = sorted(leaderboard.items(), key=lambda x: int(x[1]), reverse=True)
        return JSONResponse({"leaderboard": sorted_leaderboard})

    app.include_router(router)
