"""Cykl życia uprawnień przy zdarzeniach kadrowych – tabela 3.18 (WF-12, WF-16, rys. 3.5).

Źródłem zdarzeń jest system kadrowy; model reaguje automatycznie: nadaje, zmienia lub
odbiera role, przydziały i upoważnienie do przetwarzania danych osobowych (WT7).
Konta przy odejściu są wyłączane, a nie usuwane – ślad audytowy zostaje.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from dostep.model import Klasa, Konto, Okres, TypKonta, Upowaznienie, Uzytkownik
from dostep.polityka.role import ROLE
from dostep.polityka.zakres import w_katalogu, zakres_upowaznienia
from dostep.polityka.zasoby import ZASOBY
from dostep.sod_statyczne import sprawdz_przypisanie_roli

if TYPE_CHECKING:
    from dostep.system import Rezultat, SystemDostepu

BLOKADA_PO_BRAKU_AKTYWNOSCI = timedelta(days=45)
SYGNAL_NIEUZYWANE = timedelta(days=90)
ZASOBY_ZESPOLU = ("Z3", "Z4", "Z5", "Z6", "Z7")


class CyklZycia:
    def __init__(self, system: "SystemDostepu") -> None:
        self.s = system
        self.zgloszone_nieuzywane: set[tuple[str, str]] = set()

    # ------------------------------------------------------------------
    def _zdarzenie(self, czas: datetime, rodzaj: str, u: Uzytkownik, zmiany: list[str]) -> "Rezultat":
        from dostep.system import Rezultat
        self.s.zapisz(czas, "zdarzenie_kadrowe", rodzaj=rodzaj, uzytkownik=u.id)
        for z in zmiany:
            self.s.zapisz(czas, "zmiana_przypisania", uzytkownik=u.id, opis=z, przyczyna=rodzaj,
                          wykonal="IAM (automatycznie)")
        return Rezultat(True, f"{rodzaj}: {u.imie_nazwisko}" + (" – " + "; ".join(zmiany) if zmiany else ""),
                        ["WF-16"], zmiany)

    def _nadaj_upowaznienie(self, u: Uzytkownik, czas: datetime) -> str:
        zakres = zakres_upowaznienia(u, self.s.rejestr.katalog)
        if u.upowaznienie:
            u.upowaznienie.odwolane_o = czas
        u.upowaznienie = Upowaznienie(zakres, czas, None) if zakres else None
        return (f"upoważnienie do przetwarzania danych osobowych: {', '.join(sorted(zakres, key=lambda z: int(z[1:])))}"
                if zakres else "brak upoważnienia do danych osobowych (funkcja go nie wymaga)")

    # ------------------------------------------------------------------
    def zatrudnij(self, u: Uzytkownik, czas: datetime) -> "Rezultat":
        """Zatrudnienie, początek kontraktu lub stażu – rola bazowa i funkcyjna z danych kadrowych."""
        from dostep.system import Rezultat
        if ROLE.get(u.rola_funkcyjna) is None:
            return Rezultat(False, f"nieznana rola {u.rola_funkcyjna}")
        u.aktywny, u.data_zatrudnienia = True, czas
        u.role_uprzywilejowane, u.przydzialy = set(), []
        self.s.rejestr.dodaj(u, Konto(u.id, u.id))
        zmiany = [f"rola bazowa i rola funkcyjna {u.rola_funkcyjna} ({ROLE[u.rola_funkcyjna].nazwa})",
                  f"konto {u.id}", self._nadaj_upowaznienie(u, czas)]
        if u.data_konca_umowy:
            zmiany.append(f"wszystkie uprawnienia wygasają {u.data_konca_umowy} ({u.forma.value})")
        return self._zdarzenie(czas, "zatrudnienie", u, zmiany)

    def zloz_oswiadczenie_nda(self, uzytkownik_id: str, klient: str, czas: datetime) -> "Rezultat":
        """Oświadczenie o poufności przy przypisaniu do projektu klienta (WT1, źródło: rejestr umów)."""
        u = self.s.rejestr.uzytkownik(uzytkownik_id)
        u.oswiadczenia_nda.add(klient)
        return self._zdarzenie(czas, "oświadczenie o poufności", u, [f"oświadczenie wobec {klient} (WT1)"])

    def przenies(self, uzytkownik_id: str, nowy_zespol: str, czas: datetime, plemie: str | None = None,
                 jednostka: str | None = None, przelozony_id: str | None = None) -> "Rezultat":
        """Przeniesienie: natychmiast zapis/zatwierdzanie/KW4 w starym zespole znika, odczyt 14 dni (RC12)."""
        u = self.s.rejestr.uzytkownik(uzytkownik_id)
        zmiany = [f"zespół {u.zespol} → {nowy_zespol}; odczyt zasobów {u.zespol} przez 14 dni (RC12)"]
        u.poprzedni_zespol, u.data_przeniesienia = u.zespol, czas
        u.zespol, u.zespol_tymczasowy = nowy_zespol, None
        u.plemie = plemie or u.plemie
        u.jednostka = jednostka or u.jednostka
        u.przelozony_id = przelozony_id or u.przelozony_id
        if u.dyzury:
            u.dyzury = [d for d in u.dyzury if d.do < czas]
            zmiany.append("usunięto dyżury dotychczasowego zespołu (koniec RE1/RE2)")
        odebrane = [p for p in u.przydzialy if ZASOBY[p.zasob].klasa is Klasa.KW4 or p.zasob in ZASOBY_ZESPOLU]
        for p in odebrane:
            u.przydzialy.remove(p)
            zmiany.append(f"odebrano {p.klucz()} (uprawnienie związane z dotychczasowym zespołem)")
        zmiany.append(self._nadaj_upowaznienie(u, czas))
        return self._zdarzenie(czas, "przeniesienie między zespołami", u, zmiany)

    def przenies_czasowo(self, uzytkownik_id: str, zespol_docelowy: str, czas: datetime) -> "Rezultat":
        """Embedding: uprawnienia zespołu docelowego (RC1), w macierzystym tylko odczyt (RC11)."""
        u = self.s.rejestr.uzytkownik(uzytkownik_id)
        u.zespol_tymczasowy = zespol_docelowy
        return self._zdarzenie(czas, "czasowe przeniesienie", u,
                               [f"uprawnienia zespołu {zespol_docelowy} (RC1); w zespole {u.zespol} tylko odczyt (RC11)"])

    def zakoncz_przeniesienie_czasowe(self, uzytkownik_id: str, czas: datetime) -> "Rezultat":
        u = self.s.rejestr.uzytkownik(uzytkownik_id)
        stary, u.zespol_tymczasowy = u.zespol_tymczasowy, None
        return self._zdarzenie(czas, "koniec czasowego przeniesienia", u, [f"koniec uprawnień w zespole {stary}"])

    def zmien_stanowisko(self, uzytkownik_id: str, nowa_rola: str, czas: datetime, poziom: str | None = None,
                         stanowisko: str | None = None) -> "Rezultat":
        """Zmiana roli funkcyjnej lub poziomu – poprzednia rola odbierana natychmiast."""
        from dostep.system import Rezultat
        u = self.s.rejestr.uzytkownik(uzytkownik_id)
        if ROLE.get(nowa_rola) is None:
            return Rezultat(False, f"nieznana rola {nowa_rola}")
        stara = u.rola_funkcyjna
        zmiany = [f"rola {stara} ({ROLE[stara].nazwa}) → {nowa_rola} ({ROLE[nowa_rola].nazwa})"]
        u.rola_funkcyjna = nowa_rola
        if poziom and poziom != u.poziom:
            zmiany.append(f"poziom {u.poziom} → {poziom}")
            u.poziom = poziom
        if stanowisko is not None:
            u.stanowisko = stanowisko
        # role uprzywilejowane, których nowa funkcja nie dopuszcza (tab. 3.11, SS)
        for r in sorted(u.role_uprzywilejowane):
            if nowa_rola not in ROLE[r].kto_moze or any(
                    n.regula.startswith("SS") for n in sprawdz_przypisanie_roli(u, r)):
                u.role_uprzywilejowane.discard(r)
                zmiany.append(f"odebrano rolę uprzywilejowaną {r}")
        # przydziały spoza katalogu nowej roli
        for p in list(u.przydzialy):
            if w_katalogu(u, self.s.rejestr.katalog, p.zasob, p.operacje, p.typ_rekordu) is None:
                u.przydzialy.remove(p)
                zmiany.append(f"odebrano {p.klucz()} (spoza katalogu nowej roli)")
        if u.dyzury and nowa_rola not in ("T1", "T9"):
            u.dyzury = []
            zmiany.append("usunięto z grafiku dyżurów")
        zmiany.append(self._nadaj_upowaznienie(u, czas))
        return self._zdarzenie(czas, "zmiana stanowiska", u, zmiany)

    def dyzur(self, uzytkownik_id: str, od: datetime, do: datetime, czas: datetime) -> "Rezultat":
        """Wpis do grafiku dyżurów – uprawnienia czasowe RE1/RE2 wygasają same."""
        u = self.s.rejestr.uzytkownik(uzytkownik_id)
        u.dyzury.append(Okres(od, do))
        return self._zdarzenie(czas, "dyżur", u, [f"dyżur {od:%Y-%m-%d %H:%M} – {do:%H:%M} (RE1, RE2)"])

    def zmiana_wsparcia(self, uzytkownik_id: str, od: datetime, do: datetime, czas: datetime) -> "Rezultat":
        u = self.s.rejestr.uzytkownik(uzytkownik_id)
        u.zmiany_wsparcia.append(Okres(od, do))
        return self._zdarzenie(czas, "zmiana w grafiku wsparcia", u, [f"zmiana {od:%Y-%m-%d %H:%M} – {do:%H:%M} (RC16)"])

    def odejscie(self, uzytkownik_id: str, czas: datetime, przyczyna: str = "odejście z organizacji") -> "Rezultat":
        """Odebranie wszystkich ról i blokada kont (także administracyjnych); konta nie są usuwane."""
        r = self.s.rejestr
        u = r.uzytkownik(uzytkownik_id)
        zmiany = []
        u.aktywny = False
        for k in r.konta_uzytkownika(u.id):
            if k.typ is TypKonta.USLUGOWE:
                self.s.sygnal(czas, f"konto usługowe {k.id} straciło właściciela ({u.imie_nazwisko}) – "
                                    f"wyznacz nowego", u.id)
                continue
            if k.aktywne:
                k.aktywne, k.zablokowane_o, k.powod_blokady = False, czas, przyczyna
                zmiany.append(f"zablokowano konto {k.id} ({k.typ.value})")
        for sesja in r.sesje.values():
            if r.konto(sesja.konto_id).uzytkownik_id == u.id:
                for rola, okres in list(sesja.aktywne_role.items()):
                    if okres.do > czas:
                        sesja.aktywne_role[rola] = Okres(okres.od, czas)
                        zmiany.append(f"zakończono sesję {sesja.id}")
        if u.role_uprzywilejowane:
            zmiany.append(f"odebrano role uprzywilejowane: {', '.join(sorted(u.role_uprzywilejowane))}")
            u.role_uprzywilejowane = set()
        if u.przydzialy:
            zmiany.append(f"odebrano przydziały: {', '.join(p.klucz() for p in u.przydzialy)}")
            u.przydzialy = []
        if u.upowaznienie and u.upowaznienie.odwolane_o is None:
            u.upowaznienie.odwolane_o = czas
            zmiany.append("odwołano upoważnienie do przetwarzania danych osobowych")
        u.dyzury, u.zastepstwa = [], []
        if u.wlasciciel_zasobow:
            self.s.sygnal(czas, f"zasoby bez właściciela po odejściu {u.imie_nazwisko}: "
                                f"{', '.join(sorted(u.wlasciciel_zasobow))} – wyznacz nowego", u.id)
            zmiany.append(f"odebrano rolę właściciela {', '.join(sorted(u.wlasciciel_zasobow))}")
            u.wlasciciel_zasobow = set()
        zmiany += self._przekaz_zadania(u, czas)
        return self._zdarzenie(czas, przyczyna, u, zmiany)

    def _przekaz_zadania(self, u: Uzytkownik, czas: datetime) -> list[str]:
        """Otwarte zadania osoby odchodzącej przechodzą na aktywnego przełożonego (lub wyżej)."""
        nastepca = next(iter(self.s.dostepny_akceptujacy(self.s.przelozony(u), czas)), None)
        if nastepca is None:
            return []
        zmiany = []
        for z in self.s.przeglady:
            if z.status == "otwarte" and z.recenzent_id == u.id:
                z.recenzent_id = nastepca.id
                zmiany.append(f"zadanie {z.id} przekazano: {nastepca.imie_nazwisko}")
        for p in self.s.recertyfikacja.pozycje.values():
            if p.status in ("oczekuje", "eskalowana") and p.recenzent_id == u.id and p.uzytkownik_id != nastepca.id:
                p.recenzent_id = nastepca.id
                zmiany.append(f"recertyfikację {p.id} przekazano: {nastepca.imie_nazwisko}")
        for w in self.s.wnioski.wnioski.values():
            for wym in w.wymagania:
                if wym.udzielona_przez is None and u.id in wym.kandydaci:
                    wym.kandydaci = [k for k in wym.kandydaci if k != u.id]
                    if nastepca.id not in (w.wnioskujacy_id, w.beneficjent_id) and nastepca.id not in wym.kandydaci:
                        wym.kandydaci.append(nastepca.id)
                    zmiany.append(f"akceptację wniosku {w.id} przekazano: {nastepca.imie_nazwisko}")
        return zmiany

    # ------------------------------------------------------------------
    def przetworz(self, czas: datetime) -> list[str]:
        """Zadanie codzienne: koniec umów, wygasłe przydziały, blokada po 45 dniach, sygnał po 90 dniach."""
        dzialania: list[str] = []
        for u in list(self.s.rejestr.uzytkownicy.values()):
            if not u.aktywny:
                continue
            # koniec kontraktu B2B lub stażu – wszystkie uprawnienia wygasają w dniu końca umowy
            if u.data_konca_umowy and czas.date() > u.data_konca_umowy:
                self.odejscie(u.id, czas, przyczyna=f"koniec umowy ({u.forma.value})")
                dzialania.append(f"koniec umowy: {u.imie_nazwisko}")
                continue
            # wygasłe przydziały (w tym zastępstwa awaryjne bez akceptacji po fakcie)
            for p in [p for p in u.przydzialy if p.okres and p.okres.do < czas]:
                u.przydzialy.remove(p)
                powod = "brak akceptacji po fakcie" if p.awaryjny else "upływ terminu"
                self.s.zapisz(czas, "zmiana_przypisania", rodzaj="wygaśnięcie", uzytkownik=u.id,
                              uprawnienie=p.klucz(), powod=powod, wykonal="IAM (automatycznie)")
                dzialania.append(f"wygasło {p.klucz()} – {u.imie_nazwisko} ({powod})")
            # brak aktywności – blokada konta po 45 dniach
            ostatnia = u.ostatnia_aktywnosc or u.data_zatrudnienia
            if ostatnia and czas - ostatnia > BLOKADA_PO_BRAKU_AKTYWNOSCI:
                for k in self.s.rejestr.konta_uzytkownika(u.id):
                    if k.typ is TypKonta.ZWYKLE and k.aktywne:
                        k.aktywne, k.zablokowane_o, k.powod_blokady = False, czas, "brak aktywności 45 dni"
                        self.s.zapisz(czas, "blokada_konta", konto=k.id, powod=k.powod_blokady)
                        dzialania.append(f"zablokowano {k.id} (brak aktywności 45 dni)")
            # uprawnienia nieużywane przez 90 dni – sygnalizacja i przegląd
            for p in u.przydzialy:
                uzycia = [t for klucz, t in u.ostatnie_uzycie.items()
                          if klucz.split(":")[0] == p.zasob and klucz.split(":")[1] in {o.value for o in p.operacje}]
                ostatnie = max(uzycia, default=p.okres.od if p.okres else None)
                if ostatnie and czas - ostatnie > SYGNAL_NIEUZYWANE and (u.id, p.klucz()) not in self.zgloszone_nieuzywane:
                    self.zgloszone_nieuzywane.add((u.id, p.klucz()))
                    self.s.sygnal(czas, f"uprawnienie {p.klucz()} nieużywane od 90 dni – {u.imie_nazwisko}", u.id)
                    dzialania.append(f"nieużywane 90 dni: {p.klucz()} – {u.imie_nazwisko}")
        return dzialania
