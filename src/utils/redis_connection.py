from redis import Redis


class RedisConnection:

    def __init__(self, host: str, port: int = 6379) -> None:
        self._client = Redis(host=host, port=port, decode_responses=True)

    @property
    def client(self) -> Redis:
        return self._client
