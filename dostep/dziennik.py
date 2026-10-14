"""Dziennik zdarzeń – tylko dopisywanie (WF-18, WN-05).

Wpisy są niezmienne (frozen) i powiązane łańcuchem skrótów SHA-256:
każdy wpis zawiera skrót poprzedniego, więc zmiana lub usunięcie
dowolnego wpisu jest wykrywana przez `weryfikuj()`.
W bazie danych dodatkowo blokuje to wyzwalacz (UPDATE/DELETE zabronione).
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime

from dostep.model import Decyzja, Zadanie

SKROT_POCZATKOWY = "0" * 64


@dataclass(frozen=True)
class WpisDziennika:
    nr: int
    czas: datetime
    zdarzenie: str          # np. "decyzja", "zmiana_przypisania", "naruszenie_SoD", "tryb_awaryjny"
    dane: tuple[tuple[str, str], ...]
    skrot_poprzedni: str
    skrot: str

    def slownik(self) -> dict[str, str]:
        return dict(self.dane)


def _policz_skrot(nr: int, czas: datetime, zdarzenie: str, dane, poprzedni: str) -> str:
    tresc = json.dumps([nr, czas.isoformat(), zdarzenie, list(dane), poprzedni],
                       ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(tresc.encode("utf-8")).hexdigest()


class Dziennik:
    def __init__(self) -> None:
        self._wpisy: list[WpisDziennika] = []

    def dopisz(self, czas: datetime, zdarzenie: str, **dane: object) -> WpisDziennika:
        nr = len(self._wpisy) + 1
        poprzedni = self._wpisy[-1].skrot if self._wpisy else SKROT_POCZATKOWY
        para = tuple(sorted((k, str(v)) for k, v in dane.items()))
        wpis = WpisDziennika(nr, czas, zdarzenie, para, poprzedni,
                             _policz_skrot(nr, czas, zdarzenie, para, poprzedni))
        self._wpisy.append(wpis)
        return wpis

    def zapisz_decyzje(self, zadanie: Zadanie, uzytkownik_id: str, decyzja: Decyzja) -> WpisDziennika:
        """Zapis decyzji: podmiot, obiekt, operacja, czas, decyzja, reguła rozstrzygająca (3.5.7)."""
        wpis = self.dopisz(
            zadanie.srodowisko.czas, "decyzja",
            podmiot=uzytkownik_id, konto=zadanie.konto_id, obiekt=zadanie.obiekt_id,
            operacja=zadanie.operacja.value, wynik=decyzja.wynik.value, krok=decyzja.krok,
            reguly=",".join(decyzja.reguly), uzasadnienie=" | ".join(decyzja.uzasadnienie),
        )
        for sygnal in decyzja.sygnaly:
            self.dopisz(zadanie.srodowisko.czas, "sygnal", podmiot=uzytkownik_id, opis=sygnal)
        return wpis

    def wpisy(self) -> tuple[WpisDziennika, ...]:
        """Kopia tylko do odczytu – nie da się przez nią zmienić dziennika."""
        return tuple(self._wpisy)

    def __len__(self) -> int:
        return len(self._wpisy)

    def weryfikuj(self) -> bool:
        """Sprawdza ciągłość łańcucha skrótów."""
        poprzedni = SKROT_POCZATKOWY
        for i, w in enumerate(self._wpisy, start=1):
            if w.nr != i or w.skrot_poprzedni != poprzedni:
                return False
            if w.skrot != _policz_skrot(w.nr, w.czas, w.zdarzenie, w.dane, w.skrot_poprzedni):
                return False
            poprzedni = w.skrot
        return True
