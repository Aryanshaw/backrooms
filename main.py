"""FastAPI dashboard HTTP API."""

import os
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI

from config.db import connect_db
from config.logger import get_logger
from routes.rooms import router as rooms_router


logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("FastAPI dashboard API startup initiated.")
    async with connect_db() as db:
        app.state.db = db
        logger.info("FastAPI dashboard API startup completed.")
        yield
    logger.info("FastAPI dashboard API shutdown completed.")


app = FastAPI(title="Backrooms Dashboard API", lifespan=lifespan)

app.include_router(rooms_router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8080, reload=True)
