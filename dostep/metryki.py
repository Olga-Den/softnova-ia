"""Metryki oceny modelu M1–M10 (tabela 3.20) – pomiar do rozdziału 5.

Uruchomienie:
    python -m dostep metryki                 wyniki na ekranie + pliki w folderze „wyniki”
    python -m dostep metryki --bez-api       bez pomiaru czasu przez API (gdy nie zainstalowano FastAPI)
Pliki: metryki.md (tabele i metodyka do rozdz. 5), metryki.csv oraz szczegóły (m2_proby.csv, m7_czasy.csv, m10_role.csv).

Wszystkie pomiary są deterministyczne (stałe ziarno, stały zegar), poza czasami (M7), które zależą od komputera.
"""
from __future__ import annotations

import copy
import random
import statistics
import time
from dataclasses import dataclass, field
from datetime import timedelta

from dostep.model import Konto, Okres, Operacja, Przydzial, Srodowisko, TypKonta, Uzytkownik, Zadanie, operacje
from dostep.organizacja import DATA_GENERACJI as T, generuj_organizacje
from dostep.pdp import decyduj
from dostep.polityka.katalog import KATALOG
from dostep.polityka.macierz import MACIERZ
from dostep.polityka.role import ROLE, role_efektywne
from dostep.polityka.zakres import role_przypisane
from dostep.przyklad import Przyklad
from dostep.rejestr import Rejestr
from dostep.scenariusze import WSZYSTKIE, ZWYKLA_PRACA
from dostep.sod_statyczne import sprawdz_przypisanie_roli
from dostep.stan_przed import statystyki
from dostep.system import SystemDostepu

GODZ, DZIEN = timedelta(hours=1), timedelta(days=1)


@dataclass
class WynikMetryki:
    id: str
    nazwa: str
    wynik: str
    oczekiwane: str
    spelnione: bool | None
    metodyka: str
    szczegoly: list[list] = field(default_factory=list)       # wiersze tabeli szczegółów
    naglowek: list[str] = field(default_factory=list)
    uwagi: list[str] = field(default_factory=list)


def _proc(x: float) -> str:
    return f"{100 * x:.1f}%".replace(".", ",")


def _l(x: float, miejsca: int = 2) -> str:
    return f"{x:.{miejsca}f}".replace(".", ",")


def _efektywne(r: Rejestr, konto: str, czas, **flagi) -> set[tuple[str, str]]:
    """Zbiór par (obiekt, operacja), na które PDP zezwala – urządzenie firmowe, biuro."""
    wynik = set()
    for o in r.obiekty:
        for op in Operacja:
            if decyduj(Zadanie(konto, op, o, Srodowisko(czas)), r, **flagi).zezwolono:
                wynik.add((o, op.value))
    return wynik


# ===========================================================================
# M1 – poprawność decyzji
# ===========================================================================
def m1() -> WynikMetryki:
    wiersze, zgodne, razem = [], 0, 0
    for p in WSZYSTKIE:
        org = Przyklad()
        if p.przygotuj:
            p.przygotuj(org)
        d = org.pdp(p.konto, p.operacja, p.obiekt, **p.srodowisko)
        ok = d.wynik.value == p.oczekiwany and p.reguly <= set(d.reguly)
        zgodne += ok
        razem += 1
        reguly = ", ".join(d.reguly) or ("– (domyślna odmowa: brak uprawnienia w roli i katalogu)" if d.krok == 6 else "–")
        wiersze.append([p.id, p.opis, p.oczekiwany, f"{d.wynik.value} (krok {d.krok})", reguly, "tak" if ok else "NIE"])

    # Uogólnienie SZ1 na pełną organizację: każdy członek zespołu plemienia A × repozytorium każdego klienta
    r = generuj_organizacje()
    zg_sz1, n_sz1 = 0, 0
    for u in r.uzytkownicy.values():
        if u.plemie == "A" and u.zespol and u.rola_funkcyjna in ("T1", "T2", "T3", "T4", "T5"):
            for z in [f"A{i}" for i in range(1, 8)]:
                d = decyduj(Zadanie(u.id, Operacja.R, f"repo_{z}", Srodowisko(T)), r)
                zg_sz1 += d.zezwolono == (z == u.zespol)
                n_sz1 += 1
    wiersze.append(["SZ1-uog.", f"pełna organizacja: {n_sz1 // 7} członków zespołów plemienia A × 7 repozytoriów",
                    "zezwól tylko dla własnego zespołu", f"zgodnych {zg_sz1}/{n_sz1}", "WT1, RC1",
                    "tak" if zg_sz1 == n_sz1 else "NIE"])
    zgodne += zg_sz1
    razem += n_sz1
    return WynikMetryki(
        "M1", "poprawność decyzji", f"{_proc(zgodne / razem)} ({zgodne}/{razem})", "100%", zgodne == razem,
        "Odsetek decyzji PDP zgodnych z oczekiwanymi: (a) scenariusze zagrożeń SZ1–SZ10 i uzupełnienia (UP1, USL1, "
        "USL2) – oczekiwana odmowa, (b) scenariusze zwykłej pracy ZP01–ZP23 – oczekiwane zezwolenie, (c) uogólnienie "
        "SZ1 na pełną organizację. Decyzja jest zgodna, gdy zgadza się wynik i w uzasadnieniu występują oczekiwane "
        "reguły. Każdy scenariusz działa na świeżej kopii przykładowej organizacji.",
        wiersze, ["ID", "scenariusz", "oczekiwane", "wynik PDP", "reguły w uzasadnieniu", "zgodne"])


# ===========================================================================
# M2 – skuteczność SoD
# ===========================================================================
def m2() -> WynikMetryki:
    proby: list[list] = []     # [rodzaj, ograniczenie, opis, zablokowana]

    # (a) SO w PDP – scenariusze oznaczone jako próby naruszenia SoD
    for p in WSZYSTKIE:
        if p.sod:
            org = Przyklad()
            if p.przygotuj:
                p.przygotuj(org)
            d = org.pdp(p.konto, p.operacja, p.obiekt, **p.srodowisko)
            so = [x for x in d.reguly if x.startswith("SO")]
            proby.append(["SO (decyzja)", ", ".join(so) or "–", f"{p.id}: {p.opis}", not d.zezwolono and bool(so)])
    org = Przyklad()
    d = org.pdp("jola", "A", "mr_anny")
    proby.append(["SO (decyzja)", "SO1", "tester zatwierdza zmianę w kodzie", not d.zezwolono and "SO1" in d.reguly])
    d = org.pdp("edward", "A", "przelew_maly")
    proby.append(["SO (decyzja)", "SO3", "księgowy zatwierdza własny przelew", not d.zezwolono and "SO3" in d.reguly])

    # (b) SO6 i SO8 w procesach
    s = org.system
    wn = s.wnioski.zloz("anna", "Z9", "R", T, "sekret_projektu").dane
    r1 = s.wnioski.akceptuj(wn.id, "anna", T)
    proby.append(["SO (proces)", "SO6", "akceptacja własnego wniosku", not r1.ok and "SO6" in r1.reguly])
    s.wnioski.akceptuj(wn.id, "piotr", T)
    r2 = s.wnioski.akceptuj(wn.id, "piotr", T)
    proby.append(["SO (proces)", "SO6", "druga akceptacja tej samej osoby (KW4 – dwie osoby)", not r2.ok and "SO6" in r2.reguly])
    r3 = s.wnioski.zloz("bartek", "Z9", "R", T, "sekret_projektu", beneficjent_id="anna")
    proby.append(["SO (proces)", "SO6", "wniosek za osobę, której nie jest się przełożonym", not r3.ok and "SO6" in r3.reguly])
    from dostep.polityka.katalog import PozycjaKatalogu
    poz = PozycjaKatalogu("T12", "Z10", operacje("R"), "wniosek", "dane_kontaktowe", "test")
    zm = s.wnioski.zaproponuj_zmiane_katalogu("wanda", poz, "dodaj", T).dane
    r4 = s.wnioski.zatwierdz_zmiane_katalogu(zm, "wanda", T)
    proby.append(["SO (proces)", "SO8", "autor zatwierdza własną zmianę katalogu", not r4.ok and "SO8" in r4.reguly])
    r5 = s.sesje.przypisz_role("sylwia", "ADM_Z9", "sylwia", T)
    proby.append(["SO (proces)", "SO6", "nadanie roli uprzywilejowanej samemu sobie", not r5.ok and "SO6" in r5.reguly])

    # (c) SS – próby przypisania ról wykluczających się w pełnej organizacji
    rp = generuj_organizacje()
    U = list(rp.uzytkownicy.values())

    def ss(uzytkownicy, rola, regula, opis):
        for u in uzytkownicy:
            n = {x.regula for x in sprawdz_przypisanie_roli(u, rola)}
            proby.append(["SS (przypisanie)", regula, f"{opis}: {u.id}", regula in n])

    ss([u for u in U if u.rola_funkcyjna == "T11"], "ADM_Z16", "SS1", "administrator IT → administrator SIEM")
    ss([u for u in U if u.rola_funkcyjna == "T10"], "ADM_Z10", "SS1", "specjalista bezpieczeństwa → administrator CRM")
    ss([u for u in U if u.rola_funkcyjna == "B11"], "B7", "SS2", "specjalista kadr i płac → księgowy")
    ss([u for u in U if u.rola_funkcyjna == "B4"], "B7", "SS3", "account manager → księgowy")
    ss([u for u in U if u.rola_funkcyjna == "T1"], "ADM_Z8", "SS4", "programista → administrator produkcji")
    ss([u for u in U if "Z8" in u.wlasciciel_zasobow], "ADM_Z8", "SS5", "właściciel Z8 → administrator Z8")
    ss([u for u in U if "Z17" in u.wlasciciel_zasobow], "ADM_Z17", "SS5", "właściciel Z17 → administrator Z17")

    zabl = sum(1 for x in proby if x[3])
    grupy = {}
    for rodzaj, regula, _, ok in proby:
        g = grupy.setdefault((rodzaj, regula), [0, 0])
        g[0] += ok
        g[1] += 1
    wiersze = [[rodzaj, regula, f"{z}/{n}"] for (rodzaj, regula), (z, n) in sorted(grupy.items())]
    w = WynikMetryki(
        "M2", "skuteczność SoD", f"{_proc(zabl / len(proby))} ({zabl}/{len(proby)})", "100%", zabl == len(proby),
        "Stosunek zablokowanych prób naruszenia rozdziału obowiązków do wszystkich prób wprowadzonych w testach: "
        "(a) SO przy decyzji PDP (zatwierdzenie własnej operacji, zatwierdzenie przez niewłaściwą rolę, wdrożenie "
        "bez zatwierdzenia), (b) SO6 i SO8 w procesach wniosków, ról uprzywilejowanych i katalogu, (c) SS przy "
        "przypisaniu ról – próba wykonana dla każdej osoby z rolą objętą ograniczeniem w pełnej organizacji. "
        "Próba jest zablokowana, gdy operacja została odrzucona z powodu właściwego ograniczenia.",
        wiersze, ["rodzaj", "ograniczenie", "zablokowane / próby"])
    w.dane_proby = proby
    return w


# ===========================================================================
# M3 – uprawnienia nadmiarowe po zdarzeniach kadrowych
# ===========================================================================
def _klon(r: Rejestr, u: Uzytkownik) -> str:
    """Osoba o tych samych bieżących atrybutach, ale bez historii (nowo zatrudniona na obecne stanowisko)."""
    k = copy.deepcopy(u)
    k.id = f"klon-{u.id}"
    k.poprzedni_zespol, k.data_przeniesienia, k.przydzialy, k.zastepstwa = None, None, [], []
    k.role_uprzywilejowane = {x for x in u.role_uprzywilejowane if u.rola_funkcyjna in ROLE[x].kto_moze}
    r.dodaj(k, Konto(k.id, k.id))
    return k.id


def m3() -> WynikMetryki:
    s = SystemDostepu(generuj_organizacje())
    r, k = s.rejestr, s.kadry
    U = list(r.uzytkownicy.values())

    uzyci: set[str] = set()

    def pierwsi(warunek, ile):
        """Pierwsze osoby spełniające warunek – każda osoba bierze udział w jednym zdarzeniu."""
        wybrani = [u for u in U if warunek(u) and u.id not in uzyci][:ile]
        uzyci.update(u.id for u in wybrani)
        return wybrani

    zdarzenia: list[tuple[str, str]] = []
    przed: dict[str, set] = {}

    def zapamietaj(u):
        przed.setdefault(u.id, _efektywne(r, u.id, T))

    # 1. przeniesienia w plemieniu A (dwie osoby mają wcześniej nadane sekrety projektu – mają je stracić),
    #    z B do A (dyżurni), testerzy z A do B
    przenoszeni = pierwsi(lambda u: u.rola_funkcyjna == "T1" and u.plemie == "A" and u.poziom == "P4", 4)
    for u in przenoszeni[:2]:
        u.przydzialy.append(Przydzial("Z9", operacje("R"), "sekret_projektu", Okres(T - 10 * DZIEN, T + 80 * DZIEN), "WN-0"))
    for u in przenoszeni:
        zapamietaj(u)
        nowy = f"A{int(u.zespol[1]) % 7 + 1}"
        k.przenies(u.id, nowy, T)
        k.zloz_oswiadczenie_nda(u.id, {f"A{i}": n for i, n in enumerate(
            ["EnergoPol", "MedTech Polska", "BankoNet", "LogiTrans", "AgroDane", "RetailPlus", "UbezPro"], 1)}[nowy], T)
        zdarzenia.append(("przeniesienie A→A", u.id))
    for u in pierwsi(lambda u: u.rola_funkcyjna == "T1" and u.plemie == "B" and u.dyzury, 2):
        zapamietaj(u)
        k.przenies(u.id, "A1", T, plemie="A", jednostka="Plemię A")
        k.zloz_oswiadczenie_nda(u.id, "EnergoPol", T)
        zdarzenia.append(("przeniesienie B→A (dyżurny)", u.id))
    for u in pierwsi(lambda u: u.rola_funkcyjna == "T3" and u.plemie == "A", 2):
        zapamietaj(u)
        k.przenies(u.id, "B2", T, plemie="B", jednostka="Plemię B")
        zdarzenia.append(("przeniesienie A→B", u.id))
    # 2. zmiany stanowiska
    for u, nowa in [(pierwsi(lambda u: u.rola_funkcyjna == "T9" and u.poziom == "P4", 1)[0], "T1"),
                    (pierwsi(lambda u: u.rola_funkcyjna == "T1" and u.plemie == "B" and u.poziom == "P4"
                             and not u.dyzury, 1)[0], "T5"),
                    (pierwsi(lambda u: u.rola_funkcyjna == "T11" and u.role_uprzywilejowane, 2)[1], "T12")]:
        zapamietaj(u)
        k.zmien_stanowisko(u.id, nowa, T)
        zdarzenia.append((f"zmiana stanowiska → {nowa}", u.id))
    # 3. czasowe przeniesienie i jego koniec
    for u in pierwsi(lambda u: u.rola_funkcyjna == "T1" and u.plemie == "A" and u.zespol == "A5", 2):
        zapamietaj(u)
        k.przenies_czasowo(u.id, "A6", T)
        k.zakoncz_przeniesienie_czasowe(u.id, T + 7 * DZIEN)
        zdarzenia.append(("czasowe przeniesienie A5→A6 i powrót", u.id))
    # 4. odejścia (w tym administrator)
    odchodzacy = (pierwsi(lambda u: u.rola_funkcyjna == "T1" and u.poziom == "P4", 1)
                  + pierwsi(lambda u: u.rola_funkcyjna == "B4" and u.poziom == "P4", 1)
                  + pierwsi(lambda u: u.rola_funkcyjna == "T11" and "ADM_Z13" in u.role_uprzywilejowane, 1)
                  + pierwsi(lambda u: u.rola_funkcyjna == "T9" and u.forma.value == "umowa o pracę" and u.poziom == "P4", 1))
    for u in odchodzacy:
        zapamietaj(u)
        k.odejscie(u.id, T)
        zdarzenia.append(("odejście", u.id))
    # 5. koniec kontraktu B2B (zadanie codzienne)
    b2b = pierwsi(lambda u: u.forma.value == "B2B" and u.aktywny, 1)[0]
    zapamietaj(b2b)
    b2b.data_konca_umowy = (T + 5 * DZIEN).date()
    zdarzenia.append(("koniec kontraktu B2B", b2b.id))

    po = T + 15 * DZIEN            # po upływie okresu RC12 (14 dni)
    s.przetworz_terminy(po)

    wiersze, nadmiar, odebrane = [], 0, 0
    for rodzaj, uid in zdarzenia:
        u = r.uzytkownik(uid)
        teraz = _efektywne(r, uid, po)
        if u.aktywny:
            kid = _klon(r, u)
            wzor = _efektywne(r, kid, po)
            del r.uzytkownicy[kid], r.konta[kid]
        else:
            wzor = set()
        n = len(teraz - wzor)
        nadmiar += n
        odebrane += len(przed[uid] - teraz)
        wiersze.append([rodzaj, uid, len(przed[uid]), len(teraz), len(przed[uid] - teraz), n])
    return WynikMetryki(
        "M3", "uprawnienia nadmiarowe", str(nadmiar), "0", nadmiar == 0,
        f"Pełna organizacja; {len(zdarzenia)} zdarzeń kadrowych (przeniesienia, w tym dyżurnych i osób z przydziałami "
        "z wniosków, zmiany stanowiska, w tym administratorów, czasowe przeniesienia, odejścia, koniec kontraktu B2B). "
        "Po 15 dniach (po okresie RC12) i wykonaniu zadań codziennych dla każdej osoby porównano efektywne uprawnienia "
        "(pary obiekt–operacja, na które PDP zezwala) z uprawnieniami osoby o tych samych bieżących atrybutach, lecz "
        "bez historii. Nadmiar = uprawnienia, których taka osoba by nie miała; dla osób odchodzących – każde uprawnienie.",
        wiersze, ["zdarzenie", "osoba", "uprawnienia przed zdarzeniem", "po 15 dniach", "odebrane", "nadmiarowe"],
        [f"Model odebrał automatycznie {odebrane} uprawnień (pary obiekt–operacja) bez udziału administratora."])


# ===========================================================================
# M4, M5 – administrowalność
# ===========================================================================
def m4_m5() -> tuple[WynikMetryki, WynikMetryki]:
    s = statystyki(generuj_organizacje())
    w4 = WynikMetryki(
        "M4", "stosunek ról do użytkowników", f"1 : {_l(s['m4'])} ({s['role']} ról / {s['uzytkownicy']} osób)",
        "ok. 1 : 7,7", 7.5 <= s["m4"] <= 7.9,
        "Liczba ról organizacyjnych (rola bazowa + 25 ról funkcyjnych z tabeli 3.8) do liczby aktywnych użytkowników "
        "pełnej organizacji. Role administratorów, rola awaryjna i rola konta usługowego nie są rolami organizacyjnymi.")
    wiersze = [[x["rola"], x["nazwa"], x["uzytkownicy"], x["pa_po"], _l(x["przed_srednio"], 1),
                _l(x["nie_z_roli_srednio"], 1)] for x in s["na_role"]]
    w5 = WynikMetryki(
        "M5", "liczba przypisań", f"{_l(s['m5'], 3)} (({s['ua']} UA + {s['pa']} PA) / {s['przed']})", "< 1",
        s["m5"] < 1,
        "Σ(|Uᵢ| + |Pᵢ|) / Σ|Uᵢ|·|Pᵢ| [5, s. 19–20]. Licznik: przypisania w modelu – użytkownik–rola (rola bazowa, "
        "funkcyjna, role uprzywilejowane, konto usługowe) i rola–uprawnienie (pary zasób–operacja w macierzy). "
        "Mianownik: bezpośrednie przypisania (użytkownik, zasób–operacja) w stanie „przed”, odtworzonym z opisu "
        "w podrozdziale 3.2 (funkcja + nadmiar ze słabości S3, S7, S8, S12).",
        wiersze, ["rola", "nazwa", "osób", "uprawnienia roli (PA)", "śr. przypisań „przed”", "śr. stałych, nie z roli"],
        [f"Możliwych par (użytkownik, uprawnienie): {s['mozliwe_pary']}; przypisań „przed”: {s['przed']} "
         f"(funkcja {s['przyczyny_przed'].get('funkcja', 0)}, S8 {s['przyczyny_przed'].get('S8', 0)}, "
         f"S12 {s['przyczyny_przed'].get('S12', 0)}, S7 {s['przyczyny_przed'].get('S7', 0)}).",
         f"Uprawnienia stałe „przed”, które w modelu nie wynikają z roli (są tylko czasowe albo wcale): "
         f"{s['stale_nie_z_roli']}, w tym ponad maksimum modelu: {s['ponad_maksimum']}."])
    return w4, w5


# ===========================================================================
# M6 – nieuzasadnione odmowy
# ===========================================================================
def m6() -> WynikMetryki:
    odmowy, razem, wiersze = [], 0, []
    for p in ZWYKLA_PRACA:
        org = Przyklad()
        if p.przygotuj:
            p.przygotuj(org)
        d = org.pdp(p.konto, p.operacja, p.obiekt, **p.srodowisko)
        razem += 1
        if not d.zezwolono:
            odmowy.append(f"{p.id}: {'; '.join(d.uzasadnienie)}")
    wiersze.append(["scenariusze zwykłej pracy ZP01–ZP23 (przykładowa organizacja)", razem, len(odmowy)])

    r = generuj_organizacje()
    klient_zespolu = {o.zespol: o.id for o in r.obiekty.values() if o.zasob == "Z4"}
    karta_klienta = {o.klient: o.id for o in r.obiekty.values() if o.zasob == "Z10" and o.klient and not o.typ_rekordu}

    def sprawdz(opis, zadania):
        nonlocal razem
        n_odm = 0
        for konto, op, obiekt in zadania:
            d = decyduj(Zadanie(konto, Operacja(op), obiekt, Srodowisko(T)), r)
            razem += 1
            if not d.zezwolono:
                n_odm += 1
                odmowy.append(f"{konto} {op} {obiekt}: {'; '.join(d.uzasadnienie)}")
        wiersze.append([opis, len(zadania), n_odm])

    U = [u for u in r.uzytkownicy.values() if u.aktywny]
    sprawdz("każda osoba czyta intranet (Z2)", [(u.id, "R", "wiki") for u in U])
    sprawdz("członkowie zespołów A czytają repozytorium swojego projektu",
            [(u.id, "R", klient_zespolu[u.zespol]) for u in U if u.plemie == "A" and u.zespol in klient_zespolu
             and u.rola_funkcyjna in ("T1", "T2", "T3", "T4", "T5")])
    sprawdz("programiści A zapisują w repozytorium swojego projektu",
            [(u.id, "W", klient_zespolu[u.zespol]) for u in U if u.rola_funkcyjna == "T1" and u.zespol in klient_zespolu])
    sprawdz("programiści i testerzy B czytają moduł produktu SaaS (Z5)",
            [(u.id, "R", f"modul_{u.zespol}") for u in U if u.plemie == "B" and u.rola_funkcyjna in ("T1", "T3")])
    sprawdz("członkowie zespołów pracują z zadaniami własnego zespołu (Z3)",
            [(u.id, op, f"zadania_{u.zespol}") for u in U if u.zespol and f"zadania_{u.zespol}" in r.obiekty
             for op in "RWM"])
    sprawdz("account managerowie czytają karty przypisanych klientów (Z10)",
            [(u.id, "R", karta_klienta[c]) for u in U if u.rola_funkcyjna == "B4" for c in sorted(u.przypisani_klienci)])
    sprawdz("analitycy czytają widoki raportowe", [(u.id, "R", "crm_raport") for u in U if u.rola_funkcyjna == "T12"])
    sprawdz("księgowi czytają przelewy (Z12)", [(u.id, "R", "przelew_dostawca") for u in U if u.rola_funkcyjna == "B7"])
    sprawdz("programista plemienia B na dyżurze czyta infrastrukturę produkcji (RE1)",
            [(u.id, "R", "prod_infra") for u in U if u.rola_funkcyjna == "T1" and any(d.zawiera(T) for d in u.dyzury)])
    # DevOps/SRE nie ma stałego dostępu do produkcji – w zwykłej pracy aktywuje rolę administratora w sesji (tab. 3.11)
    s = SystemDostepu(r)
    devops = [u for u in U if u.rola_funkcyjna == "T9" and "ADM_Z8" in u.role_uprzywilejowane]
    n_odm = 0
    for u in devops:
        sesja = s.sesje.aktywuj(f"{u.id}-adm", "ADM_Z8", T).dane
        for op in "RM":
            d = decyduj(Zadanie(f"{u.id}-adm", Operacja(op), "prod_infra", Srodowisko(T), sesja), r)
            razem += 1
            if not d.zezwolono:
                n_odm += 1
                odmowy.append(f"{u.id}-adm {op} prod_infra: {'; '.join(d.uzasadnienie)}")
    wiersze.append(["DevOps/SRE aktywuje administratora Z8 w sesji i pracuje na produkcji (R, M)", 2 * len(devops), n_odm])
    w = WynikMetryki(
        "M6", "nieuzasadnione odmowy", str(len(odmowy)), "0", not odmowy,
        "Liczba odmów w scenariuszach zwykłej pracy, w których dostęp wynika z obowiązków: scenariusze ZP01–ZP23 oraz "
        "typowe czynności każdej osoby w pełnej organizacji (urządzenie firmowe, sieć biurowa, dzień roboczy 10:00). "
        "Czynności wymagające uprawnień uprzywilejowanych wykonywano tak, jak przewiduje model – po aktywacji roli "
        "w sesji (DevOps/SRE na produkcji); odmowa bez sesji jest zamierzona (brak stałego dostępu uprzywilejowanego).",
        wiersze, ["czynność", "żądań", "odmów"], odmowy[:10])
    w.razem = razem
    return w


# ===========================================================================
# M7 – czas decyzji
# ===========================================================================
def m7(proby: int = 10_000, api: bool = True, baza_api: str | None = None) -> WynikMetryki:
    r = generuj_organizacje()
    los = random.Random(7)
    konta = [k.id for k in r.konta.values() if k.typ is TypKonta.ZWYKLE]
    obiekty = list(r.obiekty)
    for _ in range(200):                                   # rozgrzewka (pierwsze wywołania)
        decyduj(Zadanie(los.choice(konta), Operacja.R, los.choice(obiekty), Srodowisko(T)), r)
    czasy = []
    for _ in range(proby):
        z = Zadanie(los.choice(konta), los.choice(list(Operacja)), los.choice(obiekty), Srodowisko(T))
        t0 = time.perf_counter_ns()
        decyduj(z, r)
        czasy.append((time.perf_counter_ns() - t0) / 1e6)
    pdp = _statystyki_czasu(czasy)
    wiersze = [["PDP (bez bazy danych)", proby, *[_l(pdp[k], 3) for k in ("srednia", "mediana", "p95", "p99", "maks")], "< 10"]]
    uwagi = []
    wynik_api = None
    if api:
        try:
            from aplikacja.pomiar_api import zmierz_api
            wynik_api = zmierz_api(url=baza_api)
            wiersze.append([f"pełne żądanie przez API ({wynik_api['baza']})", wynik_api["proby"],
                            *[_l(wynik_api[k], 3) for k in ("srednia", "mediana", "p95", "p99", "maks")], "< 100"])
        except (ImportError, RuntimeError):
            uwagi.append("Pomiar API pominięty – brak bibliotek aplikacji (pip install -r requirements.txt).")
    spelnione = pdp["p95"] < 10 and (wynik_api is None or wynik_api["p95"] < 100)
    w = WynikMetryki(
        "M7", "czas decyzji (95. percentyl)",
        f"PDP {_l(pdp['p95'], 3)} ms" + (f"; API {_l(wynik_api['p95'], 2)} ms" if wynik_api else ""),
        "< 10 ms (PDP); < 100 ms (API)", spelnione,
        f"PDP: {proby} losowych żądań (stałe ziarno) na pełnej organizacji – losowe konto zwykłe, obiekt i operacja; "
        "200 wywołań rozgrzewających pominięto. API: kolejne żądania POST /api/decyzja przez warstwę FastAPI "
        "z zapisem decyzji w dzienniku w bazie danych. Czas mierzony zegarem wysokiej rozdzielczości (perf_counter). "
        "Wynik zależy od komputera – podać jego parametry w rozdziale 5.",
        wiersze, ["pomiar", "żądań", "średnia [ms]", "mediana [ms]", "p95 [ms]", "p99 [ms]", "maks. [ms]", "próg p95 [ms]"],
        uwagi)
    w.czasy_pdp = czasy
    return w


def _statystyki_czasu(czasy: list[float]) -> dict:
    c = sorted(czasy)
    return dict(srednia=statistics.mean(c), mediana=statistics.median(c), p95=c[int(0.95 * len(c))],
                p99=c[int(0.99 * len(c))], maks=c[-1])


# ===========================================================================
# M8 – automatyzacja nadawania
# ===========================================================================
def m8() -> WynikMetryki:
    from dostep.stan_przed import uprawnienia_przed
    r = generuj_organizacje()
    U = [u for u in r.uzytkownicy.values() if u.aktywny]
    auto, warunkowe, sesja, wniosek = 0, 0, 0, 0
    wnioski_na_osobe = []
    wiersze = []
    for u in U:
        z_roli = {(w.zasob, op.value) for w in MACIERZ if w.rola in role_przypisane(u)
                  and (not w.tylko_plemie or w.tylko_plemie == u.plemie) for op in w.operacje}
        role = role_efektywne(u.rola_funkcyjna)
        kat_auto = {(p.zasob, op.value) for p in KATALOG if p.rola in role and p.sposob != "wniosek"
                    for op in p.operacje} - z_roli
        kat_wniosek = {(p.zasob, op.value) for p in KATALOG if p.rola in role and p.sposob == "wniosek"
                       for op in p.operacje} - z_roli - kat_auto
        uprz = set()
        for x in u.role_uprzywilejowane:
            uprz |= {(w.zasob, op.value) for w in MACIERZ if w.rola == x for op in w.operacje}
        uprz -= z_roli | kat_auto
        auto += len(z_roli)
        warunkowe += len(kat_auto)
        sesja += len(uprz)
        wniosek += len(kat_wniosek)
        wnioski_na_osobe.append(len({(p.zasob, p.typ_rekordu) for p in KATALOG if p.rola in role and p.sposob == "wniosek"}))
    razem = auto + warunkowe + sesja + wniosek
    przed = sum(len(uprawnienia_przed(u)) for u in U)
    wiersze = [
        ["z roli – w chwili zatrudnienia, z danych kadrowych", auto, _proc(auto / razem)],
        ["automatycznie przy spełnieniu warunku (dyżur, incydent, sprawa IOD – RE, WT5, WT6)", warunkowe, _proc(warunkowe / razem)],
        ["przez aktywację roli uprzywilejowanej w sesji", sesja, _proc(sesja / razem)],
        ["tylko na wniosek (katalog, akceptacja wg tab. 3.9)", wniosek, _proc(wniosek / razem)],
        ["razem – maksymalny zakres modelu (pary zasób–operacja)", razem, "100%"],
    ]
    bez_wniosku = (auto + warunkowe + sesja) / razem
    sr = statistics.mean(wnioski_na_osobe)
    return WynikMetryki(
        "M8", "automatyzacja nadawania",
        f"{_proc(bez_wniosku)} uprawnień bez wniosku; śr. {_l(sr)} wniosku na osobę (maks.)",
        "wysoki / niska", bez_wniosku > 0.9,
        "Dla każdej osoby pełnej organizacji maksymalny zakres modelu (pary zasób–operacja) podzielono według sposobu "
        "uzyskania: z roli (automatycznie przy zatrudnieniu), automatycznie warunkowo (reguły RE i warunki WT5/WT6), "
        "przez aktywację w sesji, tylko na wniosek. Liczba wniosków na osobę = liczba pozycji katalogu z trybem "
        "„wniosek” dostępnych dla roli – górna granica wniosków potrzebnych do pełnego zakresu. Dla porównania: "
        f"w stanie „przed” każde z {przed} bezpośrednich przypisań wymagało zgłoszenia "
        f"(śr. {_l(przed / len(U), 1)} na osobę).",
        wiersze, ["sposób uzyskania", "pary zasób–operacja", "udział"],
        [f"Stan „przed”: {przed} przypisań nadawanych ręcznie na zgłoszenie = {_l(przed / len(U), 1)} na osobę; "
         f"model: maks. {_l(sr)} wniosku na osobę, reszta automatycznie."])


# ===========================================================================
# M9 – kompletność dziennika
# ===========================================================================
def _migawka(s: SystemDostepu):
    r = s.rejestr
    return (
        tuple(sorted((u.id, u.rola_funkcyjna, u.poziom, u.aktywny, u.zespol, u.zespol_tymczasowy,
                      tuple(sorted(u.role_uprzywilejowane)), tuple(sorted(u.wlasciciel_zasobow)),
                      tuple(sorted((p.klucz(), str(p.okres.do) if p.okres else "", p.awaryjny) for p in u.przydzialy)),
                      (tuple(sorted(u.upowaznienie.zakres)), str(u.upowaznienie.odwolane_o)) if u.upowaznienie else None,
                      tuple(sorted(u.oswiadczenia_nda)), len(u.dyzury), len(u.zastepstwa))
                     for u in r.uzytkownicy.values())),
        tuple(sorted((k.id, k.aktywne) for k in r.konta.values())),
        tuple(sorted((x.id, tuple(sorted((a, str(o.do)) for a, o in x.aktywne_role.items()))) for x in r.sesje.values())),
        tuple((p.rola, p.zasob, tuple(sorted(o.value for o in p.operacje)), p.typ_rekordu) for p in r.katalog),
    )


ZDARZENIA_ZMIAN = {"zmiana_przypisania", "zdarzenie_kadrowe", "aktywacja_roli", "tryb_awaryjny", "recertyfikacja",
                   "blokada_konta", "zmiana_katalogu", "koniec_sesji"}


def m9() -> WynikMetryki:
    org = Przyklad()
    s = org.system
    licznik = {"decyzje": 0}
    oryginal = s.zadaj

    def zadaj_liczone(*a, **kw):
        licznik["decyzje"] += 1
        return oryginal(*a, **kw)
    s.zadaj = zadaj_liczone

    zmiany, zmiany_z_wpisem, wiersze = 0, 0, []

    def operacja(opis, fn):
        nonlocal zmiany, zmiany_z_wpisem
        przed, n = _migawka(s), len(s.dziennik)
        fn()
        nowe = [w.zdarzenie for w in s.dziennik.wpisy()[n:]]
        if _migawka(s) != przed:
            zmiany += 1
            ok = bool(ZDARZENIA_ZMIAN & set(nowe))
            zmiany_z_wpisem += ok
            wiersze.append([opis, "tak", ", ".join(sorted(set(nowe) & ZDARZENIA_ZMIAN)) or "BRAK", "tak" if ok else "NIE"])

    t = T
    for p in WSZYSTKIE:   # decyzje – scenariusze na jednej organizacji
        org.pdp(p.konto, p.operacja, p.obiekt, **p.srodowisko)
    wn = s.wnioski.zloz("anna", "Z9", "R", t, "sekret_projektu", okres_dni=30).dane
    operacja("wniosek – akceptacja przełożonego", lambda: s.wnioski.akceptuj(wn.id, "piotr", t))
    operacja("wniosek – akceptacja właściciela i realizacja", lambda: s.wnioski.akceptuj(wn.id, "wanda", t))
    operacja("przypisanie roli uprzywilejowanej", lambda: s.sesje.przypisz_role("sylwia", "ADM_Z9", "radek", t))
    prosba = s.sesje.aktywuj("henryk-adm", "ADM_Z13", t, numer_zgloszenia="ZGL-1").dane
    operacja("aktywacja roli (po akceptacji właściciela)", lambda: s.sesje.zatwierdz_aktywacje(prosba, "natalia", t))
    operacja("aktywacja roli administratora Z10", lambda: s.sesje.aktywuj("henryk-adm", "ADM_Z10", t, numer_zgloszenia="ZGL-2"))
    operacja("tryb awaryjny produkcji", lambda: s.sesje.tryb_awaryjny_produkcja("daria", "INC-1", t))
    operacja("zastępstwo awaryjne 72 h", lambda: s.sesje.zastepstwo_awaryjne("lukasz", "anna", "Z9", "R", t, "sekret_projektu"))
    operacja("wyznaczenie zastępcy (RE3)", lambda: s.sesje.wyznacz_zastepce("grzegorz", "felicja", "edward", t, t + 5 * DZIEN, t))
    poz = __import__("dostep.polityka.katalog", fromlist=["PozycjaKatalogu"]).PozycjaKatalogu(
        "T12", "Z10", operacje("R"), "wniosek", "dane_kontaktowe", "analiza")
    zm = s.wnioski.zaproponuj_zmiane_katalogu("wanda", poz, "dodaj", t).dane
    operacja("zmiana katalogu (SO8)", lambda: s.wnioski.zatwierdz_zmiane_katalogu(zm, "henryk", t))
    operacja("oświadczenie NDA", lambda: s.kadry.zloz_oswiadczenie_nda("bartek", "Klient X", t))
    operacja("przeniesienie", lambda: s.kadry.przenies("daria", "A1", t, "A", "Plemię A"))
    operacja("czasowe przeniesienie", lambda: s.kadry.przenies_czasowo("bartek", "A1", t))
    operacja("koniec czasowego przeniesienia", lambda: s.kadry.zakoncz_przeniesienie_czasowe("bartek", t + DZIEN))
    operacja("zmiana stanowiska", lambda: s.kadry.zmien_stanowisko("sylwia", "T1", t))
    operacja("dyżur", lambda: s.kadry.dyzur("emil", t, t + 8 * GODZ, t))
    operacja("odejście", lambda: s.kadry.odejscie("radek", t + GODZ))
    nowy = Uzytkownik("nowy", "Nowa Osoba", "T3", "P4", "Plemię A", zespol="A1", plemie="A", przelozony_id="piotr")
    operacja("zatrudnienie", lambda: s.kadry.zatrudnij(nowy, t))
    operacja("zadania codzienne (koniec umów, wygasanie)", lambda: s.przetworz_terminy(t + 4 * DZIEN))
    rec = s.recertyfikacja.uruchom(t + 200 * DZIEN)
    for p in rec[:2]:
        operacja(f"recertyfikacja – odebranie ({p.opis})",
                 lambda p=p: s.recertyfikacja.rozstrzygnij(p.id, p.recenzent_id, t + 200 * DZIEN, False))
    operacja("zadania codzienne po 6 miesiącach (blokady, wygasanie)", lambda: s.przetworz_terminy(t + 200 * DZIEN))

    decyzje_wpisy = sum(1 for w in s.dziennik.wpisy() if w.zdarzenie == "decyzja")
    lancuch = s.dziennik.weryfikuj()
    # wykrycie modyfikacji: podmiana jednego wpisu z pominięciem API
    from dataclasses import replace
    kopia = list(s.dziennik._wpisy)
    s.dziennik._wpisy[5] = replace(s.dziennik._wpisy[5], zdarzenie="zmienione")
    wykryto = not s.dziennik.weryfikuj()
    s.dziennik._wpisy = kopia
    razem = licznik["decyzje"] + zmiany
    pokryte = min(decyzje_wpisy, licznik["decyzje"]) + zmiany_z_wpisem
    w = WynikMetryki(
        "M9", "kompletność dziennika", f"{_proc(pokryte / razem)} ({pokryte}/{razem})", "100%",
        pokryte == razem and lancuch and wykryto,
        "Na przykładowej organizacji wykonano wszystkie scenariusze (decyzje PDP) oraz sekwencję operacji obejmującą "
        "każdy proces (wnioski, role uprzywilejowane, tryb awaryjny, zastępstwa, katalog, zdarzenia kadrowe, zadania "
        "codzienne, recertyfikacja). Liczba żądań do PEP porównana z liczbą wpisów „decyzja”; dla każdej operacji, "
        "która zmieniła stan przypisań (migawka przed i po), sprawdzono, czy powstał wpis zmiany. Dodatkowo "
        "zweryfikowano łańcuch skrótów i wykrycie podmiany wpisu.",
        [["żądania dostępu (decyzje PDP)", licznik["decyzje"], decyzje_wpisy, "tak" if decyzje_wpisy >= licznik["decyzje"] else "NIE"]]
        + [[x[0], 1, x[2], x[3]] for x in wiersze],
        ["operacja", "zdarzeń", "wpisy w dzienniku", "zarejestrowane"],
        [f"Wpisów w dzienniku: {len(s.dziennik)}; łańcuch skrótów poprawny: {'tak' if lancuch else 'NIE'}; "
         f"podmiana wpisu wykryta: {'tak' if wykryto else 'NIE'}."])
    return w


# ===========================================================================
# M10 – zawężenie uprawnień przez ABAC
# ===========================================================================
def m10() -> WynikMetryki:
    r = generuj_organizacje()
    wiersze, srednie = [], []
    for rola in ("T1", "T2", "T3", "T4", "T5", "B4"):
        ilorazy, sr_role, sr_abac = [], [], []
        for u in r.uzytkownicy.values():
            if u.rola_funkcyjna != rola or not u.aktywny:
                continue
            same_role = _efektywne(r, u.id, T, stosuj_abac=False, stosuj_so=False)
            z_abac = _efektywne(r, u.id, T, stosuj_abac=True, stosuj_so=False)
            if same_role:
                ilorazy.append((len(same_role) - len(same_role & z_abac)) / len(same_role))
                sr_role.append(len(same_role))
                sr_abac.append(len(same_role & z_abac))
        srednia = statistics.mean(ilorazy)
        srednie.append(srednia)
        wiersze.append([rola, ROLE[rola].nazwa, len(ilorazy), _l(statistics.mean(sr_role), 1),
                        _l(statistics.mean(sr_abac), 1), _proc(srednia)])
    wynik = statistics.mean(srednie)
    return WynikMetryki(
        "M10", "zawężenie uprawnień przez ABAC", f"{_proc(wynik)} (średnio dla ról T1–T5 i B4)", "> 0", wynik > 0,
        "Dla każdej osoby z rolą T1–T5 lub B4 w pełnej organizacji wyznaczono efektywne uprawnienia na poziomie obiektów "
        "(pary obiekt–operacja, na które PDP zezwala) przy samych rolach (bez warunków twardych i reguł zawężających) "
        "oraz po ich zastosowaniu (bez SO, by mierzyć wyłącznie ABAC). Zawężenie osoby = (przy rolach − po WT i RC) / "
        "przy rolach; wynik roli – średnia osób, wynik metryki – średnia sześciu ról.",
        wiersze, ["rola", "nazwa", "osób", "śr. par przy samych rolach", "śr. par po WT i RC", "zawężenie"])


# ===========================================================================
def wszystkie(api: bool = True, baza_api: str | None = None) -> list[WynikMetryki]:
    m4w, m5w = m4_m5()
    return [m1(), m2(), m3(), m4w, m5w, m6(), m7(api=api, baza_api=baza_api), m8(), m9(), m10()]
