"""System zarządzania dostępem – fasada łącząca PDP z procesami (rysunek 3.2, diagram Z3.1).

`SystemDostepu` pełni rolę:
  * PEP-a demonstracyjnego – `zadaj()` przekazuje żądanie do PDP, zapisuje decyzję w dzienniku,
    aktualizuje datę ostatniego użycia uprawnienia i sygnalizuje powtarzające się odmowy,
  * PAP-a – zmiany przypisań, ról i katalogu przechodzą wyłącznie przez procesy
    (wnioski, sesje, cykl życia, recertyfikacja), z których każdy zapisuje zdarzenie w dzienniku.

Wszystkie metody przyjmują czas jawnie (parametr `czas`) – dzięki temu działanie jest
deterministyczne i łatwe do pokazania (WN-02).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, time, timedelta

from dostep.dziennik import Dziennik
from dostep.model import (
    Decyzja, Operacja, Siec, Srodowisko, TypKonta, Urzadzenie, Uzytkownik, Zadanie,
)
from dostep.pdp import decyduj
from dostep.rejestr import Rejestr

PROG_ODMOW = 5                       # „powtarzające się odmowy” – ustalenie z 14.10.2026
OKNO_ODMOW = timedelta(minutes=15)


@dataclass
class Rezultat:
    """Wynik operacji procesu (wniosek, aktywacja, zdarzenie kadrowe…)."""
    ok: bool
    komunikat: str
    reguly: list[str] = field(default_factory=list)
    dane: object = None

    def __str__(self) -> str:
        znak = "OK" if self.ok else "ODMOWA"
        reg = f" [{', '.join(self.reguly)}]" if self.reguly else ""
        return f"{znak}: {self.komunikat}{reg}"


@dataclass
class ZadaniePrzegladu:
    """Zadanie dla człowieka: przegląd po trybie awaryjnym, akceptacja po fakcie, nadzór CTO…"""
    id: str
    rodzaj: str
    opis: str
    recenzent_id: str
    utworzono: datetime
    termin: datetime
    dotyczy: str = ""            # id obiektu procesu (sesji, przydziału, zmiany katalogu)
    status: str = "otwarte"      # otwarte / zamknięte
    zamknieto_o: datetime | None = None


def nastepny_dzien_roboczy(czas: datetime) -> datetime:
    """Koniec następnego dnia roboczego (pn–pt, 17:00)."""
    d = czas.date() + timedelta(days=1)
    while d.weekday() >= 5:
        d += timedelta(days=1)
    return datetime.combine(d, time(17, 0))


class SystemDostepu:
    def __init__(self, rejestr: Rejestr, dziennik: Dziennik | None = None) -> None:
        # import tutaj, żeby uniknąć importów cyklicznych (procesy korzystają z SystemDostepu)
        from dostep.cykl_zycia import CyklZycia
        from dostep.recertyfikacja import Recertyfikacja
        from dostep.sesje import SesjeUprzywilejowane
        from dostep.wnioski import ProcesWnioskow

        self.rejestr = rejestr
        self.dziennik = dziennik or Dziennik()
        self.sygnaly: list[tuple[datetime, str]] = []
        self.przeglady: list[ZadaniePrzegladu] = []
        self._odmowy: dict[str, list[datetime]] = {}
        self.liczniki: dict[str, int] = {}          # ostatnie numery identyfikatorów (WN-1, SES-3…)

        self.wnioski = ProcesWnioskow(self)
        self.sesje = SesjeUprzywilejowane(self)
        self.kadry = CyklZycia(self)
        self.recertyfikacja = Recertyfikacja(self)

    # ------------------------------------------------------------------
    # Pomocnicze
    # ------------------------------------------------------------------
    def nowe_id(self, prefiks: str) -> str:
        self.liczniki[prefiks] = self.liczniki.get(prefiks, 0) + 1
        return f"{prefiks}-{self.liczniki[prefiks]}"

    def zapisz(self, czas: datetime, zdarzenie: str, **dane: object) -> None:
        self.dziennik.dopisz(czas, zdarzenie, **dane)

    def sygnal(self, czas: datetime, tekst: str, podmiot: str = "") -> None:
        """Sygnał dla zespołu bezpieczeństwa (WF-18) – trafia też do dziennika."""
        self.sygnaly.append((czas, tekst))
        self.dziennik.dopisz(czas, "sygnal", podmiot=podmiot, opis=tekst)

    def dodaj_przeglad(self, czas: datetime, rodzaj: str, opis: str, recenzent: Uzytkownik | None,
                       termin: datetime, dotyczy: str = "") -> ZadaniePrzegladu | None:
        if recenzent is None:
            self.sygnal(czas, f"brak recenzenta dla zadania „{opis}” – wymaga ręcznego przypisania")
            return None
        z = ZadaniePrzegladu(self.nowe_id("PRZ"), rodzaj, opis, recenzent.id, czas, termin, dotyczy)
        self.przeglady.append(z)
        self.zapisz(czas, "zadanie_przegladu", id=z.id, rodzaj=rodzaj, recenzent=recenzent.id,
                    termin=termin.isoformat(), opis=opis)
        return z

    def zamknij_przeglad(self, id_: str, konto_id: str, czas: datetime, uwagi: str = "") -> Rezultat:
        z = next((p for p in self.przeglady if p.id == id_), None)
        if z is None or z.status != "otwarte":
            return Rezultat(False, f"brak otwartego zadania {id_}")
        u = self.uzytkownik_konta(konto_id)
        if u.id != z.recenzent_id:
            return Rezultat(False, "zadanie może zamknąć tylko wyznaczony recenzent")
        z.status, z.zamknieto_o = "zamknięte", czas
        self.zapisz(czas, "przeglad_zamkniety", id=z.id, recenzent=u.id, uwagi=uwagi)
        return Rezultat(True, f"zamknięto {z.id}: {z.opis}")

    def nadzor_bezpieczenstwa(self, wykonawca: Uzytkownik, opis: str, czas: datetime) -> None:
        """Działania zespołu bezpieczeństwa przegląda osoba spoza niego – CTO (3.5.4)."""
        if wykonawca.rola_funkcyjna == "T10":
            self.dodaj_przeglad(czas, "nadzór CTO", f"{wykonawca.imie_nazwisko}: {opis}",
                                self.rejestr.po_stanowisku("CTO"), czas + timedelta(days=7))

    def uzytkownik_konta(self, konto_id: str) -> Uzytkownik:
        return self.rejestr.uzytkownik(self.rejestr.konto(konto_id).uzytkownik_id)

    def przelozony(self, u: Uzytkownik) -> Uzytkownik | None:
        if not u.przelozony_id:
            return None
        return self.rejestr.uzytkownicy.get(u.przelozony_id)

    def przelozony_z_poziomu(self, u: Uzytkownik, poziomy: tuple[str, ...]) -> Uzytkownik | None:
        """Najbliższy przełożony na jednym z podanych poziomów (tabela 3.9)."""
        p = self.przelozony(u)
        while p is not None and p.poziom not in poziomy:
            p = self.przelozony(p)
        return p

    def dostepny_akceptujacy(self, osoba: Uzytkownik | None, czas: datetime) -> list[Uzytkownik]:
        """Osoba lub – gdy jest nieobecna – jej zastępca (RE3) albo przełożony (WN-07)."""
        if osoba is None:
            return []
        if osoba.aktywny and not osoba.nieobecny(czas):
            return [osoba]
        zastepcy = [z for z in self.rejestr.uzytkownicy.values() if z.aktywny and any(
            s.zastepowany_id == osoba.id and s.okres.zawiera(czas) for s in z.zastepstwa)]
        if zastepcy:
            return zastepcy
        return self.dostepny_akceptujacy(self.przelozony(osoba), czas)

    # ------------------------------------------------------------------
    # PEP – żądanie dostępu
    # ------------------------------------------------------------------
    def zadaj(self, konto_id: str, operacja: Operacja | str, obiekt_id: str, czas: datetime,
              urzadzenie: Urzadzenie = Urzadzenie.FIRMOWE, siec: Siec = Siec.BIURO,
              sesja_id: str | None = None, interaktywne: bool = True) -> Decyzja:
        zadanie = Zadanie(konto_id, Operacja(operacja), obiekt_id,
                          Srodowisko(czas, urzadzenie, siec, interaktywne), sesja_id)
        d = decyduj(zadanie, self.rejestr)
        konto = self.rejestr.konto(konto_id)
        u = self.rejestr.uzytkownik(konto.uzytkownik_id)
        self.dziennik.zapisz_decyzje(zadanie, u.id, d)
        self.sygnaly.extend((czas, s) for s in d.sygnaly)

        if konto.typ is not TypKonta.USLUGOWE:
            u.ostatnia_aktywnosc = czas
        obiekt = self.rejestr.obiekt(obiekt_id)
        if d.zezwolono:
            u.ostatnie_uzycie[f"{obiekt.zasob}:{zadanie.operacja.value}"] = czas
            if zadanie.operacja is Operacja.A and u.id not in obiekt.zatwierdzone_przez:
                obiekt.zatwierdzone_przez.append(u.id)   # historia obiektu dla SoD (SO)
        else:
            self._licz_odmowe(u, czas)
        return d

    def _licz_odmowe(self, u: Uzytkownik, czas: datetime) -> None:
        lista = [t for t in self._odmowy.get(u.id, []) if czas - t <= OKNO_ODMOW] + [czas]
        if len(lista) >= PROG_ODMOW:
            self.sygnal(czas, f"powtarzające się odmowy: {u.imie_nazwisko} – {len(lista)} odmów "
                              f"w ciągu {int(OKNO_ODMOW.total_seconds() // 60)} min", u.id)
            lista = []
        self._odmowy[u.id] = lista

    # ------------------------------------------------------------------
    # Zadania okresowe
    # ------------------------------------------------------------------
    def przetworz_terminy(self, czas: datetime) -> list[str]:
        """Zadanie uruchamiane codziennie: wygasanie, blokady, eskalacje (tab. 3.18, 3.5.7)."""
        dzialania = self.kadry.przetworz(czas) + self.recertyfikacja.przetworz(czas)
        for z in self.przeglady:
            if z.status == "otwarte" and czas > z.termin and not z.rodzaj.endswith("(po terminie)"):
                z.rodzaj += " (po terminie)"
                self.sygnal(czas, f"przekroczony termin zadania {z.id}: {z.opis}", z.recenzent_id)
                dzialania.append(f"przekroczony termin {z.id}")
        return dzialania
