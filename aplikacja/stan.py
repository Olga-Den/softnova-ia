"""Stan aplikacji: system dostępu w pamięci + trwały zapis w bazie, symulowany zegar, zbiór danych.

Aplikacja działa jako jedna instancja: stan roboczy jest w pamięci (SystemDostepu), a każda zmiana
jest zapisywana w bazie w jednej transakcji. Po restarcie stan wczytuje się z bazy.

Zegar jest symulowany – pozwala na pokazie przesunąć czas (wygasanie sesji, przydziałów, recertyfikacja).
"""
from __future__ import annotations

import os
import threading
from datetime import datetime, timedelta
from typing import Callable, TypeVar

from aplikacja.baza import Magazyn
from dostep.organizacja import generuj_organizacje
from dostep.przyklad import TERAZ, Przyklad
from dostep.system import SystemDostepu

T = TypeVar("T")
ZBIORY = {"przyklad": "przykładowa organizacja (kilkadziesiąt osób, scenariusze SZ)",
          "pelna": "pełna organizacja SoftNova (199 osób)"}
DOMYSLNY_URL = "sqlite:///softnova.db"


class StanAplikacji:
    def __init__(self, url: str | None = None, zbior: str | None = None) -> None:
        self.url = url or os.environ.get("DATABASE_URL", DOMYSLNY_URL)
        self.magazyn = Magazyn(self.url)
        self.blokada = threading.RLock()
        self.magazyn.utworz_schemat()
        if self.magazyn.jest_stan():
            self.system: SystemDostepu = self.magazyn.wczytaj_stan()
        else:
            self.reset(zbior or os.environ.get("ZBIOR_DANYCH", "przyklad"))

    # ------------------------------------------------------------------
    @property
    def zbior(self) -> str:
        return self.magazyn.ustawienie("zbior", "przyklad")

    @property
    def czas(self) -> datetime:
        return datetime.fromisoformat(self.magazyn.ustawienie("zegar", TERAZ.isoformat()))

    def ustaw_czas(self, czas: datetime) -> None:
        self.magazyn.ustaw("zegar", czas.isoformat())

    def przesun_czas(self, godziny: float) -> datetime:
        nowy = self.czas + timedelta(hours=godziny)
        self.ustaw_czas(nowy)
        return nowy

    # ------------------------------------------------------------------
    def reset(self, zbior: str) -> None:
        """Nowa baza z wybranym zbiorem danych – także nowy, pusty dziennik."""
        if zbior not in ZBIORY:
            raise ValueError(f"nieznany zbiór danych: {zbior}")
        with self.blokada:
            self.magazyn.usun_wszystko()
            self.magazyn.utworz_schemat()
            self.system = Przyklad().system if zbior == "przyklad" else SystemDostepu(generuj_organizacje())
            self.magazyn.zapisz_stan(self.system)
            self.magazyn.ustaw("zbior", zbior)
            self.ustaw_czas(TERAZ)

    def zmiana(self, operacja: Callable[[], T]) -> T:
        """Wykonuje operację zmieniającą stan i zapisuje wynik w bazie (w razie błędu – wczytuje stan z bazy)."""
        with self.blokada:
            try:
                wynik = operacja()
                self.magazyn.zapisz_stan(self.system)
                return wynik
            except Exception:
                self.system = self.magazyn.wczytaj_stan()
                raise

    def decyzja(self, konto: str, operacja: str, obiekt: str, **srodowisko):
        """Żądanie dostępu (PEP) – szybki zapis tylko tego, co się zmieniło."""
        with self.blokada:
            d = self.system.zadaj(konto, operacja, obiekt, self.czas, **srodowisko)
            self.magazyn.zapisz_po_decyzji(self.system, self.system.rejestr.konto(konto).uzytkownik_id, obiekt)
            return d
