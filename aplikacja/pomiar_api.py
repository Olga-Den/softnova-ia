"""Pomiar czasu pełnego żądania przez API (metryka M7) – warstwa FastAPI + PDP + zapis w bazie.

Domyślnie mierzy na tymczasowej bazie SQLite. Aby zmierzyć na PostgreSQL, podaj adres OSOBNEJ, pustej bazy
(parametr --baza-api) – pomiar ładuje do niej pełną organizację, więc nie wskazuj bazy z danymi pokazu.
"""
from __future__ import annotations

import random
import statistics
import tempfile
import time
from pathlib import Path

from fastapi.testclient import TestClient

from aplikacja.main import utworz_aplikacje


def zmierz_api(proby: int = 500, url: str | None = None) -> dict:
    tymczasowy = None
    if not url:
        tymczasowy = Path(tempfile.mkdtemp()) / "pomiar.db"
        url = f"sqlite:///{tymczasowy}"
    with TestClient(utworz_aplikacje(url)) as c:
        c.post("/api/demo/reset/pelna")
        konta = [k["konto"] for k in c.get("/api/konta").json() if k["typ"] == "zwykłe"]
        obiekty = [o["id"] for o in c.get("/api/obiekty").json()]
        los = random.Random(7)
        for _ in range(20):    # rozgrzewka
            c.post("/api/decyzja", json=dict(operacja="R", obiekt=los.choice(obiekty)), headers={"X-Konto": los.choice(konta)})
        czasy = []
        for _ in range(proby):
            dane = dict(operacja=los.choice("RWMDA"), obiekt=los.choice(obiekty))
            naglowki = {"X-Konto": los.choice(konta)}
            t0 = time.perf_counter_ns()
            odp = c.post("/api/decyzja", json=dane, headers=naglowki)
            czasy.append((time.perf_counter_ns() - t0) / 1e6)
            odp.raise_for_status()
    c_ = sorted(czasy)
    if tymczasowy:
        tymczasowy.unlink(missing_ok=True)
    return dict(baza="PostgreSQL" if url.startswith("postgresql") else "SQLite", proby=proby,
                srednia=statistics.mean(c_), mediana=statistics.median(c_), p95=c_[int(0.95 * len(c_))],
                p99=c_[int(0.99 * len(c_))], maks=c_[-1])
