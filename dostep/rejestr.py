"""Rejestr w pamięci – źródło atrybutów (PIP) i stanu (użytkownicy, konta, obiekty, sesje).

Rdzeń nie wie nic o bazie danych (WN-01). Warstwa bazy danych dostarczy własną
implementację o tym samym interfejsie.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from dostep.model import Konto, Obiekt, Sesja, Uzytkownik
from dostep.polityka.katalog import KATALOG, PozycjaKatalogu


class BrakObiektu(KeyError):
    pass


@dataclass
class Rejestr:
    uzytkownicy: dict[str, Uzytkownik] = field(default_factory=dict)
    konta: dict[str, Konto] = field(default_factory=dict)
    obiekty: dict[str, Obiekt] = field(default_factory=dict)
    sesje: dict[str, Sesja] = field(default_factory=dict)
    # Katalog uprawnień wnioskowalnych jest stanem, bo zmienia go proces SO8 (PAP).
    katalog: list[PozycjaKatalogu] = field(default_factory=lambda: list(KATALOG))

    # --- dodawanie ---
    def dodaj(self, *elementy: Uzytkownik | Konto | Obiekt | Sesja) -> None:
        for e in elementy:
            if isinstance(e, Uzytkownik):
                self.uzytkownicy[e.id] = e
            elif isinstance(e, Konto):
                self.konta[e.id] = e
            elif isinstance(e, Obiekt):
                self.obiekty[e.id] = e
            elif isinstance(e, Sesja):
                self.sesje[e.id] = e
            else:
                raise TypeError(f"Nieznany typ: {type(e).__name__}")

    # --- odczyt ---
    def uzytkownik(self, id_: str) -> Uzytkownik:
        try:
            return self.uzytkownicy[id_]
        except KeyError:
            raise BrakObiektu(f"Brak użytkownika {id_}") from None

    def konto(self, id_: str) -> Konto:
        try:
            return self.konta[id_]
        except KeyError:
            raise BrakObiektu(f"Brak konta {id_}") from None

    def obiekt(self, id_: str) -> Obiekt:
        try:
            return self.obiekty[id_]
        except KeyError:
            raise BrakObiektu(f"Brak obiektu {id_}") from None

    def sesja(self, id_: str | None) -> Sesja | None:
        return self.sesje.get(id_) if id_ else None

    def konta_uzytkownika(self, uzytkownik_id: str) -> list[Konto]:
        return [k for k in self.konta.values() if k.uzytkownik_id == uzytkownik_id]

    def wlasciciele(self, zasob: str) -> list[Uzytkownik]:
        """Właściciele zasobu (tabela 3.7) – aktywni użytkownicy z rolą właściciela."""
        return [u for u in self.uzytkownicy.values() if zasob in u.wlasciciel_zasobow and u.aktywny]

    def administratorzy(self, zasob: str) -> list[Uzytkownik]:
        """Osoby, którym przypisano rolę administratora danego systemu."""
        return [u for u in self.uzytkownicy.values()
                if f"ADM_{zasob}" in u.role_uprzywilejowane and u.aktywny]

    def po_stanowisku(self, stanowisko: str) -> Uzytkownik | None:
        return next((u for u in self.uzytkownicy.values()
                     if u.stanowisko == stanowisko and u.aktywny), None)
