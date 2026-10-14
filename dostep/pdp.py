"""Punkt decyzyjny polityki (PDP) – podrozdział 3.5.6.

Kolejność wyznaczania decyzji („odmowa wygrywa”):
  1. Jeśli którykolwiek warunek twardy nie jest spełniony – odmów.
  2. Jeśli którakolwiek reguła zawężająca nie dopuszcza żądania – odmów.
  3. Jeśli operacja naruszałaby ograniczenie SO – odmów.
  4. Jeśli uprawnienie wynika z roli użytkownika (w tym z roli aktywnej w sesji) – zezwól.
  5. Jeśli reguła rozszerzająca przyznaje uprawnienie należące do katalogu roli – zezwól.
  6. W pozostałych przypadkach – odmów.

Uprawnienie może wynikać z kilku „ścieżek” (wpis macierzy dla roli bazowej,
funkcyjnej, dziedziczonej, rola w sesji, pozycja katalogu). Reguły przypisane
do wpisu zawężają tylko ten wpis; reguły ogólne (REGULY_OGOLNE) – każde żądanie.
Uzasadnienie zawiera wszystkie niespełnione reguły, nie tylko pierwszą (WN-02).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from dostep.model import Decyzja, Operacja, TypKonta, Wynik, Zadanie
from dostep.polityka.macierz import MACIERZ, POZIOM_P2_P3
from dostep.polityka.role import ROLE, role_efektywne
from dostep.polityka.zasoby import ZASOBY
from dostep.reguly import REGULY_OGOLNE, Kontekst, Ocena, ocen, sprawdz_so
from dostep.rejestr import Rejestr

KROK_WT, KROK_RC, KROK_SO, KROK_ROLA, KROK_RE, KROK_DOMYSLNA = 1, 2, 3, 4, 5, 6


@dataclass
class Sciezka:
    """Jedno możliwe źródło uprawnienia."""
    opis: str
    krok_zezwolenia: int                         # 4 – rola/sesja, 5 – katalog
    reguly: tuple[str, ...] = ()                 # reguły wpisu do sprawdzenia
    warunki: list[Ocena] = field(default_factory=list)  # warunek uruchomienia (RE, WT5/6, przydział)
    sygnaly: list[str] = field(default_factory=list)


def _sciezki(k: Kontekst, rejestr: Rejestr, sesja_id: str | None) -> list[Sciezka]:
    u, konto, o, op = k.uzytkownik, k.konto, k.obiekt, k.operacja
    wynik: list[Sciezka] = []

    # --- (a) role przypisane: tylko konto zwykłe (konto administracyjne nie ma roli bazowej) ---
    if konto.typ is TypKonta.ZWYKLE:
        role = role_efektywne(u.rola_funkcyjna)
        if u.poziom in ("P2", "P3"):
            role.append(POZIOM_P2_P3)
        for w in MACIERZ:
            if w.rola in role and w.zasob == o.zasob and w.obejmuje(op, o.typ_rekordu):
                if w.tylko_plemie and u.plemie != w.tylko_plemie:
                    continue
                opis = f"rola {w.rola} ({ROLE[w.rola].nazwa if w.rola in ROLE else 'poziom P2/P3'}): " \
                       f"{w.zasob} {_ops(w.operacje)}"
                wynik.append(Sciezka(opis, KROK_ROLA, w.reguly))

    # --- (b) role uprzywilejowane aktywne w sesji ---
    sesja = rejestr.sesja(sesja_id)
    if sesja and sesja.konto_id == konto.id:
        for id_roli, okres in sesja.aktywne_role.items():
            r = ROLE[id_roli]
            if not okres.zawiera(k.czas):
                continue
            if r.wymaga_zgloszenia and not sesja.numer_zgloszenia:
                continue
            for w in MACIERZ:
                if w.rola == id_roli and w.zasob == o.zasob and w.obejmuje(op, o.typ_rekordu):
                    s = Sciezka(f"rola {id_roli} aktywna w sesji {sesja.id} do {okres.do:%H:%M}",
                                KROK_ROLA, w.reguly)
                    if id_roli == "AWARYJNA_Z8":
                        s.sygnaly.append(f"ALARM: użycie roli awaryjnej Z8 (incydent "
                                         f"{sesja.numer_zgloszenia}) – powiadomić zespół "
                                         f"bezpieczeństwa i właściciela, przegląd w ciągu dnia roboczego")
                    wynik.append(s)

    # --- (c) katalog uprawnień wnioskowalnych (tylko konto zwykłe) ---
    if konto.typ is TypKonta.ZWYKLE:
        role = role_efektywne(u.rola_funkcyjna)
        for p in rejestr.katalog:
            if p.rola not in role or not p.obejmuje(o.zasob, op, o.typ_rekordu):
                continue
            s = Sciezka(f"katalog roli {p.rola}: {p.opis}", KROK_RE)
            if p.sposob in ("RE1", "RE2", "RE4", "WT5", "WT6"):
                s.warunki.append(ocen(p.sposob, k))
                if p.sposob == "RE4":
                    s.sygnaly.append("powiadomienie właściciela Z8: dostęp do danych klientów (RE4)")
            # Przydział z zaakceptowanego wniosku zastępuje regułę rozszerzającą.
            przydzial = next((pr for pr in u.przydzialy
                              if pr.zasob == o.zasob and op in pr.operacje
                              and (pr.typ_rekordu is None or pr.typ_rekordu == o.typ_rekordu)
                              and (pr.okres is None or pr.okres.zawiera(k.czas))), None)
            if przydzial:
                s.warunki = [Ocena("WF-15", True, f"uprawnienie nadane wnioskiem {przydzial.wniosek_id}"
                                   + (f" do {przydzial.okres.do:%Y-%m-%d %H:%M}" if przydzial.okres else ""))]
            elif p.sposob in ("wniosek", "sesja"):
                s.warunki.append(Ocena("WF-15", False, "uprawnienie wymaga zaakceptowanego wniosku"))
            wynik.append(s)

    # --- (d) konto usługowe: wyłącznie uprawnienia jego roli usługowej ---
    if konto.typ is TypKonta.USLUGOWE and konto.rola:
        for w in MACIERZ:
            if w.rola == konto.rola and w.zasob == o.zasob and w.obejmuje(op, o.typ_rekordu):
                wynik.append(Sciezka(f"konto usługowe {konto.id} – rola {konto.rola}: {w.zasob} "
                                     f"{_ops(w.operacje)}", KROK_ROLA, w.reguly))
    return wynik


def _ops(zbior) -> str:
    """Operacje w kolejności R W M D A."""
    return "".join(o.value for o in Operacja if o in zbior)


def _krok_dla(o: Ocena) -> int:
    return {"WT": KROK_WT, "RC": KROK_RC, "SO": KROK_SO, "WF": KROK_SO if o.regula == "WF-09" else KROK_DOMYSLNA}.get(
        o.rodzaj, KROK_DOMYSLNA)


def _odmowa(krok: int, niespelnione: list[Ocena], dodatkowe: list[str] | None = None,
            sygnaly: list[str] | None = None) -> Decyzja:
    uzasadnienie = [f"{o.regula}: {o.komentarz}" for o in niespelnione] + (dodatkowe or [])
    reguly = list(dict.fromkeys(o.regula for o in niespelnione))
    return Decyzja(Wynik.ODMOW, krok, uzasadnienie, reguly, sygnaly=sygnaly or [])


def decyduj(zadanie: Zadanie, rejestr: Rejestr, stosuj_abac: bool = True, stosuj_so: bool = True) -> Decyzja:
    """Wyznacza decyzję dla żądania.

    `stosuj_abac=False` pomija warunki twarde i reguły zawężające, a `stosuj_so=False` – ograniczenia SO.
    Oba przełączniki służą wyłącznie do policzenia metryki M10 (uprawnienia przy samych rolach).
    """
    konto = rejestr.konto(zadanie.konto_id)
    u = rejestr.uzytkownik(konto.uzytkownik_id)
    o = rejestr.obiekt(zadanie.obiekt_id)
    k = Kontekst(u, konto, o, ZASOBY[o.zasob], zadanie.operacja, zadanie.srodowisko,
                 rejestr.uzytkownik, rejestr.obiekt)

    if konto.typ is TypKonta.USLUGOWE and zadanie.srodowisko.interaktywne:
        return Decyzja(Wynik.ODMOW, KROK_DOMYSLNA,
                       ["konta usługowe nie służą do logowania interaktywnego (WF-13)"], ["WF-13"])

    # Reguły ogólne
    ogolne = [oc for r in REGULY_OGOLNE if (oc := ocen(r, k)) is not None] if stosuj_abac else []
    sciezki = _sciezki(k, rejestr, zadanie.sesja_id)

    # Ocena każdej ścieżki: reguły wpisu (bez powtarzania ogólnych) + warunki uruchomienia
    oceny_sciezek: list[tuple[Sciezka, list[Ocena]]] = []
    for s in sciezki:
        oc = [x for r in s.reguly if r not in REGULY_OGOLNE and (x := ocen(r, k)) is not None] \
            if stosuj_abac else []
        oc += s.warunki  # warunek uruchomienia ścieżki (RE, WT5/WT6, wniosek) obowiązuje zawsze
        oceny_sciezek.append((s, oc))

    nies_ogolne = [x for x in ogolne if not x.spelniona]
    dobre = [(s, oc) for s, oc in oceny_sciezek if all(x.spelniona for x in oc)]

    # Kroki 1–2: warunki twarde i reguły zawężające
    if nies_ogolne or not dobre:
        nies = nies_ogolne + [x for _, oc in oceny_sciezek for x in oc if not x.spelniona]
        nies = list({(x.regula, x.komentarz): x for x in nies}.values())
        so = [x for x in sprawdz_so(k) if not x.spelniona] if stosuj_abac and stosuj_so else []
        if not sciezki:
            if konto.typ is TypKonta.ADMINISTRACYJNE:
                dodatkowe = [f"konto administracyjne nie ma aktywnej w sesji roli uprawniającej do "
                             f"{zadanie.operacja.value} w {o.zasob} – domyślna odmowa"]
            else:
                dodatkowe = [f"brak uprawnienia {zadanie.operacja.value} do {o.zasob} w roli "
                             f"{u.rola_funkcyjna} ani w katalogu – domyślna odmowa"]
            krok = min([_krok_dla(x) for x in nies if x.rodzaj in ("WT", "RC")], default=KROK_DOMYSLNA)
            return _odmowa(krok, nies + so, dodatkowe, _sygnal_sod(so))
        krok = min([_krok_dla(x) for x in nies], default=KROK_DOMYSLNA)
        return _odmowa(krok, nies + so, sygnaly=_sygnal_sod(so))

    # Krok 3: SoD na poziomie obiektu
    if stosuj_abac and stosuj_so:
        so = sprawdz_so(k)
        nies_so = [x for x in so if not x.spelniona]
        if nies_so:
            return _odmowa(KROK_SO, nies_so, sygnaly=_sygnal_sod(nies_so))
    else:
        so = []

    # Kroki 4–5: zezwolenie – preferujemy rolę przed katalogiem
    s, oc = min(dobre, key=lambda p: p[0].krok_zezwolenia)
    spelnione = [x for x in ogolne + oc + so if x.spelniona]
    uzasadnienie = [f"uprawnienie: {s.opis}"] + [f"{x.regula}: {x.komentarz}" for x in spelnione]
    return Decyzja(Wynik.ZEZWOL, s.krok_zezwolenia, uzasadnienie,
                   list(dict.fromkeys(x.regula for x in spelnione)), zrodlo=s.opis, sygnaly=s.sygnaly)


def _sygnal_sod(niespelnione_so: list[Ocena]) -> list[str]:
    if not niespelnione_so:
        return []
    return ["próba naruszenia rozdziału obowiązków: " + ", ".join(dict.fromkeys(x.regula for x in niespelnione_so))]
