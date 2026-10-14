"""Przykładowa organizacja – wycinek SoftNova (kilkunastu pracowników, kilkadziesiąt obiektów)
potrzebny do pokazu i scenariuszy SZ1–SZ10. Działa bez bazy danych i API (WN-01).

Pełny generator 199 osób powstanie w etapie E4.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

from dostep.model import (
    Decyzja, FormaWspolpracy, Konto, Obiekt, Okres, Operacja, Siec, Srodowisko, TypKonta,
    Upowaznienie, Urzadzenie, Uzytkownik, Zadanie,
)
from dostep.polityka.zakres import zakres_upowaznienia
from dostep.rejestr import Rejestr
from dostep.system import SystemDostepu

TERAZ = datetime(2026, 10, 14, 10, 0)  # środa, 10:00
X, Y = "Klient X", "Klient Y"


def _uzytkownicy() -> list[Uzytkownik]:
    U = Uzytkownik
    return [
        # --- zarząd ---
        U("grzegorz", "Grzegorz Duda", "B1", "P1", "Zarząd", stanowisko="COO"),
        U("celina", "Celina Wrona", "B1", "P1", "Zarząd", stanowisko="CTO"),
        # --- plemię A „Projekty klienckie” ---
        U("lukasz", "Łukasz Adamczyk", "T6", "P2", "Plemię A", plemie="A", stanowisko="lider plemienia",
          przelozony_id="celina", wlasciciel_zasobow={"Z4"}, oswiadczenia_nda={X, Y}),
        U("piotr", "Piotr Wiśniewski", "T1", "P3", "Plemię A", zespol="A1", plemie="A",
          chapter="A-Backend", stanowisko="lider chaptera", przelozony_id="lukasz", oswiadczenia_nda={X}),
        U("anna", "Anna Nowak", "T1", "P4", "Plemię A", zespol="A1", plemie="A",
          chapter="A-Backend", przelozony_id="piotr", oswiadczenia_nda={X}),
        U("bartek", "Bartosz Lis", "T1", "P4", "Plemię A", zespol="A2", plemie="A",
          chapter="A-Backend", przelozony_id="piotr", oswiadczenia_nda={Y}),
        U("cezary", "Cezary Kowal", "T1", "P4", "Plemię A", zespol="A1", plemie="A",
          forma=FormaWspolpracy.B2B, data_konca_umowy=date(2026, 10, 10), przelozony_id="piotr",
          kierownik_umowy_id="lukasz", oswiadczenia_nda={X}),
        U("igor", "Igor Mazur", "T2", "P5", "Plemię A", zespol="A1", plemie="A", przelozony_id="piotr",
          forma=FormaWspolpracy.STAZ, data_konca_umowy=date(2027, 2, 28), oswiadczenia_nda={X}),
        U("jola", "Jolanta Krawczyk", "T3", "P4", "Plemię A", zespol="A1", plemie="A",
          przelozony_id="piotr", oswiadczenia_nda={X}),
        U("olek", "Aleksander Pawlak", "T5", "P4", "Plemię A", zespol="A1", plemie="A",
          przelozony_id="lukasz", oswiadczenia_nda={X}),
        # --- plemię B „Produkt SaaS” ---
        U("beata", "Beata Sowa", "T6", "P2", "Plemię B", plemie="B", stanowisko="lider plemienia",
          przelozony_id="celina", wlasciciel_zasobow={"Z5"}),
        U("daria", "Daria Zając", "T1", "P4", "Plemię B", zespol="B1", plemie="B", przelozony_id="beata",
          dyzury=[Okres(TERAZ - timedelta(hours=1), TERAZ + timedelta(hours=7))]),
        U("emil", "Emil Wróbel", "T1", "P4", "Plemię B", zespol="B2", plemie="B", przelozony_id="beata",
          dyzury=[Okres(TERAZ - timedelta(days=3), TERAZ - timedelta(days=2, hours=16))]),
        # --- plemię C „Platforma i bezpieczeństwo” ---
        U("radek", "Radosław Pietrzak", "T9", "P3", "Plemię C", zespol="C-DevOps", plemie="C",
          stanowisko="lider DevOps/SRE", przelozony_id="celina", wlasciciel_zasobow={"Z6", "Z7", "Z8"},
          role_uprzywilejowane={"ADM_Z6"}),
        U("sylwia", "Sylwia Kaczmarek", "T9", "P4", "Plemię C", zespol="C-DevOps", plemie="C",
          przelozony_id="radek", role_uprzywilejowane={"ADM_Z8"}),
        U("wanda", "Wanda Lewandowska", "T10", "P3", "Plemię C", zespol="C-Sec", plemie="C",
          stanowisko="lider bezpieczeństwa", przelozony_id="celina", wlasciciel_zasobow={"Z9", "Z16", "Z17"}),
        U("henryk", "Henryk Szulc", "T11", "P4", "Plemię C", zespol="C-IT", plemie="C",
          przelozony_id="celina", role_uprzywilejowane={"ADM_Z10", "ADM_Z13", "ADM_Z17"}),
        U("tomasz", "Tomasz Michalski", "T12", "P4", "Plemię C", zespol="C-BI", plemie="C",
          przelozony_id="celina"),
        # --- działy biznesowe ---
        U("zbigniew", "Zbigniew Kaczor", "B4", "P2", "Sprzedaż", stanowisko="dyrektor sprzedaży",
          przelozony_id="grzegorz", wlasciciel_zasobow={"Z10"}),
        U("kamil", "Kamil Górski", "B4", "P4", "Sprzedaż", przypisani_klienci={X}, przelozony_id="zbigniew"),
        U("felicja", "Felicja Baran", "B7", "P2", "Finanse", stanowisko="główna księgowa",
          przelozony_id="grzegorz", wlasciciel_zasobow={"Z12"}),
        U("edward", "Edward Sikora", "B7", "P4", "Finanse", przelozony_id="felicja"),
        U("natalia", "Natalia Kozieł", "B9", "P2", "HR", stanowisko="kierownik HR",
          przelozony_id="grzegorz", wlasciciel_zasobow={"Z13", "Z14"}),
        U("marta", "Marta Wójcik", "B11", "P4", "HR", przelozony_id="natalia"),
        U("patryk", "Patryk Zieliński", "B2", "P3", "Dział prawny", stanowisko="prawnik",
          przelozony_id="grzegorz", wlasciciel_zasobow={"Z15"}),
        U("ula", "Urszula Jabłońska", "B3", "P3", "Dział prawny", stanowisko="IOD", przelozony_id="grzegorz"),
    ]


def _obiekty() -> list[Obiekt]:
    O = Obiekt
    return [
        O("wiki", "Z2", "strona intranetu"),
        O("zadanie_a1", "Z3", "zadanie zespołu A1", zespol="A1", plemie="A", klient=X),
        O("zadanie_b1", "Z3", "zadanie zespołu B1", zespol="B1", plemie="B"),
        O("repo_x", "Z4", "repozytorium projektu Klienta X", zespol="A1", plemie="A", klient=X),
        O("repo_y", "Z4", "repozytorium projektu Klienta Y", zespol="A2", plemie="A", klient=Y),
        O("galaz_igora", "Z4", "gałąź stażysty", zespol="A1", plemie="A", klient=X, autor_id="igor"),
        O("mr_anny", "Z4", "zmiana kodu Anny", zespol="A1", plemie="A", klient=X,
          typ_rekordu="zmiana_kodu", autor_id="anna", proces="SO1"),
        O("odbior_testow", "Z4", "odbiór testów zmiany Anny", zespol="A1", plemie="A", klient=X,
          typ_rekordu="odbior_testow", autor_id="anna", proces="SO9"),
        O("cicd_a1", "Z6", "potok CI/CD zespołu A1", zespol="A1", plemie="A", klient=X),
        O("wdrozenie_a1", "Z6", "wydanie zespołu A1", zespol="A1", plemie="A", klient=X,
          autor_id="anna", proces="SO2"),
        O("wydanie_a1", "Z8", "wdrożenie wydania A1 na produkcję", typ_rekordu="wydanie",
          autor_id="anna", proces="SO2", zrodlo_id="wdrozenie_a1"),
        O("prod_infra", "Z8", "infrastruktura produkcji", typ_rekordu="infrastruktura"),
        O("prod_dane", "Z8", "baza klientów SaaS", typ_rekordu="dane_klientow"),
        O("sekret_a1", "Z9", "sekrety potoku A1", typ_rekordu="sekret_projektu", zespol="A1"),
        O("crm_x", "Z10", "karta Klienta X", klient=X),
        O("crm_y", "Z10", "karta Klienta Y (pełne dane)", klient=Y),
        O("crm_y_podst", "Z10", "dane podstawowe Klienta Y", klient=Y, typ_rekordu="dane_podstawowe"),
        O("raport_sprzedazy", "Z10", "raport sprzedaży", typ_rekordu="widok_raportowy"),
        O("przelew_maly", "Z12", "przelew 12 000 zł", jednostka="Finanse", autor_id="edward",
          proces="SO3", kwota=12_000),
        O("przelew_duzy", "Z12", "przelew 80 000 zł", jednostka="Finanse", autor_id="edward",
          proces="SO3", kwota=80_000),
        O("przelew_fikcyjny", "Z12", "przelew na rzecz fikcyjnego kontrahenta", jednostka="Finanse",
          autor_id="edward", proces="SO3", kwota=30_000),
        O("przelew_felicji", "Z12", "przelew przygotowany przez główną księgową", jednostka="Finanse",
          autor_id="felicja", proces="SO3", kwota=8_000),
        O("kadry_anna", "Z13", "dane kadrowe Anny", jednostka="Plemię A", typ_rekordu="rekord_kadrowy",
          dotyczy_osoby_id="anna"),
        O("zdrowie_anna", "Z13", "zaświadczenie lekarskie Anny", jednostka="Plemię A",
          typ_rekordu="dane_o_zdrowiu", dotyczy_osoby_id="anna"),
        O("lista_plac", "Z13", "lista płac 10/2026", autor_id="marta", proces="SO4"),
        O("iam_przypisanie", "Z17", "przypisanie uprawnień", typ_rekordu="przypisanie"),
        O("wniosek_anny", "Z17", "wniosek Anny", typ_rekordu="wniosek", autor_id="anna"),
    ]


class Przyklad:
    """Przykładowa organizacja podłączona do systemu dostępu (PDP + procesy)."""

    def __init__(self) -> None:
        self.rejestr = Rejestr()
        for u in _uzytkownicy():
            u.data_zatrudnienia = TERAZ - timedelta(days=400)
            u.ostatnia_aktywnosc = TERAZ - timedelta(days=1)
            self.rejestr.dodaj(u, Konto(u.id, u.id))
        self.rejestr.dodaj(
            Konto("henryk-adm", "henryk", TypKonta.ADMINISTRACYJNE),
            Konto("sylwia-adm", "sylwia", TypKonta.ADMINISTRACYJNE),
            Konto("radek-adm", "radek", TypKonta.ADMINISTRACYJNE),
            Konto("cicd-potok", "radek", TypKonta.USLUGOWE, rola="USL_CICD"),
        )
        for o in _obiekty():
            self.rejestr.dodaj(o)
        # Upoważnienia do przetwarzania danych osobowych (WT7) – zakres wynikający z funkcji.
        for u in self.rejestr.uzytkownicy.values():
            zakres = zakres_upowaznienia(u, self.rejestr.katalog)
            if zakres:
                u.upowaznienie = Upowaznienie(zakres, TERAZ - timedelta(days=365))
        self.system = SystemDostepu(self.rejestr)
        self.dziennik = self.system.dziennik

    def u(self, id_: str) -> Uzytkownik:
        return self.rejestr.uzytkownik(id_)

    def zadanie(self, konto: str, op: str, obiekt: str, czas: datetime = TERAZ,
                urzadzenie: Urzadzenie = Urzadzenie.FIRMOWE, siec: Siec = Siec.BIURO,
                sesja: str | None = None) -> Zadanie:
        return Zadanie(konto, Operacja(op), obiekt, Srodowisko(czas, urzadzenie, siec), sesja)

    def pdp(self, konto: str, op: str, obiekt: str, czas: datetime = TERAZ,
            urzadzenie: Urzadzenie = Urzadzenie.FIRMOWE, siec: Siec = Siec.BIURO,
            sesja: str | None = None, interaktywne: bool = True) -> Decyzja:
        """Żądanie przez PEP: decyzja PDP + wpis do dziennika + skutki (historia zatwierdzeń)."""
        return self.system.zadaj(konto, op, obiekt, czas, urzadzenie, siec, sesja, interaktywne)
