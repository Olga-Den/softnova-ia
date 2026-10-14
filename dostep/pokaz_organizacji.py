"""Pełna organizacja (199 osób): zestawienie, metryki M4 i M5, eksport do CSV.

Uruchomienie:
    python -m dostep organizacja                 zestawienie i porównanie ze stanem „przed”
    python -m dostep organizacja --csv wyniki    to samo + pliki CSV w folderze „wyniki”
Pliki CSV mają średnik jako separator i kodowanie UTF-8 z BOM – otwierają się poprawnie w Excelu.
"""
from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path

from dostep.model import Operacja
from dostep.organizacja import DATA_GENERACJI, generuj_organizacje
from dostep.polityka.macierz import MACIERZ
from dostep.polityka.role import ROLE
from dostep.rejestr import Rejestr
from dostep.stan_przed import statystyki, uprawnienia_przed

# Oczekiwane liczebności ról – tabela 3.8
TABELA_3_8 = {"T1": 60, "T2": 8, "T3": 24, "T4": 12, "T5": 12, "T6": 3, "T7": 1, "T8": 2, "T9": 10, "T10": 5,
              "T11": 7, "T12": 5, "B1": 3, "B2": 1, "B3": 1, "B4": 7, "B5": 3, "B6": 12, "B7": 5, "B8": 2,
              "B9": 3, "B10": 4, "B11": 2, "B12": 4, "B13": 3}


def _liczba(x: float, miejsca: int = 2) -> str:
    return f"{x:.{miejsca}f}".replace(".", ",")


def pokaz(folder_csv: str | None = None) -> Rejestr:
    r = generuj_organizacje()
    U = list(r.uzytkownicy.values())
    print(f"Organizacja SoftNova – stan na {DATA_GENERACJI:%Y-%m-%d}: {len(U)} osób, {len(r.konta)} kont, "
          f"{len(r.obiekty)} obiektów w zasobach Z1–Z17\n")

    print("Jednostki (tab. Z1.1):")
    for j, n in sorted(Counter(u.jednostka for u in U).items(), key=lambda x: -x[1]):
        print(f"  {j:22} {n:4}")
    formy = Counter(u.forma.value for u in U)
    print("\nFormy współpracy: " + ", ".join(f"{k} {v}" for k, v in formy.items()))
    print("Poziomy (tab. Z1.3): " + ", ".join(f"{k} {v}" for k, v in sorted(Counter(u.poziom for u in U).items())))
    kont_adm = sum(1 for k in r.konta.values() if k.typ.value == "administracyjne")
    print(f"Konta administracyjne: {kont_adm}; przypisań ról uprzywilejowanych: "
          f"{sum(len(u.role_uprzywilejowane) for u in U)}; konta usługowe: "
          f"{sum(1 for k in r.konta.values() if k.typ.value == 'usługowe')}")

    s = statystyki(r)
    print("\nRole (tab. 3.8) – liczba osób, uprawnienia roli w modelu, średnio uprawnień stałych „przed”:")
    print(f"  {'rola':5} {'nazwa':28} {'osób':>5} {'tab. 3.8':>8} {'PA po':>6} {'przed/os.':>10} {'stałe, nie z roli/os.':>22}")
    for w in s["na_role"]:
        zgodne = "✔" if TABELA_3_8[w["rola"]] == w["uzytkownicy"] else "✘"
        print(f"  {w['rola']:5} {w['nazwa']:28} {w['uzytkownicy']:5} {TABELA_3_8[w['rola']]:6} {zgodne} "
              f"{w['pa_po']:6} {_liczba(w['przed_srednio'], 1):>10} {_liczba(w['nie_z_roli_srednio'], 1):>22}")

    print("\nMetryki administrowalności (WN-03):")
    print(f"  M4  stosunek ról do użytkowników: {s['role']} ról / {s['uzytkownicy']} osób = 1 : {_liczba(s['m4'])}"
          f"   (oczekiwane ok. 1 : 7,7)")
    print(f"  M5  przypisania w modelu / bezpośrednie przypisania przed = ({s['ua']} UA + {s['pa']} PA) / {s['przed']}"
          f" = {_liczba(s['m5'], 3)}   (oczekiwane < 1)")
    print(f"      możliwych par (użytkownik, uprawnienie): {s['mozliwe_pary']}; "
          f"faktycznych „przed”: {s['przed']} w {s['grupy_przed']} grupach o identycznych uprawnieniach")
    print("      pochodzenie uprawnień „przed”: " +
          ", ".join(f"{k}: {v}" for k, v in sorted(s["przyczyny_przed"].items())))
    print(f"  Uprawnienia stałe „przed”, które w modelu nie wynikają z roli (są tylko czasowe albo wcale): "
          f"{s['stale_nie_z_roli']}")
    print(f"  w tym ponad maksimum modelu (rola + katalog + role uprzywilejowane): {s['ponad_maksimum']}")

    if folder_csv:
        zapisz_csv(r, Path(folder_csv))
    return r


def zapisz_csv(r: Rejestr, folder: Path) -> None:
    folder.mkdir(parents=True, exist_ok=True)

    def plik(nazwa, naglowek, wiersze):
        with open(folder / nazwa, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f, delimiter=";")
            w.writerow(naglowek)
            w.writerows(wiersze)

    U = sorted(r.uzytkownicy.values(), key=lambda u: (u.jednostka, u.zespol or "", u.poziom, u.id))
    plik("uzytkownicy.csv",
         ["id", "imię i nazwisko", "rola", "nazwa roli", "poziom", "jednostka", "zespół", "chapter", "stanowisko",
          "forma współpracy", "koniec umowy", "przełożony", "role uprzywilejowane", "właściciel zasobów",
          "upoważnienie RODO"],
         [[u.id, u.imie_nazwisko, u.rola_funkcyjna, ROLE[u.rola_funkcyjna].nazwa, u.poziom, u.jednostka,
           u.zespol or "", u.chapter or "", u.stanowisko, u.forma.value, u.data_konca_umowy or "",
           u.przelozony_id or "", " ".join(sorted(u.role_uprzywilejowane)), " ".join(sorted(u.wlasciciel_zasobow)),
           " ".join(sorted(u.upowaznienie.zakres, key=lambda z: int(z[1:]))) if u.upowaznienie else ""]
          for u in U])
    plik("uprawnienia_rol.csv", ["rola", "nazwa roli", "zasób", "operacje", "reguły", "SoD", "zakres"],
         [[w.rola, ROLE[w.rola].nazwa if w.rola in ROLE else "poziom P2/P3", w.zasob,
           "".join(o.value for o in Operacja if o in w.operacje), " ".join(w.reguly), " ".join(w.so),
           " ".join(sorted(w.typy_rekordu)) if w.typy_rekordu else ""] for w in MACIERZ])
    plik("stan_przed.csv", ["użytkownik", "rola", "zasób", "operacja", "przyczyna"],
         [[u.id, u.rola_funkcyjna, z, op, przyczyna]
          for u in U for (z, op), przyczyna in sorted(uprawnienia_przed(u).items(), key=lambda x: (int(x[0][0][1:]), x[0][1]))])
    plik("obiekty.csv", ["id", "zasób", "nazwa", "zespół", "jednostka", "klient", "typ rekordu", "proces"],
         [[o.id, o.zasob, o.nazwa, o.zespol or "", o.jednostka or "", o.klient or "", o.typ_rekordu or "",
           o.proces or ""] for o in r.obiekty.values()])
    print(f"\nZapisano pliki CSV w folderze {folder.resolve()}: uzytkownicy.csv, uprawnienia_rol.csv, "
          f"stan_przed.csv, obiekty.csv")
