import json
import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Response
from sqlalchemy.orm import Session

import crud
import schemas
from config import settings
from database import Base, engine, get_db
from redis_client import redis_client
from bmi_dashboard.api import router as bmi_router
from bmi_dashboard.startup import startup as bmi_startup

logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(settings.app_name)

ITEM_CACHE_TTL_SECONDS = 30


@asynccontextmanager
async def lifespan(_: FastAPI):
    logger.info("Starting %s in %s mode", settings.app_name, settings.app_env)
    Base.metadata.create_all(bind=engine)
    bmi_startup()  # no-op unless the BMI dashboard is configured; migrations failures stop the app on purpose
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.include_router(bmi_router)


@app.get("/")
async def root() -> dict:
    return {"service": settings.app_name, "env": settings.app_env}


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.post("/items", response_model=schemas.ItemRead, status_code=201)
def create_item(item: schemas.ItemCreate, db: Session = Depends(get_db)):
    return crud.create_item(db, item)


@app.get("/items", response_model=list[schemas.ItemRead])
def list_items(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return crud.get_items(db, skip, limit)


@app.get("/items/{item_id}", response_model=schemas.ItemRead)
def read_item(item_id: int, response: Response, db: Session = Depends(get_db)):
    cache_key = f"item:{item_id}"
    cached = redis_client.get(cache_key)
    if cached is not None:
        response.headers["X-Cache"] = "HIT"
        return json.loads(cached)

    db_item = crud.get_item(db, item_id)
    if db_item is None:
        raise HTTPException(status_code=404, detail="Item not found")

    item = schemas.ItemRead.model_validate(db_item)
    redis_client.setex(cache_key, ITEM_CACHE_TTL_SECONDS, item.model_dump_json())
    response.headers["X-Cache"] = "MISS"
    return item


@app.put("/items/{item_id}", response_model=schemas.ItemRead)
def update_item(item_id: int, item: schemas.ItemUpdate, db: Session = Depends(get_db)):
    db_item = crud.update_item(db, item_id, item)
    if db_item is None:
        raise HTTPException(status_code=404, detail="Item not found")
    redis_client.delete(f"item:{item_id}")
    return db_item


@app.delete("/items/{item_id}", status_code=204)
def delete_item(item_id: int, db: Session = Depends(get_db)):
    db_item = crud.delete_item(db, item_id)
    if db_item is None:
        raise HTTPException(status_code=404, detail="Item not found")
    redis_client.delete(f"item:{item_id}")
