"""Role uprzywilejowane w sesji (WF-13, tab. 3.11) i tryb awaryjny (WF-14, podrozdział 3.5.4).

  * przypisanie roli uprzywilejowanej – z kontrolą SS (tab. 3.12) i SO6, tylko do konta administracyjnego,
  * aktywacja w sesji – maks. czas, numer zgłoszenia, dla Z13 i Z17 akceptacja właściciela,
  * tryb awaryjny produkcji – 4 h, numer incydentu, alarm, przegląd w ciągu dnia roboczego,
  * nagłe zastępstwo – przełożony P2 nadaje na 72 h uprawnienie z katalogu; bez akceptacji
    właściciela po fakcie uprawnienie wygasa; nie dotyczy Z13 i Z17,
  * wyznaczenie zastępcy z uprawnieniami zatwierdzającymi (RE3, maks. 30 dni).
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from dostep.model import Konto, Okres, Przydzial, Sesja, TypKonta, Zastepstwo, operacje
from dostep.polityka.role import ROLE
from dostep.polityka.zakres import w_katalogu
from dostep.sod_statyczne import sprawdz_przypisanie_roli

if TYPE_CHECKING:
    from dostep.system import Rezultat, SystemDostepu

ZASTEPSTWO_AWARYJNE = timedelta(hours=72)
MAKS_ZASTEPSTWO_RE3 = timedelta(days=30)


class SesjeUprzywilejowane:
    def __init__(self, system: "SystemDostepu") -> None:
        self.s = system
        self.prosby: dict[str, dict] = {}   # aktywacje czekające na akceptację właściciela

    # ------------------------------------------------------------------
    def przypisz_role(self, uzytkownik_id: str, rola: str, zatwierdzajacy_konto: str,
                      czas: datetime) -> "Rezultat":
        """Stałe przypisanie roli uprzywilejowanej (uprawnienie do jej aktywacji)."""
        from dostep.system import Rezultat
        r = self.s.rejestr
        u = r.uzytkownik(uzytkownik_id)
        zatw = self.s.uzytkownik_konta(zatwierdzajacy_konto)
        if zatw.id == u.id:
            return Rezultat(False, "nikt nie nadaje roli uprzywilejowanej samemu sobie", ["SO6"])
        naruszenia = sprawdz_przypisanie_roli(u, rola)
        if naruszenia:
            for n in naruszenia:
                if n.regula.startswith("SS"):
                    self.s.zapisz(czas, "naruszenie_SoD", regula=n.regula, podmiot=u.id, rola=rola, opis=n.komentarz)
            self.s.sygnal(czas, f"zablokowane przypisanie roli {rola} dla {u.imie_nazwisko}: "
                                f"{', '.join(n.regula for n in naruszenia)}", u.id)
            return Rezultat(False, "; ".join(n.komentarz for n in naruszenia), [n.regula for n in naruszenia])
        u.role_uprzywilejowane.add(rola)
        if not any(k.typ is TypKonta.ADMINISTRACYJNE for k in r.konta_uzytkownika(u.id)):
            r.dodaj(Konto(f"{u.id}-adm", u.id, TypKonta.ADMINISTRACYJNE))
        self.s.zapisz(czas, "zmiana_przypisania", rodzaj="rola uprzywilejowana", uzytkownik=u.id, rola=rola,
                      zatwierdzil=zatw.id)
        return Rezultat(True, f"{u.imie_nazwisko} może aktywować rolę {ROLE[rola].nazwa} "
                              f"z konta {u.id}-adm", ["WF-13"])

    # ------------------------------------------------------------------
    def aktywuj(self, konto_id: str, rola: str, czas: datetime, godziny: int | None = None,
                numer_zgloszenia: str | None = None) -> "Rezultat":
        from dostep.system import Rezultat
        r = self.s.rejestr
        konto = r.konto(konto_id)
        u = r.uzytkownik(konto.uzytkownik_id)
        definicja = ROLE.get(rola)
        if definicja is None or not rola.startswith("ADM_"):
            return Rezultat(False, f"{rola} nie jest rolą administratora (tryb awaryjny: tryb_awaryjny_produkcja)")
        bledy = []
        if konto.typ is not TypKonta.ADMINISTRACYJNE:
            bledy.append(("WT4", "rolę uprzywilejowaną aktywuje się tylko z konta administracyjnego"))
        if not konto.aktywne or not u.aktywny:
            bledy.append(("WT3", "konto lub użytkownik nieaktywny"))
        if rola not in u.role_uprzywilejowane:
            bledy.append(("WF-13", f"użytkownikowi nie przypisano roli {definicja.nazwa}"))
        bledy += [(n.regula, n.komentarz) for n in sprawdz_przypisanie_roli(u, rola) if n.regula.startswith("SS")]
        godziny = godziny or definicja.maks_godzin
        if godziny > definicja.maks_godzin:
            bledy.append(("WF-13", f"maksymalny czas aktywacji to {definicja.maks_godzin} h"))
        if definicja.wymaga_zgloszenia and not numer_zgloszenia:
            bledy.append(("WF-13", "aktywacja wymaga numeru zgłoszenia"))
        if bledy:
            self.s.zapisz(czas, "aktywacja_odrzucona", konto=konto_id, rola=rola,
                          powod="; ".join(t for _, t in bledy))
            return Rezultat(False, "; ".join(t for _, t in bledy), [g for g, _ in bledy])

        if definicja.wymaga_akceptacji_wlasciciela:
            kandydaci = [w.id for w in r.wlasciciele(definicja.zasob) if w.id != u.id]
            id_ = self.s.nowe_id("AKT")
            self.prosby[id_] = dict(konto=konto_id, rola=rola, godziny=godziny, numer=numer_zgloszenia,
                                    kandydaci=kandydaci, status="oczekuje")
            self.s.zapisz(czas, "aktywacja_prosba", id=id_, konto=konto_id, rola=rola,
                          akceptujacy="/".join(kandydaci), zgloszenie=numer_zgloszenia)
            return Rezultat(True, f"prośba {id_} o aktywację {definicja.nazwa} czeka na akceptację właściciela "
                                  f"({', '.join(r.uzytkownik(k).imie_nazwisko for k in kandydaci)})",
                            ["WF-13"], id_)
        return self._otworz_sesje(konto_id, rola, godziny, numer_zgloszenia, czas)

    def zatwierdz_aktywacje(self, prosba_id: str, konto_id: str, czas: datetime) -> "Rezultat":
        from dostep.system import Rezultat
        p = self.prosby.get(prosba_id)
        if not p or p["status"] != "oczekuje":
            return Rezultat(False, f"prośba {prosba_id} nie oczekuje")
        u = self.s.uzytkownik_konta(konto_id)
        if u.id not in p["kandydaci"]:
            return Rezultat(False, "aktywację zatwierdza właściciel zasobu, inny niż wnioskujący", ["SO6"])
        p["status"] = "zatwierdzona"
        self.s.zapisz(czas, "aktywacja_zatwierdzona", id=prosba_id, przez=u.id)
        return self._otworz_sesje(p["konto"], p["rola"], p["godziny"], p["numer"], czas)

    def _otworz_sesje(self, konto_id: str, rola: str, godziny: int, numer: str | None,
                      czas: datetime) -> "Rezultat":
        from dostep.system import Rezultat
        sesja = Sesja(self.s.nowe_id("SES"), konto_id, {rola: Okres(czas, czas + timedelta(hours=godziny))}, numer)
        self.s.rejestr.dodaj(sesja)
        self.s.zapisz(czas, "aktywacja_roli", sesja=sesja.id, konto=konto_id, rola=rola,
                      do=(czas + timedelta(hours=godziny)).isoformat(), zgloszenie=numer or "")
        return Rezultat(True, f"sesja {sesja.id}: rola {ROLE[rola].nazwa} aktywna do "
                              f"{czas + timedelta(hours=godziny):%H:%M}", ["WF-13"], sesja.id)

    def zakoncz(self, sesja_id: str, czas: datetime) -> "Rezultat":
        from dostep.system import Rezultat
        sesja = self.s.rejestr.sesja(sesja_id)
        if not sesja:
            return Rezultat(False, f"brak sesji {sesja_id}")
        for rola, okres in list(sesja.aktywne_role.items()):
            if okres.do > czas:
                sesja.aktywne_role[rola] = Okres(okres.od, czas)
        self.s.zapisz(czas, "koniec_sesji", sesja=sesja_id)
        return Rezultat(True, f"sesja {sesja_id} zakończona")

    # ------------------------------------------------------------------
    # Tryb awaryjny
    # ------------------------------------------------------------------
    def tryb_awaryjny_produkcja(self, konto_id: str, numer_incydentu: str | None,
                                czas: datetime) -> "Rezultat":
        """Rola awaryjna Z8 na 4 h: lider DevOps/SRE lub osoba z dyżuru, z numerem incydentu."""
        from dostep.system import Rezultat, nastepny_dzien_roboczy
        r = self.s.rejestr
        konto = r.konto(konto_id)
        u = r.uzytkownik(konto.uzytkownik_id)
        lider = u.rola_funkcyjna == "T9" and u.stanowisko == "lider DevOps/SRE"
        dyzur = any(d.zawiera(czas) for d in u.dyzury)
        if not numer_incydentu:
            return Rezultat(False, "tryb awaryjny wymaga numeru incydentu", ["WF-14"])
        if not (lider or dyzur):
            self.s.sygnal(czas, f"odrzucona próba trybu awaryjnego: {u.imie_nazwisko} (nie lider DevOps/SRE "
                                f"i nie pełni dyżuru)", u.id)
            return Rezultat(False, "tryb awaryjny może uruchomić lider DevOps/SRE lub osoba pełniąca dyżur", ["WF-14"])
        if not konto.aktywne or not u.aktywny:
            return Rezultat(False, "konto nieaktywne", ["WT3"])

        maks = ROLE["AWARYJNA_Z8"].maks_godzin
        sesja = Sesja(self.s.nowe_id("SES"), konto_id, {"AWARYJNA_Z8": Okres(czas, czas + timedelta(hours=maks))},
                      numer_incydentu)
        r.dodaj(sesja)
        self.s.zapisz(czas, "tryb_awaryjny", sesja=sesja.id, konto=konto_id, incydent=numer_incydentu,
                      do=(czas + timedelta(hours=maks)).isoformat())
        self.s.sygnal(czas, f"ALARM: {u.imie_nazwisko} uruchomił(a) tryb awaryjny produkcji (incydent "
                            f"{numer_incydentu}) – powiadomienie zespołu bezpieczeństwa i właściciela Z8", u.id)
        # Przegląd w ciągu dnia roboczego; gdy aktywuje właściciel Z8 – przegląda lider bezpieczeństwa.
        wlasciciel = next(iter(r.wlasciciele("Z8")), None)
        recenzent = r.po_stanowisku("lider bezpieczeństwa") if (wlasciciel is None or wlasciciel.id == u.id) \
            else wlasciciel
        self.s.dodaj_przeglad(czas, "przegląd trybu awaryjnego",
                              f"użycie roli awaryjnej Z8 przez {u.imie_nazwisko}, incydent {numer_incydentu}",
                              recenzent, nastepny_dzien_roboczy(czas), sesja.id)
        return Rezultat(True, f"tryb awaryjny: sesja {sesja.id}, rola awaryjna Z8 aktywna do "
                              f"{czas + timedelta(hours=maks):%H:%M}; przegląd: "
                              f"{recenzent.imie_nazwisko if recenzent else 'brak'}", ["WF-14"], sesja.id)

    def zastepstwo_awaryjne(self, konto_przelozonego: str, beneficjent_id: str, zasob: str, ops: str,
                            czas: datetime, typ_rekordu: str | None = None) -> "Rezultat":
        """Nagłe zastępstwo: przełożony z poziomu P2 nadaje na 72 h uprawnienie z katalogu osoby."""
        from dostep.system import Rezultat
        r = self.s.rejestr
        przel = self.s.uzytkownik_konta(konto_przelozonego)
        benef = r.uzytkownik(beneficjent_id)
        if przel.poziom != "P2":
            return Rezultat(False, "zastępstwo awaryjne nadaje przełożony z poziomu P2", ["WF-14"])
        if self.s.przelozony_z_poziomu(benef, ("P2",)) is not przel:
            return Rezultat(False, f"{przel.imie_nazwisko} nie jest przełożonym P2 osoby {benef.imie_nazwisko}",
                            ["WF-14"])
        if zasob in ("Z13", "Z17"):
            return Rezultat(False, "tryb awaryjny nie dotyczy Z13 i Z17", ["WF-14"])
        if w_katalogu(benef, r.katalog, zasob, operacje(ops), typ_rekordu) is None:
            return Rezultat(False, f"uprawnienie nie należy do katalogu roli {benef.rola_funkcyjna}", ["WF-06"])
        p = Przydzial(zasob, operacje(ops), typ_rekordu, Okres(czas, czas + ZASTEPSTWO_AWARYJNE),
                      self.s.nowe_id("AWR"), awaryjny=True)
        benef.przydzialy.append(p)
        self.s.zapisz(czas, "tryb_awaryjny", rodzaj="zastępstwo 72 h", uzytkownik=benef.id, nadal=przel.id,
                      uprawnienie=p.klucz(), do=p.okres.do.isoformat())
        self.s.sygnal(czas, f"tryb awaryjny – zastępstwo: {benef.imie_nazwisko} otrzymał(a) {p.klucz()} na 72 h",
                      benef.id)
        wl = next(iter(r.wlasciciele(zasob)), None)
        self.s.dodaj_przeglad(czas, "akceptacja po fakcie",
                              f"zastępstwo awaryjne {p.wniosek_id}: {benef.imie_nazwisko} – {p.klucz()}",
                              wl, p.okres.do, p.wniosek_id)
        return Rezultat(True, f"nadano {p.klucz()} do {p.okres.do:%Y-%m-%d %H:%M}; bez akceptacji właściciela "
                              f"uprawnienie wygaśnie", ["WF-14"], p)

    def akceptuj_po_fakcie(self, przydzial_id: str, konto_wlasciciela: str, czas: datetime,
                           okres_dni: int = 30) -> "Rezultat":
        from dostep.system import Rezultat
        wl = self.s.uzytkownik_konta(konto_wlasciciela)
        for u in self.s.rejestr.uzytkownicy.values():
            for p in u.przydzialy:
                if p.wniosek_id == przydzial_id and p.awaryjny:
                    if p.zasob not in wl.wlasciciel_zasobow or wl.id == u.id:
                        return Rezultat(False, "akceptuje właściciel zasobu, inny niż beneficjent", ["SO6"])
                    if not p.aktywny(czas):
                        return Rezultat(False, "uprawnienie już wygasło – potrzebny zwykły wniosek")
                    p.awaryjny = False
                    p.okres = Okres(p.okres.od, czas + timedelta(days=okres_dni))
                    p.ostatnia_recertyfikacja = czas
                    self.s.zapisz(czas, "zmiana_przypisania", rodzaj="akceptacja po fakcie", uzytkownik=u.id,
                                  uprawnienie=p.klucz(), do=p.okres.do.isoformat(), zatwierdzil=wl.id)
                    for z in self.s.przeglady:
                        if z.dotyczy == przydzial_id and z.status == "otwarte":
                            z.status, z.zamknieto_o = "zamknięte", czas
                    return Rezultat(True, f"zastępstwo {przydzial_id} zaakceptowane do {p.okres.do:%Y-%m-%d}")
        return Rezultat(False, f"brak zastępstwa awaryjnego {przydzial_id}")

    def wyznacz_zastepce(self, konto_przelozonego: str, zastepowany_id: str, zastepca_id: str,
                         od: datetime, do: datetime, czas: datetime) -> "Rezultat":
        """RE3 – zastępca uzyskuje uprawnienia zatwierdzające osoby zastępowanej (maks. 30 dni)."""
        from dostep.system import Rezultat
        r = self.s.rejestr
        przel = self.s.uzytkownik_konta(konto_przelozonego)
        zastepowany, zastepca = r.uzytkownik(zastepowany_id), r.uzytkownik(zastepca_id)
        if zastepowany.przelozony_id != przel.id:
            return Rezultat(False, "zastępcę wyznacza przełożony osoby zastępowanej", ["RE3"])
        if zastepca.id == zastepowany.id or do - od > MAKS_ZASTEPSTWO_RE3:
            return Rezultat(False, "zastępstwo: inna osoba, maks. 30 dni", ["RE3"])
        zastepca.zastepstwa.append(Zastepstwo(zastepowany.id, Okres(od, do)))
        self.s.zapisz(czas, "zmiana_przypisania", rodzaj="zastępstwo (RE3)", zastepca=zastepca.id,
                      zastepowany=zastepowany.id, od=od.isoformat(), do=do.isoformat(), wyznaczyl=przel.id)
        return Rezultat(True, f"{zastepca.imie_nazwisko} zastępuje {zastepowany.imie_nazwisko} "
                              f"od {od:%Y-%m-%d} do {do:%Y-%m-%d}", ["RE3"])
