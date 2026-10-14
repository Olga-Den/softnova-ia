"""Proces nadania uprawnienia na wniosek (WF-06, WF-15, tab. 3.9, SO6, rys. 3.4)
oraz zmiana katalogu uprawnień wnioskowalnych (SO8).

Przebieg wniosku:
  1. złożenie (zapis W w Z17 – sprawdzany przez PDP),
  2. automatyczne sprawdzenie: katalog (WF-06), warunki twarde (WT3, WT7), duplikat,
  3. wyznaczenie akceptujących wg tabeli 3.9 (KW2–KW3: właściciel; KW4: przełożony i właściciel),
  4. akceptacje – każda przez inną osobę, różną od wnioskującego i beneficjenta (SO6),
  5. automatyczna realizacja (Przydzial na czas określony) i wpis do dziennika – bez udziału administratora.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import TYPE_CHECKING

from dostep.model import Klasa, Obiekt, Okres, Operacja, Przydzial, Uzytkownik, operacje
from dostep.polityka.katalog import PozycjaKatalogu
from dostep.polityka.zakres import w_katalogu
from dostep.polityka.zasoby import ZASOBY

if TYPE_CHECKING:
    from dostep.system import Rezultat, SystemDostepu

DOMYSLNY_OKRES_DNI = 90   # założenie: wnioskowane uprawnienie domyślnie na 90 dni (WF-12)


class StatusWniosku(str, Enum):
    ODRZUCONY_AUTOMATYCZNIE = "odrzucony automatycznie"
    OCZEKUJE = "oczekuje na akceptację"
    ODRZUCONY = "odrzucony"
    ZREALIZOWANY = "zrealizowany"


@dataclass
class Wymaganie:
    """Jedna wymagana akceptacja – kto może jej udzielić."""
    rola: str                       # „właściciel zasobu” / „przełożony”
    kandydaci: list[str]
    udzielona_przez: str | None = None
    czas: datetime | None = None


@dataclass
class Wniosek:
    id: str
    wnioskujacy_id: str
    beneficjent_id: str
    zasob: str
    operacje: frozenset[Operacja]
    typ_rekordu: str | None
    uzasadnienie: str
    okres_dni: int
    zlozony_o: datetime
    status: StatusWniosku = StatusWniosku.OCZEKUJE
    wymagania: list[Wymaganie] = field(default_factory=list)
    powod: str = ""
    reguly: list[str] = field(default_factory=list)

    def opis(self) -> str:
        ops = "".join(o.value for o in Operacja if o in self.operacje)
        typ = f" ({self.typ_rekordu})" if self.typ_rekordu else ""
        return f"{ops} w {self.zasob} {ZASOBY[self.zasob].nazwa}{typ}"


class ProcesWnioskow:
    def __init__(self, system: "SystemDostepu") -> None:
        self.s = system
        self.wnioski: dict[str, Wniosek] = {}
        self.zmiany_katalogu: dict[str, dict] = {}

    # ------------------------------------------------------------------
    def zloz(self, konto_id: str, zasob: str, ops: str, czas: datetime, typ_rekordu: str | None = None,
             uzasadnienie: str = "", okres_dni: int = DOMYSLNY_OKRES_DNI,
             beneficjent_id: str | None = None) -> "Rezultat":
        from dostep.system import Rezultat
        r = self.s.rejestr
        wnioskujacy = self.s.uzytkownik_konta(konto_id)
        beneficjent = r.uzytkownik(beneficjent_id) if beneficjent_id else wnioskujacy
        w = Wniosek(self.s.nowe_id("WN"), wnioskujacy.id, beneficjent.id, zasob, operacje(ops),
                    typ_rekordu, uzasadnienie, okres_dni, czas)
        self.wnioski[w.id] = w

        # 1. Złożenie = zapis wniosku w Z17 – PDP sprawdza uprawnienie roli bazowej.
        r.dodaj(Obiekt(w.id, "Z17", f"wniosek {w.id}", typ_rekordu="wniosek", autor_id=wnioskujacy.id,
                       dotyczy_osoby_id=beneficjent.id))
        d = self.s.zadaj(konto_id, "W", w.id, czas)
        if not d.zezwolono:
            return self._odrzuc_auto(w, czas, "nie można złożyć wniosku: " + "; ".join(d.uzasadnienie), d.reguly)
        if beneficjent.id != wnioskujacy.id and beneficjent.przelozony_id != wnioskujacy.id:
            return self._odrzuc_auto(w, czas, "wniosek za inną osobę może złożyć tylko jej przełożony", ["SO6"])

        # 2. Automatyczne sprawdzenia
        pozycja = w_katalogu(beneficjent, r.katalog, zasob, w.operacje, typ_rekordu)
        if pozycja is None:
            return self._odrzuc_auto(w, czas, f"uprawnienie {w.opis()} nie należy do katalogu roli "
                                              f"{beneficjent.rola_funkcyjna}", ["WF-06"])
        if pozycja.sposob != "wniosek":
            return self._odrzuc_auto(w, czas, f"to uprawnienie nie jest nadawane na wniosek, lecz "
                                              f"automatycznie ({pozycja.sposob})", ["WF-06", pozycja.sposob])
        bledy = self._warunki_twarde(beneficjent, zasob, czas)
        if bledy:
            return self._odrzuc_auto(w, czas, "; ".join(t for _, t in bledy), [g for g, _ in bledy])
        if any(p.zasob == zasob and w.operacje <= p.operacje and p.typ_rekordu == typ_rekordu
               and p.aktywny(czas) for p in beneficjent.przydzialy):
            return self._odrzuc_auto(w, czas, "użytkownik ma już to uprawnienie", [])

        # 3. Akceptujący wg tabeli 3.9
        w.wymagania = self._wymagania(w, wnioskujacy, beneficjent, czas)
        if any(not x.kandydaci for x in w.wymagania):
            return self._odrzuc_auto(w, czas, "nie udało się wyznaczyć akceptującego – zgłoś do zespołu "
                                              "bezpieczeństwa", ["WF-15"])
        self.s.zapisz(czas, "wniosek_zlozony", id=w.id, wnioskujacy=wnioskujacy.id, beneficjent=beneficjent.id,
                      uprawnienie=w.opis(), akceptujacy=" + ".join(
                          f"{x.rola}: {'/'.join(x.kandydaci)}" for x in w.wymagania))
        kto = "; ".join(f"{x.rola} ({', '.join(r.uzytkownik(k).imie_nazwisko for k in x.kandydaci)})"
                        for x in w.wymagania)
        return Rezultat(True, f"wniosek {w.id} złożony – czeka na akceptację: {kto}", ["WF-15"], w)

    def _warunki_twarde(self, u: Uzytkownik, zasob: str, czas: datetime) -> list[tuple[str, str]]:
        bledy = []
        if not u.aktywny or (u.data_konca_umowy and czas.date() > u.data_konca_umowy):
            bledy.append(("WT3", "beneficjent nie ma aktywnej umowy"))
        if ZASOBY[zasob].dane_osobowe:
            up = u.upowaznienie
            if not up or not up.wazne(czas) or zasob not in up.zakres:
                bledy.append(("WT7", f"brak ważnego upoważnienia do przetwarzania danych osobowych w {zasob}"))
        return bledy

    def _wymagania(self, w: Wniosek, wnioskujacy: Uzytkownik, benef: Uzytkownik,
                   czas: datetime) -> list[Wymaganie]:
        r = self.s.rejestr
        wykluczeni = {wnioskujacy.id, benef.id}   # SO6
        wym: list[Wymaganie] = []

        # przełożony – tylko KW4; wniosek osoby z P3 → przełożony z P2, osoby z P2 → członek zarządu
        if ZASOBY[w.zasob].klasa is Klasa.KW4:
            if benef.poziom == "P3":
                przel = self.s.przelozony_z_poziomu(benef, ("P2", "P1"))
            elif benef.poziom in ("P2", "P1"):
                przel = next((x for x in r.uzytkownicy.values() if x.rola_funkcyjna == "B1"
                              and x.aktywny and x.id not in wykluczeni), None)
            else:
                przel = self.s.przelozony(benef)
            while przel is not None and przel.id in wykluczeni:     # brak zatwierdzającego → wyższy poziom
                przel = self.s.przelozony(przel)
            kand = [x.id for x in self.s.dostepny_akceptujacy(przel, czas) if x.id not in wykluczeni]
            wym.append(Wymaganie("przełożony", kand))

        # właściciel zasobu (zawsze); gdy jest wykluczony lub nieobecny → wyższy poziom
        kand: list[str] = []
        for wl in r.wlasciciele(w.zasob):
            osoba = wl if wl.id not in wykluczeni else self.s.przelozony(wl)
            kand += [x.id for x in self.s.dostepny_akceptujacy(osoba, czas) if x.id not in wykluczeni]
        wym.append(Wymaganie("właściciel zasobu", list(dict.fromkeys(kand))))
        return wym

    def _odrzuc_auto(self, w: Wniosek, czas: datetime, powod: str, reguly: list[str]) -> "Rezultat":
        from dostep.system import Rezultat
        w.status, w.powod, w.reguly = StatusWniosku.ODRZUCONY_AUTOMATYCZNIE, powod, reguly
        self.s.zapisz(czas, "wniosek_odrzucony", id=w.id, beneficjent=w.beneficjent_id,
                      uprawnienie=w.opis(), powod=powod, reguly=",".join(reguly))
        return Rezultat(False, f"wniosek {w.id} odrzucony automatycznie: {powod}", reguly, w)

    # ------------------------------------------------------------------
    def akceptuj(self, wniosek_id: str, konto_id: str, czas: datetime, zgoda: bool = True,
                 komentarz: str = "") -> "Rezultat":
        from dostep.system import Rezultat
        w = self.wnioski.get(wniosek_id)
        if w is None or w.status is not StatusWniosku.OCZEKUJE:
            return Rezultat(False, f"wniosek {wniosek_id} nie oczekuje na akceptację")
        u = self.s.uzytkownik_konta(konto_id)
        if not u.aktywny or not self.s.rejestr.konto(konto_id).aktywne:
            return Rezultat(False, "konto akceptującego jest nieaktywne", ["WT3"])

        # SO6: nikt nie akceptuje własnego wniosku ani wniosku, który go dotyczy; dwie różne osoby
        if u.id in (w.wnioskujacy_id, w.beneficjent_id) or any(x.udzielona_przez == u.id for x in w.wymagania):
            powod = ("nikt nie akceptuje własnego wniosku ani wniosku, który go dotyczy"
                     if u.id in (w.wnioskujacy_id, w.beneficjent_id)
                     else "wniosek o zasób KW4 wymaga akceptacji dwóch różnych osób")
            self.s.zapisz(czas, "naruszenie_SoD", regula="SO6", podmiot=u.id, wniosek=w.id, opis=powod)
            self.s.sygnal(czas, f"próba naruszenia rozdziału obowiązków SO6: {u.imie_nazwisko}, {w.id}", u.id)
            return Rezultat(False, powod, ["SO6"])

        wym = next((x for x in w.wymagania if x.udzielona_przez is None and u.id in x.kandydaci), None)
        if wym is None:
            return Rezultat(False, f"{u.imie_nazwisko} nie jest akceptującym tego wniosku (tabela 3.9)", ["WF-15"])

        if not zgoda:
            w.status, w.powod = StatusWniosku.ODRZUCONY, komentarz or "odrzucony przez akceptującego"
            self.s.zapisz(czas, "wniosek_odrzucony", id=w.id, przez=u.id, powod=w.powod)
            return Rezultat(True, f"wniosek {w.id} odrzucony przez {u.imie_nazwisko}", [], w)

        wym.udzielona_przez, wym.czas = u.id, czas
        self.s.rejestr.obiekt(w.id).zatwierdzone_przez.append(u.id)
        self.s.zapisz(czas, "akceptacja", wniosek=w.id, przez=u.id, jako=wym.rola, komentarz=komentarz)
        self.s.nadzor_bezpieczenstwa(u, f"akceptacja wniosku {w.id} ({w.opis()})", czas)
        if any(x.udzielona_przez is None for x in w.wymagania):
            brak = [x.rola for x in w.wymagania if x.udzielona_przez is None]
            return Rezultat(True, f"akceptacja przyjęta – brakuje jeszcze: {', '.join(brak)}", ["SO6"], w)
        return self._realizuj(w, czas)

    def _realizuj(self, w: Wniosek, czas: datetime) -> "Rezultat":
        """Automatyczna realizacja – warunki twarde sprawdzane ponownie, niezależnie od akceptacji (WF-07)."""
        from dostep.system import Rezultat
        benef = self.s.rejestr.uzytkownik(w.beneficjent_id)
        bledy = self._warunki_twarde(benef, w.zasob, czas)
        if bledy:
            w.status, w.powod = StatusWniosku.ODRZUCONY, "; ".join(t for _, t in bledy)
            self.s.zapisz(czas, "wniosek_odrzucony", id=w.id, powod=w.powod)
            return Rezultat(False, f"wniosek {w.id} nie może zostać zrealizowany: {w.powod}",
                            [g for g, _ in bledy], w)
        koniec = czas + timedelta(days=w.okres_dni)
        if benef.data_konca_umowy:   # nie dłużej niż umowa (B2B, staż)
            koniec = min(koniec, datetime.combine(benef.data_konca_umowy, datetime.max.time()))
        p = Przydzial(w.zasob, w.operacje, w.typ_rekordu, Okres(czas, koniec), w.id,
                      ostatnia_recertyfikacja=czas)
        benef.przydzialy.append(p)
        w.status = StatusWniosku.ZREALIZOWANY
        self.s.zapisz(czas, "zmiana_przypisania", rodzaj="nadanie", uzytkownik=benef.id,
                      uprawnienie=w.opis(), do=koniec.isoformat(), wniosek=w.id, wykonal="IAM (automatycznie)")
        return Rezultat(True, f"wniosek {w.id} zrealizowany automatycznie – {benef.imie_nazwisko} ma "
                              f"{w.opis()} do {koniec:%Y-%m-%d}", ["WF-15"], p)

    def oczekujace_dla(self, uzytkownik_id: str) -> list[Wniosek]:
        return [w for w in self.wnioski.values() if w.status is StatusWniosku.OCZEKUJE and any(
            x.udzielona_przez is None and uzytkownik_id in x.kandydaci for x in w.wymagania)]

    # ------------------------------------------------------------------
    # SO8 – zmiana katalogu uprawnień wnioskowalnych
    # ------------------------------------------------------------------
    def zaproponuj_zmiane_katalogu(self, konto_id: str, pozycja: PozycjaKatalogu, dzialanie: str,
                                   czas: datetime) -> "Rezultat":
        """Inicjuje specjalista bezpieczeństwa; zatwierdza administrator danego systemu (SO8)."""
        from dostep.system import Rezultat
        u = self.s.uzytkownik_konta(konto_id)
        if u.rola_funkcyjna != "T10":
            return Rezultat(False, "zmianę katalogu inicjuje specjalista bezpieczeństwa", ["SO8"])
        if dzialanie not in ("dodaj", "usun"):
            return Rezultat(False, "działanie: dodaj albo usun")
        if dzialanie == "usun" and pozycja not in self.s.rejestr.katalog:
            return Rezultat(False, "takiej pozycji nie ma w katalogu")
        kandydaci = [a.id for a in self.s.rejestr.administratorzy(pozycja.zasob) if a.id != u.id]
        if not kandydaci:
            return Rezultat(False, f"brak administratora systemu {pozycja.zasob}, który mógłby zatwierdzić zmianę",
                            ["SO8"])
        id_ = self.s.nowe_id("KAT")
        self.zmiany_katalogu[id_] = dict(pozycja=pozycja, dzialanie=dzialanie, autor=u.id,
                                         kandydaci=kandydaci, status="oczekuje")
        self.s.zapisz(czas, "zmiana_katalogu_zaproponowana", id=id_, autor=u.id, dzialanie=dzialanie,
                      pozycja=f"{pozycja.rola} {pozycja.zasob} {''.join(o.value for o in pozycja.operacje)}")
        return Rezultat(True, f"zmiana katalogu {id_} czeka na zatwierdzenie administratora "
                              f"{pozycja.zasob}: {', '.join(kandydaci)}", ["SO8"], id_)

    def zatwierdz_zmiane_katalogu(self, id_: str, konto_id: str, czas: datetime) -> "Rezultat":
        from dostep.system import Rezultat
        z = self.zmiany_katalogu.get(id_)
        if not z or z["status"] != "oczekuje":
            return Rezultat(False, f"zmiana {id_} nie oczekuje na zatwierdzenie")
        u = self.s.uzytkownik_konta(konto_id)
        if u.id == z["autor"] or u.id not in z["kandydaci"]:
            self.s.zapisz(czas, "naruszenie_SoD", regula="SO8", podmiot=u.id, zmiana=id_)
            return Rezultat(False, "zmianę katalogu zatwierdza administrator danego systemu, "
                                   "inny niż autor zmiany", ["SO8"])
        p: PozycjaKatalogu = z["pozycja"]
        if z["dzialanie"] == "dodaj":
            self.s.rejestr.katalog.append(p)
        else:
            self.s.rejestr.katalog.remove(p)
        z["status"] = "wprowadzona"
        self.s.zapisz(czas, "zmiana_katalogu", id=id_, zatwierdzil=u.id, dzialanie=z["dzialanie"],
                      pozycja=f"{p.rola} {p.zasob} {''.join(o.value for o in p.operacje)}")
        autor = self.s.rejestr.uzytkownik(z["autor"])
        self.s.nadzor_bezpieczenstwa(autor, f"zmiana katalogu {id_} ({z['dzialanie']} {p.rola} {p.zasob})", czas)
        return Rezultat(True, f"zmiana katalogu {id_} wprowadzona", ["SO8"])
