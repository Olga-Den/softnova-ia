"""Stan obecny („przed”, podrozdział 3.2) i porównanie z modelem – metryki M4 i M5.

Stan „przed” odtworzono z opisu w podrozdziale 3.2 na poziomie par (zasób, operacja):
  * uprawnienia przypisane bezpośrednio kontom, osobno w każdym systemie (S1, S2),
  * podstawą jest to, czego funkcja faktycznie używa (macierz z załącznika 2 bez warunków ABAC),
  * plus nadmiar wynikający ze słabości:
      S7  – wszyscy programiści zapisują we wszystkich repozytoriach (Z4, Z5, także usuwanie i zatwierdzanie),
      S3  – stażyści dostają uprawnienia skopiowane od programisty („jak u osoby X”, SZ8),
      S8  – stały dostęp do produkcji i sekretów: DevOps/SRE oraz programiści plemienia B pełniący dyżury,
      S12 – IT wewnętrzne realizuje zgłoszenia samo – stałe prawa administracyjne w systemach biznesowych (SZ6),
  * nie ma systemu IAM (Z17) ani katalogu – nie ma też wniosków.

M5 = Σ(|Uᵢ| + |Pᵢ|) / Σ|Uᵢ|·|Pᵢ|   [5, s. 19–20]
  licznik   – przypisania w modelu: użytkownik–rola (UA) + rola–uprawnienie (PA),
  mianownik – bezpośrednie przypisania (użytkownik, uprawnienie) w stanie „przed”.
"""
from __future__ import annotations

from collections import defaultdict

from dostep.model import Operacja, TypRoli, Uzytkownik
from dostep.polityka.katalog import PozycjaKatalogu
from dostep.polityka.macierz import MACIERZ, POZIOM_P2_P3
from dostep.polityka.role import ROLE, role_efektywne
from dostep.polityka.zakres import role_przypisane
from dostep.rejestr import Rejestr

Uprawnienie = tuple[str, str]   # (zasób, operacja)


def _pary(zasoby, ops: str) -> set[Uprawnienie]:
    return {(z, op) for z in zasoby for op in ops}


def _z_macierzy(role: list[str]) -> set[Uprawnienie]:
    return {(w.zasob, op.value) for w in MACIERZ if w.rola in role for op in w.operacje}


def uprawnienia_przed(u: Uzytkownik) -> dict[Uprawnienie, str]:
    """Bezpośrednie uprawnienia użytkownika w stanie „przed”: para → przyczyna (funkcja / słabość S…)."""
    rola = "T1" if u.rola_funkcyjna == "T2" else u.rola_funkcyjna        # S3: stażysta = kopia programisty
    wynik: dict[Uprawnienie, str] = {}
    for p in _z_macierzy(role_przypisane(Uzytkownik(u.id, "", rola, u.poziom, u.jednostka))):
        if p[0] != "Z17":                                                # brak systemu IAM
            wynik[p] = "funkcja"
    nadmiar: list[tuple[set[Uprawnienie], str]] = []
    if rola == "T1":
        nadmiar.append((_pary(("Z4", "Z5"), "RWMDA"), "S7"))
        if u.rola_funkcyjna == "T2":
            nadmiar.append((set(wynik), "S3"))
        if u.plemie == "B":
            nadmiar.append((_pary(("Z8",), "RM"), "S8"))
    if rola == "T9":
        nadmiar.append((_pary([f"Z{n}" for n in range(4, 10)], "RWMD"), "S8"))
    if rola == "T11":
        nadmiar.append((_pary([f"Z{n}" for n in (1, 2, 3, 10, 11, 12, 13, 14, 15)], "RWMD"), "S12"))
    if rola == "T10":
        nadmiar.append((_pary(("Z16",), "RWMD") | _pary(("Z9",), "R"), "S8"))
    for pary, przyczyna in nadmiar:
        for p in pary:
            wynik.setdefault(p, przyczyna)
    return wynik


def maksimum_modelu(u: Uzytkownik, katalog: list[PozycjaKatalogu]) -> set[Uprawnienie]:
    """Maksymalny zbiór par (zasób, operacja), jaki model w ogóle może dać użytkownikowi:
    macierz roli + katalog + przypisane role uprzywilejowane + rola awaryjna (podrozdział 3.5.1)."""
    pary = _z_macierzy(role_przypisane(u))
    role = role_efektywne(u.rola_funkcyjna)
    pary |= {(p.zasob, op.value) for p in katalog if p.rola in role for op in p.operacje}
    for r in u.role_uprzywilejowane | ({"AWARYJNA_Z8"} if u.rola_funkcyjna in ROLE["AWARYJNA_Z8"].kto_moze else set()):
        pary |= _z_macierzy([r])
    return pary


def statystyki(rejestr: Rejestr) -> dict:
    """M4, M5 i zestawienie przypisań przed i po – dane do rozdziału 5."""
    uzytkownicy = [u for u in rejestr.uzytkownicy.values() if u.aktywny]

    # --- M4: liczba ról / liczba użytkowników (role funkcyjne + rola bazowa, tab. 3.8) ---
    role_organizacyjne = [r for r in ROLE.values() if r.typ in (TypRoli.BAZOWA, TypRoli.FUNKCYJNA)]
    m4 = len(uzytkownicy) / len(role_organizacyjne)

    # --- przypisania w modelu (licznik M5) ---
    ua = defaultdict(int)
    for u in uzytkownicy:
        ua["RB"] += 1
        ua[u.rola_funkcyjna] += 1
        for r in u.role_uprzywilejowane:
            ua[r] += 1
    ua["USL_CICD"] = sum(1 for k in rejestr.konta.values() if k.rola == "USL_CICD")
    pa = {r: len(_z_macierzy([r])) for r in list(ROLE) + [POZIOM_P2_P3]}
    role_uzywane = [r for r in pa if ua.get(r) or r == POZIOM_P2_P3]
    suma_ua = sum(ua[r] for r in role_uzywane if r != POZIOM_P2_P3)
    suma_pa = sum(pa[r] for r in role_uzywane)

    # --- stan „przed” (mianownik M5) ---
    przed = {u.id: uprawnienia_przed(u) for u in uzytkownicy}
    suma_przed = sum(len(p) for p in przed.values())
    grupy = defaultdict(list)                     # użytkownicy o identycznym zestawie ≈ ta sama funkcja (Uᵢ, Pᵢ)
    for u in uzytkownicy:
        grupy[frozenset(przed[u.id])].append(u.id)
    przyczyny = defaultdict(int)
    for p in przed.values():
        for przyczyna in p.values():
            przyczyny[przyczyna] += 1

    # --- uprawnienia stałe ponad maksimum modelu (nadmiar usunięty przez model) ---
    ponad = {u.id: set(przed[u.id]) - maksimum_modelu(u, rejestr.katalog) for u in uzytkownicy}
    suma_ponad = sum(len(x) for x in ponad.values())
    # --- uprawnienia stałe „przed”, które w modelu nie wynikają z roli (są tylko czasowe: sesja,
    #     tryb awaryjny, dyżur, incydent, wniosek – albo nie ma ich wcale) ---
    nie_z_roli = {u.id: set(przed[u.id]) - _z_macierzy(role_przypisane(u)) for u in uzytkownicy}
    suma_nie_z_roli = sum(len(x) for x in nie_z_roli.values())

    na_role = []
    for r in sorted({u.rola_funkcyjna for u in uzytkownicy}, key=lambda x: (x[0], int(x[1:]))):
        osoby = [u for u in uzytkownicy if u.rola_funkcyjna == r]
        na_role.append(dict(rola=r, nazwa=ROLE[r].nazwa, uzytkownicy=len(osoby), pa_po=pa[r],
                            przed_srednio=sum(len(przed[u.id]) for u in osoby) / len(osoby),
                            ponad_srednio=sum(len(ponad[u.id]) for u in osoby) / len(osoby),
                            nie_z_roli_srednio=sum(len(nie_z_roli[u.id]) for u in osoby) / len(osoby)))

    return dict(
        uzytkownicy=len(uzytkownicy), role=len(role_organizacyjne), m4=m4,
        ua=suma_ua, pa=suma_pa, po=suma_ua + suma_pa,
        przed=suma_przed, grupy_przed=len(grupy), m5=(suma_ua + suma_pa) / suma_przed,
        przyczyny_przed=dict(przyczyny), ponad_maksimum=suma_ponad, stale_nie_z_roli=suma_nie_z_roli,
        mozliwe_pary=len(uzytkownicy) * 17 * len(Operacja),
        na_role=na_role,
    )
