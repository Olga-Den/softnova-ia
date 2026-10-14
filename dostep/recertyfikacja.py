"""Okresowa recertyfikacja przypisań i wykazy uprawnień (WF-17, podrozdział 3.5.7, rys. 3.6).

  * KW3 (i niżej) – co 12 miesięcy, KW4 i role uprzywilejowane – co 6 miesięcy,
  * dostęp kontraktorów B2B – co 3 miesiące, potwierdza kierownik, który zawarł umowę,
  * przegląd wykonuje właściciel zasobu (gdy jest też administratorem systemu – przełożony użytkownika),
    na podstawie wykazu z datą ostatniego użycia,
  * niepotwierdzone przypisanie: po 14 dniach eskalacja, po 30 dniach odebranie.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from dostep.model import Klasa, Operacja, Siec, TypKonta, Urzadzenie, Uzytkownik
from dostep.polityka.macierz import MACIERZ
from dostep.polityka.role import ROLE
from dostep.polityka.zakres import role_przypisane
from dostep.polityka.zasoby import ZASOBY

if TYPE_CHECKING:
    from dostep.system import Rezultat, SystemDostepu

OKRES_KW3 = timedelta(days=365)
OKRES_KW4 = timedelta(days=182)
OKRES_B2B = timedelta(days=91)
ESKALACJA = timedelta(days=14)
ODEBRANIE = timedelta(days=30)


@dataclass
class PozycjaPrzegladu:
    id: str
    uzytkownik_id: str
    rodzaj: str                # „przydział”, „rola uprzywilejowana”, „dostęp B2B”
    klucz: str                 # klucz przydziału / id roli / „B2B”
    opis: str
    recenzent_id: str
    utworzono: datetime
    ostatnie_uzycie: datetime | None
    status: str = "oczekuje"   # oczekuje / eskalowana / potwierdzona / odebrana
    rozstrzygnieto_o: datetime | None = None


class Recertyfikacja:
    def __init__(self, system: "SystemDostepu") -> None:
        self.s = system
        self.pozycje: dict[str, PozycjaPrzegladu] = {}
        self.ostatnia: dict[tuple[str, str], datetime] = {}   # (użytkownik, klucz) → data recertyfikacji

    # ------------------------------------------------------------------
    def _aktywny(self, osoba: Uzytkownik | None, czas: datetime, wykluczony: str) -> Uzytkownik | None:
        """Aktywna osoba (lub jej zastępca/przełożony), różna od przeglądanej."""
        while osoba is not None:
            kand = [x for x in self.s.dostepny_akceptujacy(osoba, czas) if x.id != wykluczony]
            if kand:
                return kand[0]
            osoba = self.s.przelozony(osoba)
        return None

    def _recenzent_zasobu(self, u: Uzytkownik, zasob: str, czas: datetime) -> Uzytkownik | None:
        for wl in self.s.rejestr.wlasciciele(zasob):
            if wl.id != u.id and f"ADM_{zasob}" not in wl.role_uprzywilejowane:
                return self._aktywny(wl, czas, u.id)
        return self._aktywny(self.s.przelozony(u), czas, u.id)

    def _ostatnie_uzycie(self, u: Uzytkownik, zasob: str, ops=None) -> datetime | None:
        pasujace = [t for k, t in u.ostatnie_uzycie.items()
                    if k.split(":")[0] == zasob and (ops is None or k.split(":")[1] in {o.value for o in ops})]
        return max(pasujace, default=None)

    def _oczekuje(self, u_id: str, klucz: str) -> bool:
        return any(p.uzytkownik_id == u_id and p.klucz == klucz and p.status in ("oczekuje", "eskalowana")
                   for p in self.pozycje.values())

    def _dodaj(self, czas, u, rodzaj, klucz, opis, recenzent, uzycie) -> PozycjaPrzegladu | None:
        if recenzent is None or self._oczekuje(u.id, klucz):
            return None
        p = PozycjaPrzegladu(self.s.nowe_id("REC"), u.id, rodzaj, klucz, opis, recenzent.id, czas, uzycie)
        self.pozycje[p.id] = p
        self.s.zapisz(czas, "recertyfikacja_pozycja", id=p.id, uzytkownik=u.id, klucz=klucz, recenzent=recenzent.id)
        return p

    def uruchom(self, czas: datetime) -> list[PozycjaPrzegladu]:
        """Tworzy pozycje do przeglądu dla przypisań, którym minął okres recertyfikacji."""
        nowe: list[PozycjaPrzegladu] = []
        for u in self.s.rejestr.uzytkownicy.values():
            if not u.aktywny:
                continue
            for pr in u.przydzialy:
                if pr.awaryjny:
                    continue
                okres = OKRES_KW4 if ZASOBY[pr.zasob].klasa is Klasa.KW4 else OKRES_KW3
                ostatnia = pr.ostatnia_recertyfikacja or (pr.okres.od if pr.okres else datetime.min)
                if czas - ostatnia >= okres:
                    p = self._dodaj(czas, u, "przydział", pr.klucz(), f"{pr.klucz()} (wniosek {pr.wniosek_id})",
                                    self._recenzent_zasobu(u, pr.zasob, czas), self._ostatnie_uzycie(u, pr.zasob, pr.operacje))
                    nowe += [p] if p else []
            for rola in sorted(u.role_uprzywilejowane):
                ostatnia = self.ostatnia.get((u.id, rola), u.data_zatrudnienia or datetime.min)
                if czas - ostatnia >= OKRES_KW4:
                    zasob = ROLE[rola].zasob
                    p = self._dodaj(czas, u, "rola uprzywilejowana", rola, ROLE[rola].nazwa,
                                    self._recenzent_zasobu(u, zasob, czas), self._ostatnie_uzycie(u, zasob))
                    nowe += [p] if p else []
            if u.forma.value == "B2B":
                ostatnia = self.ostatnia.get((u.id, "B2B"), u.data_zatrudnienia or datetime.min)
                if czas - ostatnia >= OKRES_B2B:
                    kier = self._aktywny(self.s.rejestr.uzytkownicy.get(u.kierownik_umowy_id or "")
                                         or self.s.przelozony(u), czas, u.id)
                    p = self._dodaj(czas, u, "dostęp B2B", "B2B", "cały dostęp kontraktora B2B", kier,
                                    max(u.ostatnie_uzycie.values(), default=None))
                    nowe += [p] if p else []
        return nowe

    # ------------------------------------------------------------------
    def rozstrzygnij(self, pozycja_id: str, konto_id: str, czas: datetime, zachowaj: bool,
                     komentarz: str = "") -> "Rezultat":
        from dostep.system import Rezultat
        p = self.pozycje.get(pozycja_id)
        if not p or p.status not in ("oczekuje", "eskalowana"):
            return Rezultat(False, f"pozycja {pozycja_id} nie oczekuje na przegląd")
        rec = self.s.uzytkownik_konta(konto_id)
        if rec.id != p.recenzent_id or rec.id == p.uzytkownik_id:
            return Rezultat(False, "przegląd wykonuje wyznaczony recenzent, inny niż osoba przeglądana", ["WF-17"])
        p.rozstrzygnieto_o = czas
        if zachowaj:
            p.status = "potwierdzona"
            self._oznacz(p, czas)
            self.s.zapisz(czas, "recertyfikacja", id=p.id, uzytkownik=p.uzytkownik_id, klucz=p.klucz,
                          decyzja="potwierdzone", recenzent=rec.id, komentarz=komentarz)
        else:
            self._odbierz(p, czas, f"nie potwierdzono przez {rec.imie_nazwisko}")
        self.s.nadzor_bezpieczenstwa(rec, f"recertyfikacja {p.id} ({p.opis}): "
                                          f"{'potwierdzone' if zachowaj else 'odebrane'}", czas)
        return Rezultat(True, f"{p.id}: {'potwierdzono' if zachowaj else 'odebrano'} {p.opis}", ["WF-17"])

    def _oznacz(self, p: PozycjaPrzegladu, czas: datetime) -> None:
        u = self.s.rejestr.uzytkownik(p.uzytkownik_id)
        self.ostatnia[(u.id, p.klucz)] = czas
        for pr in u.przydzialy:
            if pr.klucz() == p.klucz:
                pr.ostatnia_recertyfikacja = czas

    def _odbierz(self, p: PozycjaPrzegladu, czas: datetime, powod: str) -> None:
        u = self.s.rejestr.uzytkownik(p.uzytkownik_id)
        p.status = "odebrana"
        if p.rodzaj == "przydział":
            u.przydzialy = [x for x in u.przydzialy if x.klucz() != p.klucz]
        elif p.rodzaj == "rola uprzywilejowana":
            u.role_uprzywilejowane.discard(p.klucz)
        elif p.rodzaj == "dostęp B2B":
            self.s.kadry.odejscie(u.id, czas, przyczyna="brak potwierdzenia dostępu B2B")
        self.s.zapisz(czas, "recertyfikacja", id=p.id, uzytkownik=u.id, klucz=p.klucz, decyzja="odebrane",
                      powod=powod)
        self.s.zapisz(czas, "zmiana_przypisania", rodzaj="odebranie (recertyfikacja)", uzytkownik=u.id,
                      uprawnienie=p.klucz, powod=powod, wykonal="IAM (automatycznie)")

    def przetworz(self, czas: datetime) -> list[str]:
        """Po 14 dniach eskalacja do przełożonego recenzenta, po 30 dniach odebranie."""
        dzialania = []
        for p in self.pozycje.values():
            if p.status not in ("oczekuje", "eskalowana"):
                continue
            if czas - p.utworzono >= ODEBRANIE:
                self._odbierz(p, czas, "brak potwierdzenia w ciągu 30 dni")
                dzialania.append(f"odebrano {p.opis} – brak recertyfikacji")
            elif czas - p.utworzono >= ESKALACJA and p.status == "oczekuje":
                rec = self.s.rejestr.uzytkownik(p.recenzent_id)
                wyzej = self._aktywny(self.s.przelozony(rec), czas, p.uzytkownik_id)
                if wyzej:
                    p.recenzent_id, p.status = wyzej.id, "eskalowana"
                    self.s.zapisz(czas, "recertyfikacja_eskalacja", id=p.id, do=wyzej.id)
                    self.s.sygnal(czas, f"eskalacja recertyfikacji {p.id} do {wyzej.imie_nazwisko}", rec.id)
                    dzialania.append(f"eskalacja {p.id} do {wyzej.imie_nazwisko}")
        return dzialania

    # ------------------------------------------------------------------
    # Wykazy (WF-17)
    # ------------------------------------------------------------------
    def wykaz_uzytkownika(self, uzytkownik_id: str, czas: datetime) -> list[dict]:
        """Co ma użytkownik: maksimum z ról (z regułami), przydziały, role uprzywilejowane, ostatnie użycie."""
        u = self.s.rejestr.uzytkownik(uzytkownik_id)
        wiersze = []
        role = role_przypisane(u)
        for w in MACIERZ:
            if w.rola in role and (not w.tylko_plemie or w.tylko_plemie == u.plemie):
                ops = "".join(o.value for o in Operacja if o in w.operacje)
                wiersze.append(dict(zrodlo=f"rola {w.rola}", zasob=w.zasob, operacje=ops,
                                    warunki=" ".join(w.reguly + w.so) or "–",
                                    wazne_do="zgodnie z funkcją",
                                    ostatnie_uzycie=self._ostatnie_uzycie(u, w.zasob, w.operacje)))
        for p in u.przydzialy:
            wiersze.append(dict(zrodlo=f"wniosek {p.wniosek_id}" + (" (awaryjny)" if p.awaryjny else ""),
                                zasob=p.zasob, operacje="".join(o.value for o in Operacja if o in p.operacje),
                                warunki=p.typ_rekordu or "–",
                                wazne_do=f"{p.okres.do:%Y-%m-%d %H:%M}" if p.okres else "bez terminu",
                                ostatnie_uzycie=self._ostatnie_uzycie(u, p.zasob, p.operacje)))
        for r in sorted(u.role_uprzywilejowane):
            wiersze.append(dict(zrodlo="rola uprzywilejowana (aktywacja w sesji)", zasob=ROLE[r].zasob,
                                operacje="RWMD", warunki="konto administracyjne, WT4",
                                wazne_do=f"maks. {ROLE[r].maks_godzin} h na sesję",
                                ostatnie_uzycie=self._ostatnie_uzycie(u, ROLE[r].zasob)))
        return wiersze

    def kto_ma_dostep(self, obiekt_id: str, czas: datetime) -> list[dict]:
        """Kto ma dostęp do obiektu – efektywnie, z regułami ABAC, w podanej chwili (urządzenie firmowe, biuro)."""
        from dostep.model import Srodowisko, Zadanie
        from dostep.pdp import decyduj
        wynik = []
        for u in self.s.rejestr.uzytkownicy.values():
            for k in self.s.rejestr.konta_uzytkownika(u.id):
                if k.typ is not TypKonta.ZWYKLE:
                    continue
                ops = [op.value for op in Operacja if decyduj(
                    Zadanie(k.id, op, obiekt_id, Srodowisko(czas, Urzadzenie.FIRMOWE, Siec.BIURO)),
                    self.s.rejestr).zezwolono]
                if ops:
                    wynik.append(dict(uzytkownik=u.id, imie_nazwisko=u.imie_nazwisko,
                                      rola=ROLE[u.rola_funkcyjna].nazwa, operacje="".join(ops)))
        return wynik
