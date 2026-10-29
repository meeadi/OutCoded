from contextlib import asynccontextmanager

import asyncpg
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.db import create_pool, get_conn
from app.routers import profiles, solo, matches


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.pool = await create_pool(get_settings().database_url)
    yield
    await app.state.pool.close()


app = FastAPI(
    title="OutCoded API",
    version="0.1.0",
    description="Competitive coding puzzles. The server is the referee.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(profiles.router)
app.include_router(solo.router)
app.include_router(matches.router)


@app.get("/health", tags=["meta"])
async def health(conn: asyncpg.Connection = Depends(get_conn)) -> dict:
    await conn.fetchval("select 1")
    return {"status": "ok"}
