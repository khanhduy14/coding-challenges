import logging

import uvicorn
from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

from api.quiz_api import register_quiz_api
from utils.redis_connection import RedisConnection
from utils.ws_connection import WsConnection


def main():
    log_fmt = "%(asctime)s %(levelname)-7s - %(name)-20s: %(message)s"
    logging.basicConfig(level=logging.INFO, format=log_fmt, datefmt="%Y-%m-%d %H:%M:%S")
    redis = RedisConnection(host="localhost")
    ws_connection = WsConnection()

    app = FastAPI()

    register_quiz_api(app, ws_connection, redis)

    app.add_middleware(CORSMiddleware,
                       allow_origins=["*"],
                       allow_credentials=True,
                       allow_methods=["*"],
                       allow_headers=["*"])
    uvicorn.run(app, host="localhost", port=8000, log_config=None)


if __name__ == "__main__":
    main()
