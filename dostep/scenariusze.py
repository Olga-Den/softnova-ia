"""Przypadki testowe jako dane: scenariusze zagrożeń SZ1–SZ10 (tabela 3.2)
oraz scenariusze zwykłej pracy (metryka M6).

Ta sama lista służy pokazowi (`python -m dostep`), testom i później skryptowi metryk
(M1, M2, M6) – dlatego jest zapisana jako dane.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
from typing import Callable

from dostep.model import Siec, Urzadzenie
from dostep.przyklad import TERAZ, Przyklad as Swiat


@dataclass
class Przypadek:
    id: str
    opis: str
    konto: str
    operacja: str
    obiekt: str
    oczekiwany: str                    # "zezwól" albo "odmów"
    reguly: set[str] = field(default_factory=set)   # reguły, które muszą pojawić się w uzasadnieniu
    krok: int | None = None            # oczekiwany krok algorytmu PDP
    przygotuj: Callable[[Swiat], None] | None = None
    srodowisko: dict = field(default_factory=dict)
    sod: bool = False                  # próba naruszenia SoD (metryka M2)


def _przeniesienie_darii(s: Swiat) -> None:
    """Daria przeniesiona z B1 (plemię B) do A1 dwa dni temu; dyżury plemienia B zakończone."""
    d = s.u("daria")
    d.poprzedni_zespol, d.data_przeniesienia = d.zespol, TERAZ - timedelta(days=2)
    d.zespol, d.plemie, d.jednostka = "A1", "A", "Plemię A"
    d.dyzury = []


def _bez_upowaznienia_kamila(s: Swiat) -> None:
    s.u("kamil").upowaznienie.odwolane_o = TERAZ - timedelta(days=1)


def _wdrozenie_zatwierdzone(s: Swiat) -> None:
    s.rejestr.obiekt("wdrozenie_a1").zatwierdzone_przez.append("olek")


# ---------------------------------------------------------------------------
# Scenariusze zagrożeń (tabela 3.2) – wszystkie powinny kończyć się odmową
# ---------------------------------------------------------------------------
SCENARIUSZE_ZAGROZEN: list[Przypadek] = [
    Przypadek("SZ1", "programista zespołu klienta X czyta repozytorium klienta Y",
              "anna", "R", "repo_y", "odmów", {"WT1", "RC1"}, krok=1),
    Przypadek("SZ2a", "kontraktor B2B po wygaśnięciu umowy loguje się do CI/CD",
              "cezary", "R", "cicd_a1", "odmów", {"WT3"}, krok=1),
    Przypadek("SZ2b", "kontraktor B2B po wygaśnięciu umowy odczytuje sekrety potoku",
              "cezary", "R", "sekret_a1", "odmów", {"WT3"}, krok=1),
    Przypadek("SZ3a", "programista przeniesiony z plemienia B nie ma już dostępu do produkcji",
              "daria", "M", "prod_infra", "odmów", {"RE1"}, krok=6, przygotuj=_przeniesienie_darii),
    Przypadek("SZ3b", "po przeniesieniu nie zapisuje w zadaniach dawnego zespołu (RC12 – tylko odczyt)",
              "daria", "W", "zadanie_b1", "odmów", {"RC1"}, krok=2, przygotuj=_przeniesienie_darii),
    Przypadek("SZ4a", "przejęte konto programisty poza dyżurem – odczyt bazy klientów",
              "emil", "R", "prod_dane", "odmów", {"RE4"}, krok=6),
    Przypadek("SZ4b", "przejęte konto na dyżurze, ale z urządzenia prywatnego",
              "daria", "R", "prod_infra", "odmów", {"WT2"}, krok=1,
              srodowisko={"urzadzenie": Urzadzenie.PRYWATNE, "siec": Siec.ZEWNETRZNA}),
    Przypadek("SZ5a", "księgowy sam zatwierdza przelew na rzecz fikcyjnego kontrahenta",
              "edward", "A", "przelew_fikcyjny", "odmów", {"SO3", "RC13"}, krok=2, sod=True),
    Przypadek("SZ5b", "główna księgowa zatwierdza przelew, który sama przygotowała",
              "felicja", "A", "przelew_felicji", "odmów", {"SO3"}, krok=3, sod=True),
    Przypadek("SZ6a", "członek IT nadaje sobie dostęp w IAM ze zwykłego konta",
              "henryk", "W", "iam_przypisanie", "odmów", krok=6),
    Przypadek("SZ6b", "członek IT z konta administracyjnego bez aktywnej roli w sesji",
              "henryk-adm", "W", "iam_przypisanie", "odmów", krok=6),
    Przypadek("SZ6c", "członek IT z konta administracyjnego odczytuje dane kadrowe",
              "henryk-adm", "R", "kadry_anna", "odmów", krok=6),
    Przypadek("SZ7a", "programista zatwierdza własną zmianę w kodzie",
              "anna", "A", "mr_anny", "odmów", {"SO1"}, krok=3, sod=True),
    Przypadek("SZ7b", "programista zatwierdza własne wdrożenie na produkcję",
              "anna", "A", "wdrozenie_a1", "odmów", {"SO2"}, krok=3, sod=True),
    Przypadek("SZ8a", "stażysta usuwa repozytorium",
              "igor", "D", "repo_x", "odmów", krok=6),
    Przypadek("SZ8b", "stażysta zapisuje poza własną gałęzią",
              "igor", "W", "repo_x", "odmów", {"RC9"}, krok=2),
    Przypadek("SZ10", "account manager eksportuje pełne dane klienta prowadzonego przez innych",
              "kamil", "R", "crm_y", "odmów", {"RC3"}, krok=2),
    # --- uzupełnienia z 14.10.2026: WT7 i konto usługowe ---
    Przypadek("UP1", "account manager bez upoważnienia RODO otwiera kartę swojego klienta",
              "kamil", "R", "crm_x", "odmów", {"WT7"}, krok=1, przygotuj=_bez_upowaznienia_kamila),
    Przypadek("USL1", "potok CI/CD wdraża wydanie, którego nikt nie zatwierdził",
              "cicd-potok", "W", "wydanie_a1", "odmów", {"SO2"}, krok=3,
              srodowisko={"interaktywne": False}, sod=True),
    Przypadek("USL2", "ktoś loguje się interaktywnie na konto usługowe potoku",
              "cicd-potok", "R", "cicd_a1", "odmów", {"WF-13"}, krok=6),
]
# SZ9 (zaprzeczenie zmianie) dotyczy rozliczalności – jest osobnym testem dziennika.

# ---------------------------------------------------------------------------
# Zwykła praca – każda odmowa byłaby „nieuzasadniona” (metryka M6)
# ---------------------------------------------------------------------------
ZWYKLA_PRACA: list[Przypadek] = [
    Przypadek("ZP01", "programista czyta wiki", "anna", "R", "wiki", "zezwól", krok=4),
    Przypadek("ZP02", "programista czyta zadania zespołu", "anna", "R", "zadanie_a1", "zezwól", {"RC1"}, krok=4),
    Przypadek("ZP03", "programista czyta repozytorium projektu", "anna", "R", "repo_x", "zezwól", {"RC1", "WT1"}, krok=4),
    Przypadek("ZP04", "programista zapisuje w repozytorium projektu", "anna", "W", "repo_x", "zezwól", krok=4),
    Przypadek("ZP05", "programista składa wniosek w IAM", "anna", "W", "wniosek_anny", "zezwól", krok=4),
    Przypadek("ZP06", "inny programista zespołu zatwierdza zmianę", "piotr", "A", "mr_anny", "zezwól", {"SO1"}, krok=4),
    Przypadek("ZP07", "tester odbiera testy zmiany", "jola", "A", "odbior_testow", "zezwól", {"SO9"}, krok=4),
    Przypadek("ZP08", "PO zatwierdza wdrożenie", "olek", "A", "wdrozenie_a1", "zezwól", {"SO2"}, krok=4),
    Przypadek("ZP09", "stażysta zapisuje we własnej gałęzi", "igor", "W", "galaz_igora", "zezwól", krok=4),
    Przypadek("ZP10", "programista na dyżurze czyta infrastrukturę produkcji", "daria", "R", "prod_infra",
              "zezwól", {"RE1", "WT2"}, krok=5),
    Przypadek("ZP11", "programista na dyżurze modyfikuje infrastrukturę przez VPN", "daria", "M", "prod_infra",
              "zezwól", {"RE1"}, krok=5, srodowisko={"siec": Siec.VPN}),
    Przypadek("ZP12", "główna księgowa zatwierdza przelew do 50 000 zł", "felicja", "A", "przelew_maly",
              "zezwól", {"RC13", "SO3"}, krok=4),
    Przypadek("ZP13", "COO zatwierdza przelew powyżej 50 000 zł", "grzegorz", "A", "przelew_duzy",
              "zezwól", {"RC13", "SO3"}, krok=4),
    Przypadek("ZP14", "księgowy czyta przelew", "edward", "R", "przelew_maly", "zezwól", krok=4),
    Przypadek("ZP15", "account manager czyta kartę swojego klienta", "kamil", "R", "crm_x", "zezwól", {"RC3"}, krok=4),
    Przypadek("ZP16", "account manager aktualizuje kartę swojego klienta", "kamil", "M", "crm_x", "zezwól", krok=4),
    Przypadek("ZP17", "account manager czyta dane podstawowe innego klienta", "kamil", "R", "crm_y_podst",
              "zezwól", {"RC3"}, krok=4),
    Przypadek("ZP18", "specjalista kadr czyta dane kadrowe", "marta", "R", "kadry_anna", "zezwól", krok=4),
    Przypadek("ZP19", "specjalista kadr czyta dane o zdrowiu", "marta", "R", "zdrowie_anna", "zezwól", {"RC14"}, krok=4),
    Przypadek("ZP20", "kierownik HR zatwierdza listę płac", "natalia", "A", "lista_plac", "zezwól", {"RC13", "SO4"}, krok=4),
    Przypadek("ZP21", "analityk czyta widok raportowy", "tomasz", "R", "raport_sprzedazy", "zezwól", {"RC17"}, krok=4),
    Przypadek("ZP22", "potok CI/CD wdraża wydanie zatwierdzone przez PO", "cicd-potok", "W", "wydanie_a1",
              "zezwól", {"SO2"}, krok=4, przygotuj=_wdrozenie_zatwierdzone, srodowisko={"interaktywne": False}),
    Przypadek("ZP23", "account manager z ważnym upoważnieniem RODO czyta kartę klienta", "kamil", "R", "crm_x",
              "zezwól", {"WT7", "RC3"}, krok=4),
]

WSZYSTKIE = SCENARIUSZE_ZAGROZEN + ZWYKLA_PRACA
