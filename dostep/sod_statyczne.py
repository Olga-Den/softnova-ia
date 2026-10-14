"""Statyczny rozdział obowiązków (SS1–SS5, tabela 3.12) – sprawdzany przy przypisaniu roli."""
from __future__ import annotations

from dostep.model import FormaWspolpracy, Klasa, TypRoli, Uzytkownik
from dostep.polityka.role import ROLE
from dostep.polityka.zasoby import ZASOBY
from dostep.reguly import Ocena

# Pary ról funkcyjnych wykluczających się.
PARY_SS: dict[str, tuple[str, str, str]] = {
    "SS1": ("T11", "T10", "administrowanie systemami i audyt ich zabezpieczeń"),
    "SS2": ("B11", "B7", "przygotowanie listy płac i wykonanie przelewu wynagrodzeń"),
    "SS3": ("B4", "B7", "sprzedaż i fakturowanie tych samych klientów"),
    "SS4": ("T1", "T9", "wytwarzanie i administrowanie produkcją"),
}

ROLA_WLASCICIELA = "WLASCICIEL"


def _rodzina(id_roli: str) -> set[str]:
    """Role funkcyjne „reprezentowane” przez rolę – dla roli administratora: kto może ją uzyskać."""
    r = ROLE[id_roli]
    if r.typ is TypRoli.UPRZYWILEJOWANA:
        return set() if id_roli == "AWARYJNA_Z8" else set(r.kto_moze)  # rola awaryjna – jawny wyjątek
    return {id_roli}


def _konflikty_par(funkcyjna: str, nowa: str) -> list[Ocena]:
    wynik = []
    for ss, (a, b, uzasadnienie) in PARY_SS.items():
        for r in _rodzina(nowa) | ({nowa} if ROLE[nowa].typ is TypRoli.FUNKCYJNA else set()):
            if {funkcyjna, r} == {a, b}:
                wynik.append(Ocena(ss, False, f"role wykluczające się: {ROLE[a].nazwa} – {ROLE[b].nazwa} "
                                              f"({uzasadnienie})"))
    return wynik


def sprawdz_przypisanie_roli(u: Uzytkownik, id_roli: str) -> list[Ocena]:
    """Zwraca listę naruszeń (pusta = przypisanie dozwolone)."""
    r = ROLE[id_roli]
    naruszenia: list[Ocena] = []
    if r.typ is TypRoli.FUNKCYJNA:
        if u.rola_funkcyjna and u.rola_funkcyjna != id_roli:
            naruszenia.append(Ocena("WF-02", False, f"użytkownik ma już rolę funkcyjną {u.rola_funkcyjna} – "
                                                    "zmiana stanowiska odbiera poprzednią rolę"))
        naruszenia += _konflikty_par(u.rola_funkcyjna, id_roli)
    elif r.typ is TypRoli.UPRZYWILEJOWANA:
        naruszenia += _konflikty_par(u.rola_funkcyjna, id_roli)
        if u.rola_funkcyjna not in r.kto_moze:
            naruszenia.append(Ocena("WF-03", False, f"rolę {r.nazwa} mogą uzyskać tylko: "
                                                    f"{', '.join(ROLE[x].nazwa for x in r.kto_moze)}"))
        if r.zasob in u.wlasciciel_zasobow and ZASOBY[r.zasob].klasa is Klasa.KW4 and id_roli.startswith("ADM_"):
            naruszenia.append(Ocena("SS5", False, f"właściciel zasobu {r.zasob} (KW4) nie może być jego administratorem"))
    return naruszenia


def sprawdz_nadanie_wlasnosci(u: Uzytkownik, zasob: str) -> list[Ocena]:
    """Rola właściciela zasobu – tylko umowa o pracę, SS5 wobec administratora tego systemu KW4."""
    naruszenia = []
    if u.forma is not FormaWspolpracy.UMOWA_O_PRACE:
        naruszenia.append(Ocena("WF-03", False, "właścicielem zasobu może być tylko osoba na umowie o pracę"))
    if ZASOBY[zasob].klasa is Klasa.KW4 and f"ADM_{zasob}" in u.role_uprzywilejowane:
        naruszenia.append(Ocena("SS5", False, f"administrator {zasob} (KW4) nie może być jego właścicielem"))
    return naruszenia
