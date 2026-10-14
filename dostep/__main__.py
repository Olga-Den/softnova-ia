"""Pokaz działania rdzenia z wiersza poleceń – bez bazy danych, bez dodatkowych bibliotek.

Użycie:
    python -m dostep                      wszystkie scenariusze (SZ1–SZ10 i zwykła praca)
    python -m dostep SZ1                  jeden scenariusz ze szczegółami
    python -m dostep anna R repo_y        własne żądanie: konto, operacja (R/W/M/D/A), obiekt
    python -m dostep --lista              lista kont i obiektów przykładowej organizacji
    python -m dostep procesy              pokaz procesów: wnioski, sesje, tryb awaryjny, kadry, recertyfikacja
    python -m dostep dziennik             ostatnie wpisy dziennika po pokazie procesów
    python -m dostep organizacja          pełna organizacja (199 osób), metryki M4 i M5
    python -m dostep organizacja --csv wyniki   to samo + eksport do CSV
    python -m dostep metryki              metryki M1–M10 – raport do rozdziału 5 (folder „wyniki”)
"""
from __future__ import annotations

import os
import sys

from dostep.model import Operacja
from dostep.polityka.role import ROLE
from dostep.polityka.zasoby import ZASOBY
from dostep.przyklad import Przyklad
from dostep.scenariusze import WSZYSTKIE, Przypadek

ZIELONY, CZERWONY, SZARY, KONIEC = "\033[32m", "\033[31m", "\033[90m", "\033[0m"


def _kolor(tekst: str, kolor: str) -> str:
    return f"{kolor}{tekst}{KONIEC}" if sys.stdout.isatty() else tekst


def _wypisz_decyzje(d, szczegoly: bool = True) -> None:
    kolor = ZIELONY if d.zezwolono else CZERWONY
    print(f"  Decyzja: {_kolor(d.wynik.value.upper(), kolor)}  (krok {d.krok} algorytmu PDP)")
    if szczegoly:
        for linia in d.uzasadnienie:
            print(f"    • {linia}")
        for s in d.sygnaly:
            print(f"    ! {s}")


def _uruchom(p: Przypadek, szczegoly: bool) -> bool:
    org = Przyklad()
    if p.przygotuj:
        p.przygotuj(org)
    d = org.pdp(p.konto, p.operacja, p.obiekt, **p.srodowisko)
    zgodna = d.wynik.value == p.oczekiwany
    znak = _kolor("✔", ZIELONY) if zgodna else _kolor("✘", CZERWONY)
    print(f"{znak} {p.id:5} {p.opis}")
    print(_kolor(f"  {p.konto} → {p.operacja} na {p.obiekt}; oczekiwano: {p.oczekiwany}", SZARY))
    _wypisz_decyzje(d, szczegoly)
    print()
    return zgodna


def pokaz_wszystkie() -> None:
    zgodne = sum(_uruchom(p, szczegoly=False) for p in WSZYSTKIE)
    print(f"Decyzje zgodne z oczekiwanymi: {zgodne}/{len(WSZYSTKIE)}")
    print("Szczegóły jednego scenariusza: python -m dostep SZ1")


def pokaz_liste() -> None:
    org = Przyklad()
    print("KONTA (konto → osoba, rola, zespół):")
    for k in org.rejestr.konta.values():
        u = org.rejestr.uzytkownik(k.uzytkownik_id)
        print(f"  {k.id:12} {u.imie_nazwisko:22} {ROLE[u.rola_funkcyjna].nazwa:28} "
              f"{u.zespol or u.jednostka:10} konto {k.typ.value}")
    print("\nOBIEKTY (obiekt → zasób, opis):")
    for o in org.rejestr.obiekty.values():
        print(f"  {o.id:18} {o.zasob:4} {ZASOBY[o.zasob].nazwa:34} {o.nazwa}")


def main(argv: list[str]) -> int:
    if not argv:
        pokaz_wszystkie()
    elif argv[0] in ("--lista", "-l"):
        pokaz_liste()
    elif argv[0] == "procesy":
        from dostep.pokaz_procesow import pokaz
        pokaz()
    elif argv[0] == "organizacja":
        from dostep.pokaz_organizacji import pokaz as pokaz_org
        folder = argv[2] if len(argv) >= 3 and argv[1] == "--csv" else None
        pokaz_org(folder)
    elif argv[0] == "metryki":
        from dostep.raport_metryk import main as metryki
        return metryki(argv[1:])
    elif argv[0] == "dziennik":
        from dostep.pokaz_procesow import pokaz_dziennik
        pokaz_dziennik()
    elif len(argv) == 1:
        p = next((x for x in WSZYSTKIE if x.id.upper() == argv[0].upper()), None)
        if not p:
            print(f"Nie ma scenariusza {argv[0]}. Dostępne: {', '.join(x.id for x in WSZYSTKIE)}")
            return 1
        _uruchom(p, szczegoly=True)
    elif len(argv) == 3:
        konto, op, obiekt = argv
        if op.upper() not in Operacja.__members__:
            print(f"Nieznana operacja {op} – dozwolone: R, W, M, D, A")
            return 1
        org = Przyklad()
        try:
            d = org.pdp(konto, op.upper(), obiekt)
        except KeyError as e:
            print(f"Błąd: {e.args[0]}. Sprawdź nazwy poleceniem: python -m dostep --lista")
            return 1
        print(f"{konto} → {op.upper()} na {obiekt}")
        _wypisz_decyzje(d)
    else:
        print(__doc__)
        return 1
    return 0


if __name__ == "__main__":
    if sys.platform == "win32":
        os.system("")  # włącza kolory w konsoli Windows
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # polskie znaki w każdej konsoli
    except AttributeError:
        pass
    sys.exit(main(sys.argv[1:]))
