"""Zakres uprawnień wynikający z funkcji – maksimum wyznaczone przez rolę i katalog (podrozdział 3.5.1).

Służy do:
  * wyznaczenia zakresu upoważnienia do przetwarzania danych osobowych (WT7),
  * wykazu „do czego użytkownik może w ogóle uzyskać dostęp” (WF-17),
  * odebrania przydziałów niezgodnych z nową funkcją przy zmianie stanowiska (tab. 3.18).
"""
from __future__ import annotations

from dostep.model import Uzytkownik
from dostep.polityka.katalog import PozycjaKatalogu
from dostep.polityka.macierz import MACIERZ, POZIOM_P2_P3
from dostep.polityka.role import ROLE, role_efektywne
from dostep.polityka.zasoby import ZASOBY


def role_przypisane(u: Uzytkownik) -> list[str]:
    """Role z macierzy obowiązujące użytkownika na koncie zwykłym (z dziedziczeniem i P2/P3)."""
    role = role_efektywne(u.rola_funkcyjna)
    if u.poziom in ("P2", "P3"):
        role.append(POZIOM_P2_P3)
    return role


def zasoby_z_roli(u: Uzytkownik, bez_wlasnych_danych: bool = False) -> set[str]:
    """Zasoby z macierzy ról użytkownika. `bez_wlasnych_danych` pomija wpisy dotyczące
    wyłącznie własnych danych (składanie własnych wniosków w Z17) – nie wymagają upoważnienia."""
    role = role_przypisane(u)
    return {w.zasob for w in MACIERZ if w.rola in role
            and (not w.tylko_plemie or w.tylko_plemie == u.plemie)
            and not (bez_wlasnych_danych and w.typy_rekordu == frozenset({"wniosek"}))}


def zasoby_z_katalogu(u: Uzytkownik, katalog: list[PozycjaKatalogu]) -> set[str]:
    role = role_efektywne(u.rola_funkcyjna)
    return {p.zasob for p in katalog if p.rola in role}


def zasoby_uprzywilejowane(u: Uzytkownik) -> set[str]:
    """Zasoby ról uprzywilejowanych przypisanych użytkownikowi oraz roli awaryjnej,
    którą jego funkcja może uruchomić (lider DevOps/SRE, osoba z dyżuru)."""
    przypisane = {ROLE[r].zasob for r in u.role_uprzywilejowane if ROLE[r].zasob}
    awaryjne = {ROLE["AWARYJNA_Z8"].zasob} if u.rola_funkcyjna in ROLE["AWARYJNA_Z8"].kto_moze else set()
    return przypisane | awaryjne


def zakres_upowaznienia(u: Uzytkownik, katalog: list[PozycjaKatalogu]) -> frozenset[str]:
    """Zasoby ze znacznikiem DO, do których funkcja użytkownika może dać dostęp."""
    wszystkie = zasoby_z_roli(u, bez_wlasnych_danych=True) | zasoby_z_katalogu(u, katalog) | zasoby_uprzywilejowane(u)
    return frozenset(z for z in wszystkie if ZASOBY[z].dane_osobowe)


def w_katalogu(u: Uzytkownik, katalog: list[PozycjaKatalogu], zasob: str, operacje, typ_rekordu) -> \
        PozycjaKatalogu | None:
    """Pozycja katalogu roli użytkownika obejmująca żądane uprawnienie (WF-06)."""
    role = role_efektywne(u.rola_funkcyjna)
    for p in katalog:
        if (p.rola in role and p.zasob == zasob and set(operacje) <= p.operacje
                and (p.typ_rekordu is None or p.typ_rekordu == typ_rekordu)):
            return p
    return None
