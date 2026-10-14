"""Generator pełnej organizacji modelowej SoftNova sp. z o.o. – 199 osób (podrozdział 3.1,
załącznik 1: tabele Z1.1–Z1.3, katalog ról: tabela 3.8).

Generator jest deterministyczny (stałe ziarno) – za każdym razem powstaje ta sama organizacja,
więc wyniki metryk są powtarzalne (WN-02). Imiona i nazwiska są losowane z list i fikcyjne,
podobnie jak nazwy klientów.

Struktura:
  * zarząd (prezes, CTO, COO), dział prawny (prawnik, IOD), role przekrojowe (chief architect, 2 agile coachów),
  * plemię A „Projekty klienckie”: lider + 7 zespołów po 9 osób (każdy zespół = projekt jednego klienta),
  * plemię B „Produkt SaaS”: lider + 5 zespołów po 9 osób (każdy zespół = moduł produktu),
  * plemię C „Platforma i bezpieczeństwo”: lider + DevOps/SRE (10), bezpieczeństwo (5), IT wewnętrzne (7), dane/BI (5),
  * 8 stażystów w zespołach plemion A i B, ponad podstawowy skład,
  * sprzedaż i obsługa klienta (22), finanse (7), HR (9), marketing (4), administracja biura (3).
Skład zespołu A/B (tab. Z1.2): PO, 3 programistów backend, 2 frontend/mobile, 2 testerów, 1 projektant UX/analityk.
"""
from __future__ import annotations

import random
import unicodedata
from datetime import date, datetime, timedelta

from dostep.model import (
    FormaWspolpracy, Konto, Obiekt, Okres, TypKonta, Upowaznienie, Uzytkownik,
)
from dostep.polityka.zakres import zakres_upowaznienia
from dostep.rejestr import Rejestr
from dostep.sod_statyczne import sprawdz_przypisanie_roli

DATA_GENERACJI = datetime(2026, 10, 14, 10, 0)
ZIARNO = 2026

# Fikcyjni klienci projektów plemienia A (zespół A1 → pierwszy klient itd.)
KLIENCI = ["EnergoPol", "MedTech Polska", "BankoNet", "LogiTrans", "AgroDane", "RetailPlus", "UbezPro"]
MODULY_B = ["płatności", "konta klientów", "raportowanie", "integracje", "aplikacja mobilna"]

IMIONA = ["Adam", "Agnieszka", "Aleksandra", "Andrzej", "Anna", "Barbara", "Bartosz", "Beata", "Dariusz",
          "Dorota", "Ewa", "Filip", "Grzegorz", "Hanna", "Igor", "Iwona", "Jakub", "Joanna", "Kamil",
          "Karolina", "Katarzyna", "Krzysztof", "Łukasz", "Magdalena", "Marcin", "Maria", "Mateusz",
          "Michał", "Monika", "Natalia", "Oliwia", "Paweł", "Piotr", "Rafał", "Sebastian", "Szymon",
          "Tomasz", "Weronika", "Wojciech", "Zofia"]
NAZWISKA = ["Nowak", "Wójcik", "Kowalczyk", "Kaczmarek", "Mazur", "Krawczyk", "Zając", "Król", "Wieczorek",
            "Wróbel", "Dudek", "Adamczyk", "Pawlak", "Walczak", "Sikora", "Baran", "Duda", "Szewczyk",
            "Michalak", "Pietrzak", "Marciniak", "Kubiak", "Wilk", "Lis", "Mazurek", "Kołodziej", "Sowa",
            "Kozieł", "Kaczor", "Bąk", "Wrona", "Sobczak", "Urban", "Głowacz", "Kurek", "Szulc"]


def _ascii(tekst: str) -> str:
    tekst = tekst.replace("ł", "l").replace("Ł", "L")
    return unicodedata.normalize("NFKD", tekst).encode("ascii", "ignore").decode().lower()


class GeneratorOrganizacji:
    def __init__(self, ziarno: int = ZIARNO, teraz: datetime = DATA_GENERACJI) -> None:
        self.los = random.Random(ziarno)
        self.teraz = teraz
        self.r = Rejestr()

    # ------------------------------------------------------------------
    def _osoba(self, rola: str, poziom: str, jednostka: str, **atrybuty) -> Uzytkownik:
        while True:
            imie, nazwisko = self.los.choice(IMIONA), self.los.choice(NAZWISKA)
            id_ = _ascii(f"{imie}.{nazwisko}")
            if id_ not in self.r.uzytkownicy:
                break
        u = Uzytkownik(id_, f"{imie} {nazwisko}", rola, poziom, jednostka, **atrybuty)
        u.data_zatrudnienia = self.teraz - timedelta(days=self.los.randint(60, 2500))
        u.ostatnia_aktywnosc = self.teraz - timedelta(hours=self.los.randint(1, 96))
        self.r.dodaj(u, Konto(u.id, u.id))
        return u

    def _b2b(self, u: Uzytkownik, kierownik: Uzytkownik) -> None:
        u.forma = FormaWspolpracy.B2B
        u.kierownik_umowy_id = kierownik.id
        u.data_konca_umowy = self.teraz.date() + timedelta(days=self.los.randint(90, 420))

    def _rola_uprzywilejowana(self, u: Uzytkownik, rola: str) -> None:
        naruszenia = sprawdz_przypisanie_roli(u, rola)
        if naruszenia:   # generator nie może tworzyć danych łamiących SoD
            raise ValueError(f"{u.id} – {rola}: {[n.regula for n in naruszenia]}")
        u.role_uprzywilejowane.add(rola)
        if f"{u.id}-adm" not in self.r.konta:
            self.r.dodaj(Konto(f"{u.id}-adm", u.id, TypKonta.ADMINISTRACYJNE))

    # ------------------------------------------------------------------
    def zbuduj(self) -> Rejestr:
        t = self.teraz
        o = self._osoba

        # --- zarząd, dział prawny, role przekrojowe ---
        prezes = o("B1", "P1", "Zarząd", stanowisko="prezes")
        cto = o("B1", "P1", "Zarząd", stanowisko="CTO", przelozony_id=prezes.id)
        coo = o("B1", "P1", "Zarząd", stanowisko="COO", przelozony_id=prezes.id)
        o("B2", "P3", "Dział prawny", stanowisko="prawnik", przelozony_id=prezes.id, wlasciciel_zasobow={"Z15"})
        o("B3", "P3", "Dział prawny", stanowisko="IOD", przelozony_id=prezes.id)
        architekt = o("T7", "P2", "Role przekrojowe", stanowisko="chief architect", przelozony_id=cto.id)
        coach1 = o("T8", "P4", "Role przekrojowe", przelozony_id=cto.id)
        coach2 = o("T8", "P4", "Role przekrojowe", przelozony_id=cto.id)
        self._b2b(coach2, cto)

        # --- plemiona A i B ---
        zespoly_a = [f"A{i}" for i in range(1, 8)]
        zespoly_b = [f"B{i}" for i in range(1, 6)]
        lider_a = o("T6", "P2", "Plemię A", plemie="A", stanowisko="lider plemienia", przelozony_id=cto.id,
                    wlasciciel_zasobow={"Z4"}, oswiadczenia_nda=set(KLIENCI))
        lider_b = o("T6", "P2", "Plemię B", plemie="B", stanowisko="lider plemienia", przelozony_id=cto.id,
                    wlasciciel_zasobow={"Z5"})
        self.klient_zespolu = dict(zip(zespoly_a, KLIENCI))
        for plemie, lider, zespoly, b2b_nr in (("A", lider_a, zespoly_a, 6), ("B", lider_b, zespoly_b, 3)):
            self._plemie(plemie, lider, zespoly, b2b_nr)

        architekt.zespoly_wspierane = {"A1", "A2", "B1"}
        architekt.oswiadczenia_nda = {self.klient_zespolu["A1"], self.klient_zespolu["A2"]}
        coach1.zespoly_wspierane = set(zespoly_a[:4])
        coach1.oswiadczenia_nda = {self.klient_zespolu[z] for z in zespoly_a[:4]}
        coach2.zespoly_wspierane = set(zespoly_a[4:] + zespoly_b)
        coach2.oswiadczenia_nda = {self.klient_zespolu[z] for z in zespoly_a[4:]}

        # --- plemię C ---
        lider_c = o("T6", "P2", "Plemię C", plemie="C", stanowisko="lider plemienia", przelozony_id=cto.id)
        self._plemie_c(lider_c)

        # --- sprzedaż i obsługa klienta (22) ---
        dyr = o("B4", "P2", "Sprzedaż", stanowisko="dyrektor sprzedaży", przelozony_id=coo.id,
                wlasciciel_zasobow={"Z10"})
        am = [o("B4", "P4", "Sprzedaż", przelozony_id=dyr.id) for _ in range(6)]
        for i, klient in enumerate(KLIENCI):
            am[i % len(am)].przypisani_klienci.add(klient)
        for _ in range(3):
            o("B5", "P4", "Sprzedaż", przelozony_id=dyr.id, przypisani_klienci={self.los.choice(KLIENCI)})
        kier_wsp = o("B6", "P3", "Sprzedaż", stanowisko="kierownik wsparcia", zespol="Wsparcie",
                     przelozony_id=dyr.id, wlasciciel_zasobow={"Z11"})
        for i in range(11):
            linia = "L1" if i < 8 else "L2"
            u = o("B6", "P4", "Sprzedaż", stanowisko=f"wsparcie {linia}", zespol="Wsparcie", przelozony_id=kier_wsp.id)
            if i % 2 == 0:   # połowa ma zmianę w grafiku wsparcia dziś (RC16)
                u.zmiany_wsparcia.append(Okres(t.replace(hour=8), t.replace(hour=16)))

        # --- finanse (7) ---
        gk = o("B7", "P2", "Finanse", stanowisko="główna księgowa", przelozony_id=coo.id, wlasciciel_zasobow={"Z12"})
        for _ in range(4):
            o("B7", "P4", "Finanse", przelozony_id=gk.id)
        for _ in range(2):
            o("B8", "P4", "Finanse", przelozony_id=gk.id)

        # --- HR (9) ---
        khr = o("B9", "P2", "HR", stanowisko="kierownik HR", przelozony_id=coo.id, wlasciciel_zasobow={"Z13", "Z14"})
        o("B9", "P4", "HR", przelozony_id=khr.id, jednostki_hrbp={"Plemię A", "Plemię B"})
        o("B9", "P4", "HR", przelozony_id=khr.id, jednostki_hrbp={
            "Plemię C", "Sprzedaż", "Finanse", "HR", "Marketing", "Administracja biura", "Zarząd",
            "Dział prawny", "Role przekrojowe"})
        for _ in range(4):
            o("B10", "P4", "HR", przelozony_id=khr.id)
        o("B11", "P4", "HR", przelozony_id=khr.id, wyznaczony_wynagrodzenia_zarzadu=True)
        o("B11", "P4", "HR", przelozony_id=khr.id)

        # --- marketing (4), administracja biura (3) ---
        km = o("B12", "P2", "Marketing", stanowisko="kierownik marketingu", przelozony_id=prezes.id,
               wlasciciel_zasobow={"Z1"})
        for _ in range(3):
            o("B12", "P4", "Marketing", przelozony_id=km.id)
        om = o("B13", "P3", "Administracja biura", stanowisko="office manager", przelozony_id=coo.id,
               wlasciciel_zasobow={"Z2"})
        for _ in range(2):
            o("B13", "P4", "Administracja biura", przelozony_id=om.id)

        self._obiekty()
        self._konto_uslugowe()
        for u in self.r.uzytkownicy.values():
            zakres = zakres_upowaznienia(u, self.r.katalog)
            if zakres:
                u.upowaznienie = Upowaznienie(zakres, u.data_zatrudnienia)
        return self.r

    # ------------------------------------------------------------------
    def _plemie(self, plemie: str, lider: Uzytkownik, zespoly: list[str], ile_b2b: int) -> None:
        """Zespoły po 9 osób + chaptery Backend, Frontend/Mobile, QA, UX/Analiza + 4 stażystów."""
        o, t = self._osoba, self.teraz
        jedn = f"Plemię {plemie}"
        liderzy_chapterow: dict[str, Uzytkownik] = {}
        czlonkowie: dict[str, list[Uzytkownik]] = {c: [] for c in ("Backend", "Frontend", "QA", "UX")}
        b2b_do_rozdania = ile_b2b

        for nr, zespol in enumerate(zespoly):
            nda = {self.klient_zespolu[zespol]} if plemie == "A" else set()
            wsp = dict(zespol=zespol, plemie=plemie, oswiadczenia_nda=nda)
            o("T5", "P4", jedn, przelozony_id=lider.id, **wsp)
            sklad = [("T1", "Backend")] * 3 + [("T1", "Frontend")] * 2 + [("T3", "QA")] * 2 + [("T4", "UX")]
            for i, (rola, chapter) in enumerate(sklad):
                u = o(rola, "P4", jedn, chapter=f"{plemie}-{chapter}", **{**wsp, "oswiadczenia_nda": set(nda)})
                if chapter not in liderzy_chapterow:            # pierwszy członek chaptera zostaje jego liderem
                    u.poziom, u.stanowisko, u.przelozony_id = "P3", "lider chaptera", lider.id
                    liderzy_chapterow[chapter] = u
                else:
                    czlonkowie[chapter].append(u)
                # B2B: drugi programista frontend w kolejnych zespołach (nigdy lider chaptera – tab. Z1.3)
                if chapter == "Frontend" and i == 4 and b2b_do_rozdania > 0:
                    self._b2b(u, lider)
                    b2b_do_rozdania -= 1
            # dyżury plemienia B: jeden programista backend z każdego zespołu, kolejne dni
            if plemie == "B":
                dyzurny = [u for u in czlonkowie["Backend"] if u.zespol == zespol][-1]
                start = t.replace(hour=8) + timedelta(days=nr)
                dyzurny.dyzury.append(Okres(start, start + timedelta(hours=12)))
        for chapter, lista in czlonkowie.items():
            for u in lista:
                u.przelozony_id = liderzy_chapterow[chapter].id
        # 4 stażystów w pierwszych czterech zespołach, przełożony: lider chaptera Backend
        for zespol in zespoly[:4]:
            nda = {self.klient_zespolu[zespol]} if plemie == "A" else set()
            s = o("T2", "P5", jedn, zespol=zespol, plemie=plemie, chapter=f"{plemie}-Backend",
                  forma=FormaWspolpracy.STAZ, przelozony_id=liderzy_chapterow["Backend"].id, oswiadczenia_nda=nda,
                  data_konca_umowy=t.date() + timedelta(days=self.los.randint(60, 150)))
            s.data_zatrudnienia = t - timedelta(days=self.los.randint(10, 40))

    def _plemie_c(self, lider: Uzytkownik) -> None:
        o = self._osoba
        jedn = "Plemię C"
        zespoly = [  # (zespół, rola, liczba, stanowisko lidera, zasoby właściciela)
            ("C-DevOps", "T9", 10, "lider DevOps/SRE", {"Z6", "Z7", "Z8"}),
            ("C-Sec", "T10", 5, "lider bezpieczeństwa", {"Z9", "Z16", "Z17"}),
            ("C-IT", "T11", 7, "lider IT wewnętrznego", {"Z3"}),
            ("C-BI", "T12", 5, "lider zespołu danych", set()),
        ]
        for zespol, rola, ile, stanowisko, wlasnosc in zespoly:
            szef = o(rola, "P3", jedn, zespol=zespol, plemie="C", stanowisko=stanowisko, przelozony_id=lider.id,
                     wlasciciel_zasobow=set(wlasnosc))
            ludzie = [szef] + [o(rola, "P4", jedn, zespol=zespol, plemie="C", przelozony_id=szef.id)
                               for _ in range(ile - 1)]
            if rola == "T9":
                for u in ludzie[-2:]:
                    self._b2b(u, lider)
                for u in ludzie:
                    for nr in range(4, 10):
                        if not (u is szef and nr == 8):           # SS5: właściciel Z8 nie administruje Z8
                            self._rola_uprzywilejowana(u, f"ADM_Z{nr}")
                ludzie[1].dyzury.append(Okres(self.teraz.replace(hour=8), self.teraz.replace(hour=20)))
            elif rola == "T11":
                for u in ludzie:
                    for nr in (1, 2, 3, 10, 11, 12, 14, 15):
                        self._rola_uprzywilejowana(u, f"ADM_Z{nr}")
                for u in ludzie[1:3]:                               # dwóch wyznaczonych administratorów Z13 i Z17
                    self._rola_uprzywilejowana(u, "ADM_Z13")
                    self._rola_uprzywilejowana(u, "ADM_Z17")
            elif rola == "T10":
                for u in ludzie[1:]:
                    self._rola_uprzywilejowana(u, "ADM_Z16")

    def _konto_uslugowe(self) -> None:
        wl = self.r.po_stanowisku("lider DevOps/SRE")
        self.r.dodaj(Konto("cicd-potok", wl.id, TypKonta.USLUGOWE, rola="USL_CICD"))

    # ------------------------------------------------------------------
    def _obiekty(self) -> None:
        """Reprezentatywne obiekty w zasobach Z1–Z17 (do decyzji, wykazów i metryk)."""
        dodaj = self.r.dodaj
        dodaj(Obiekt("strona_www", "Z1", "strona internetowa"), Obiekt("wiki", "Z2", "intranet"))
        for z, klient in self.klient_zespolu.items():
            dodaj(Obiekt(f"zadania_{z}", "Z3", f"zadania zespołu {z}", zespol=z, plemie="A", klient=klient),
                  Obiekt(f"repo_{z}", "Z4", f"repozytorium projektu {klient}", zespol=z, plemie="A", klient=klient),
                  Obiekt(f"potok_{z}", "Z6", f"potok CI/CD {z}", zespol=z, plemie="A", klient=klient),
                  Obiekt(f"test_{z}", "Z7", f"środowisko testowe {z}", zespol=z, plemie="A", klient=klient),
                  Obiekt(f"sekrety_{z}", "Z9", f"sekrety projektu {klient}", zespol=z, typ_rekordu="sekret_projektu"),
                  Obiekt(f"crm_{_ascii(klient)}", "Z10", f"karta klienta {klient}", klient=klient),
                  Obiekt(f"crm_{_ascii(klient)}_podst", "Z10", f"dane podstawowe {klient}", klient=klient,
                         typ_rekordu="dane_podstawowe"),
                  Obiekt(f"umowa_{_ascii(klient)}", "Z15", f"umowa z {klient}", klient=klient, proces="SO7"))
        for z, modul in zip([f"B{i}" for i in range(1, 6)], MODULY_B):
            dodaj(Obiekt(f"zadania_{z}", "Z3", f"zadania zespołu {z}", zespol=z, plemie="B"),
                  Obiekt(f"modul_{z}", "Z5", f"moduł {modul}", zespol=z, plemie="B"),
                  Obiekt(f"potok_{z}", "Z6", f"potok CI/CD {z}", zespol=z, plemie="B"),
                  Obiekt(f"test_{z}", "Z7", f"środowisko testowe {z}", zespol=z, plemie="B"),
                  Obiekt(f"zgloszenia_{z}", "Z11", f"zgłoszenia modułu {modul}", zespol=z),
                  Obiekt(f"dziennik_{z}", "Z16", f"dzienniki modułu {modul}", typ_rekordu="dziennik_projektu"))
        for jedn in ("Plemię C", "Sprzedaż", "Finanse", "HR", "Marketing", "Administracja biura"):
            dodaj(Obiekt(f"zadania_{_ascii(jedn).replace(' ', '_')}", "Z3", f"zadania: {jedn}", jednostka=jedn))
        dodaj(Obiekt("prod_infra", "Z8", "infrastruktura produkcji", typ_rekordu="infrastruktura"),
              Obiekt("prod_dane", "Z8", "baza klientów SaaS", typ_rekordu="dane_klientow"),
              Obiekt("crm_raport", "Z10", "raport sprzedaży", typ_rekordu="widok_raportowy"),
              Obiekt("crm_kontakty_zgoda", "Z10", "kontakty ze zgodą marketingową", typ_rekordu="kontakt_ze_zgoda"),
              Obiekt("ksiegowosc_raport", "Z12", "raport finansowy", typ_rekordu="widok_raportowy"),
              Obiekt("siem_reguly", "Z16", "reguły i alerty SIEM", typ_rekordu="regula_siem"),
              Obiekt("siem_dziennik", "Z16", "dziennik zdarzeń", typ_rekordu="wpis_dziennika"),
              Obiekt("nda_wzor", "Z15", "wzór NDA"),
              Obiekt("powierzenie_saas", "Z15", "umowa powierzenia – klienci SaaS", typ_rekordu="umowa_powierzenia"),
              Obiekt("lista_plac", "Z13", "lista płac 10/2026", proces="SO4"),
              Obiekt("wynagrodzenia_zarzadu", "Z13", "wynagrodzenia zarządu", typ_rekordu="wynagrodzenie_zarzadu"))
        for jedn in ("Plemię A", "Plemię B", "Plemię C", "Sprzedaż", "Finanse", "HR"):
            k = _ascii(jedn).replace(" ", "_")
            dodaj(Obiekt(f"faktura_{k}", "Z12", f"faktura kosztowa: {jedn}", jednostka=jedn, proces="faktura"),
                  Obiekt(f"kadry_{k}", "Z13", f"dane kadrowe: {jedn}", jednostka=jedn, typ_rekordu="rekord_kadrowy"),
                  Obiekt(f"zdrowie_{k}", "Z13", f"zwolnienia lekarskie: {jedn}", jednostka=jedn,
                         typ_rekordu="dane_o_zdrowiu"),
                  Obiekt(f"rekrutacja_{k}", "Z14", f"rekrutacja: {jedn}", jednostka=jedn,
                         termin_przechowywania=date(2026, 6, 30) if jedn == "Finanse" else None))
        dodaj(Obiekt("przelew_dostawca", "Z12", "przelew do dostawcy 18 000 zł", jednostka="Finanse",
                     proces="SO3", kwota=18_000))


def generuj_organizacje(ziarno: int = ZIARNO) -> Rejestr:
    """Pełna organizacja SoftNova – 199 osób, konta, role uprzywilejowane, obiekty, upoważnienia."""
    return GeneratorOrganizacji(ziarno).zbuduj()
