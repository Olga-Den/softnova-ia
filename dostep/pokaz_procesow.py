"""Pokaz procesów zarządzania uprawnieniami (etap E3) – opowieść krok po kroku.

Uruchomienie:  python -m dostep procesy
"""
from __future__ import annotations

import sys
from datetime import timedelta

from dostep.przyklad import TERAZ, Przyklad

MIN, GODZ, DZIEN = timedelta(minutes=1), timedelta(hours=1), timedelta(days=1)
ZIELONY, CZERWONY, ZOLTY, POGRUBIONY, SZARY, KONIEC = "\033[32m", "\033[31m", "\033[33m", "\033[1m", "\033[90m", "\033[0m"


def _k(tekst: str, kolor: str) -> str:
    return f"{kolor}{tekst}{KONIEC}" if sys.stdout.isatty() else tekst


def _naglowek(nr: int, tytul: str) -> None:
    print("\n" + _k(f"━━ {nr}. {tytul} ", POGRUBIONY) + "━" * max(0, 70 - len(tytul)))


def _krok(opis: str, wynik) -> None:
    """Wypisuje krok procesu (Rezultat) albo żądanie dostępu (Decyzja)."""
    if hasattr(wynik, "zezwolono"):  # Decyzja PDP
        kolor = ZIELONY if wynik.zezwolono else CZERWONY
        ogolne = ("WT2:", "WT3:", "RC8:")
        istotne = [wynik.uzasadnienie[0]] + [x for x in wynik.uzasadnienie[1:] if not x.startswith(ogolne)][:2]
        print(f"  {opis}\n    → {_k(wynik.wynik.value.upper(), kolor)} (krok {wynik.krok}): {'; '.join(istotne)}")
        for s in wynik.sygnaly:
            print(f"    {_k('! ' + s, ZOLTY)}")
    else:                            # Rezultat procesu
        kolor = ZIELONY if wynik.ok else CZERWONY
        print(f"  {opis}\n    → {_k(str(wynik), kolor)}")


def pokaz() -> Przyklad:
    org = Przyklad()
    s = org.system
    t = TERAZ
    print(_k(f"Pokaz procesów – przykładowa organizacja SoftNova, start: {t:%Y-%m-%d %H:%M}", POGRUBIONY))

    _naglowek(1, "Wniosek o uprawnienie z katalogu (WF-15, tab. 3.9, SO6)")
    _krok("Anna (programistka) prosi o odczyt sekretów projektu w Z9 (KW4)",
          r := s.wnioski.zloz("anna", "Z9", "R", t, typ_rekordu="sekret_projektu", uzasadnienie="konfiguracja potoku",
                              okres_dni=365))
    wn = r.dane.id
    _krok("Anna próbuje sama zaakceptować swój wniosek", s.wnioski.akceptuj(wn, "anna", t + MIN))
    _krok("Piotr (przełożony) akceptuje", s.wnioski.akceptuj(wn, "piotr", t + 5 * MIN))
    _krok("Wanda (właścicielka Z9) akceptuje", s.wnioski.akceptuj(wn, "wanda", t + 10 * MIN))
    _krok("Anna odczytuje sekrety projektu", org.pdp("anna", "R", "sekret_a1", czas=t + 15 * MIN))

    _naglowek(2, "Wniosek spoza katalogu (WF-06)")
    _krok("Anna prosi o dostęp do systemu kadrowo-płacowego Z13", s.wnioski.zloz("anna", "Z13", "R", t + 20 * MIN))

    _naglowek(3, "Rola administratora w sesji (WF-13, tab. 3.11)")
    _krok("Henryk aktywuje administratora Z13 ze zwykłego konta",
          s.sesje.aktywuj("henryk", "ADM_Z13", t + 25 * MIN, numer_zgloszenia="ZGL-7"))
    _krok("Henryk aktywuje administratora Z13 z konta administracyjnego",
          r := s.sesje.aktywuj("henryk-adm", "ADM_Z13", t + 26 * MIN, numer_zgloszenia="ZGL-7"))
    _krok("Natalia (właścicielka Z13) zatwierdza aktywację", r2 := s.sesje.zatwierdz_aktywacje(r.dane, "natalia", t + 30 * MIN))
    _krok("Henryk w sesji odczytuje dane kadrowe", org.pdp("henryk-adm", "R", "kadry_anna", sesja=r2.dane, czas=t + 35 * MIN))

    _naglowek(4, "Tryb awaryjny produkcji (WF-14)")
    _krok("Emil (nie ma dyżuru) próbuje uruchomić tryb awaryjny", s.sesje.tryb_awaryjny_produkcja("emil", "INC-9", t + 40 * MIN))
    _krok("Daria (ma dyżur) uruchamia tryb awaryjny z numerem incydentu",
          r := s.sesje.tryb_awaryjny_produkcja("daria", "INC-9", t + 41 * MIN))
    _krok("Daria modyfikuje dane w produkcji w ramach incydentu",
          org.pdp("daria", "M", "prod_dane", sesja=r.dane, czas=t + 45 * MIN))

    _naglowek(5, "Wdrożenie przez konto usługowe potoku CI/CD (SO2)")
    _krok("Potok wdraża wydanie, którego nikt nie zatwierdził",
          org.pdp("cicd-potok", "W", "wydanie_a1", czas=t + 50 * MIN, interaktywne=False))
    _krok("Anna zatwierdza własne wdrożenie", org.pdp("anna", "A", "wdrozenie_a1", czas=t + 51 * MIN))
    _krok("Olek (Product Owner) zatwierdza wdrożenie", org.pdp("olek", "A", "wdrozenie_a1", czas=t + 55 * MIN))
    _krok("Potok wdraża zatwierdzone wydanie", org.pdp("cicd-potok", "W", "wydanie_a1", czas=t + 56 * MIN,
                                                     interaktywne=False))

    _naglowek(6, "Zdarzenia kadrowe (tab. 3.18)")
    _krok("Daria czyta infrastrukturę produkcji (dyżur)", org.pdp("daria", "R", "prod_infra", czas=t + 2 * GODZ))
    _krok("Daria zostaje przeniesiona z zespołu B1 do A1",
          s.kadry.przenies("daria", "A1", t + 3 * GODZ, plemie="A", jednostka="Plemię A", przelozony_id="piotr"))
    _krok("Daria po przeniesieniu czyta infrastrukturę produkcji", org.pdp("daria", "R", "prod_infra", czas=t + 4 * GODZ))
    _krok("Daria czyta zadania dawnego zespołu (RC12 – 14 dni)", org.pdp("daria", "R", "zadanie_b1", czas=t + 4 * GODZ))
    _krok("Radek (lider DevOps/SRE) odchodzi z firmy", s.kadry.odejscie("radek", t + 5 * GODZ))
    _krok("Radek próbuje się zalogować do wiki", org.pdp("radek", "R", "wiki", czas=t + 6 * GODZ))

    _naglowek(7, "Wygasanie uprawnień i zadania codzienne")
    _krok("Henryk o 19:00 używa sesji administratora Z13 otwartej o 10:30 (maks. 8 h)",
          org.pdp("henryk-adm", "R", "kadry_anna", sesja=r2.dane, czas=t + 9 * GODZ))
    print("  Zadanie codzienne (następny dzień): koniec umów, wygasłe przydziały, blokady, nieużywane uprawnienia:")
    for d in s.przetworz_terminy(t + DZIEN):
        print(f"    • {d}")

    _naglowek(8, "Recertyfikacja po 6 miesiącach (WF-17)")
    pol_roku = t + 183 * DZIEN
    pozycje = s.recertyfikacja.uruchom(pol_roku)
    for p in pozycje[:6]:
        print(f"  • {p.id}: {s.rejestr.uzytkownik(p.uzytkownik_id).imie_nazwisko} – {p.opis}; "
              f"przegląda: {s.rejestr.uzytkownik(p.recenzent_id).imie_nazwisko}")
    if len(pozycje) > 6:
        print(f"  … i {len(pozycje) - 6} kolejnych")
    anny = next((p for p in pozycje if p.uzytkownik_id == "anna"), None)
    if anny:
        _krok("Wanda potwierdza dostęp Anny do sekretów", s.recertyfikacja.rozstrzygnij(anny.id, "wanda", pol_roku, True))

    _naglowek(9, "Rozliczalność (WF-18, WN-05)")
    print(f"  • wpisów w dzienniku: {len(org.dziennik)}; łańcuch skrótów nienaruszony: {org.dziennik.weryfikuj()}")
    print(f"  • sygnałów dla zespołu bezpieczeństwa: {len(s.sygnaly)}")
    for _, tekst in s.sygnaly[:5]:
        print(f"    {_k('! ' + tekst, ZOLTY)}")
    otwarte = [z for z in s.przeglady if z.status == "otwarte"]
    print(f"  • otwarte zadania przeglądu: {len(otwarte)}")
    for z in otwarte[:5]:
        print(f"    - {z.rodzaj}: {z.opis} → {s.rejestr.uzytkownik(z.recenzent_id).imie_nazwisko}, termin {z.termin:%Y-%m-%d}")
    print(_k("\nWpisy dziennika: python -m dostep dziennik", SZARY))
    return org


def pokaz_dziennik(ostatnie: int = 40) -> None:
    """Uruchamia pokaz procesów bez wypisywania i pokazuje ostatnie wpisy dziennika."""
    import contextlib
    import io
    with contextlib.redirect_stdout(io.StringIO()):
        org = pokaz()
    print(f"Dziennik zdarzeń – ostatnie {ostatnie} z {len(org.dziennik)} wpisów "
          f"(łańcuch skrótów: {'OK' if org.dziennik.weryfikuj() else 'NARUSZONY'})\n")
    for w in org.dziennik.wpisy()[-ostatnie:]:
        dane = ", ".join(f"{k}={v}" for k, v in w.dane if v)
        print(f"{w.nr:4} {w.czas:%Y-%m-%d %H:%M} {w.zdarzenie:26} {dane[:130]}")
