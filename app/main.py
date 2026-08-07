import logging

from fastapi import FastAPI

from config import settings

logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(settings.app_name)

app = FastAPI(title=settings.app_name)


@app.on_event("startup")
async def on_startup() -> None:
    logger.info("Starting %s in %s mode", settings.app_name, settings.app_env)


@app.get("/")
async def root() -> dict:
    return {"service": settings.app_name, "env": settings.app_env}


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
