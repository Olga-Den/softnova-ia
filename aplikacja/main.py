"""Aplikacja FastAPI – powłoka demonstracyjna modelu zarządzania dostępem.

Uruchomienie bez Dockera (baza SQLite w pliku softnova.db):
    uvicorn aplikacja.main:app --reload
Uruchomienie z Dockerem (PostgreSQL):
    docker compose up --build
Strona: http://localhost:8000   Dokumentacja API: http://localhost:8000/docs
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from aplikacja.api import api
from aplikacja.stan import StanAplikacji
from aplikacja.strony import strony


def utworz_aplikacje(url: str | None = None, zbior: str | None = None) -> FastAPI:
    @asynccontextmanager
    async def cykl(app: FastAPI):
        app.state.stan = StanAplikacji(url, zbior)
        yield

    app = FastAPI(title="SoftNova IAM – model zarządzania dostępem",
                  description="Hybrydowy model RBAC + ABAC z rozdziałem obowiązków (praca inżynierska, PWr). "
                              "Tożsamość wybiera się nagłówkiem X-Konto (logowanie symulowane).",
                  version="1.0", lifespan=cykl)
    app.mount("/statyczne", StaticFiles(directory=str(Path(__file__).parent / "statyczne")), name="statyczne")
    app.include_router(api)
    app.include_router(strony)
    return app


app = utworz_aplikacje()
