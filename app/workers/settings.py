from arq.connections import RedisSettings

from app.core.config import settings


def get_redis_settings() -> RedisSettings:
    return RedisSettings.from_dsn(settings.redis_url)


class WorkerSettings:
    redis_settings = get_redis_settings()
    functions: list = []
