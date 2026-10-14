"""Etap E4: pełna organizacja (199 osób) i stan „przed” – zgodność z tabelami pracy, M4, M5."""
import time
from collections import Counter

import pytest

from dostep.model import FormaWspolpracy, Operacja, Srodowisko, TypKonta, Zadanie
from dostep.organizacja import DATA_GENERACJI as T, KLIENCI, generuj_organizacje
from dostep.pdp import decyduj
from dostep.pokaz_organizacji import TABELA_3_8
from dostep.sod_statyczne import sprawdz_przypisanie_roli
from dostep.stan_przed import statystyki, uprawnienia_przed


@pytest.fixture(scope="module")
def org():
    return generuj_organizacje()


def test_liczebnosc_rol_zgodna_z_tabela_3_8(org):
    assert Counter(u.rola_funkcyjna for u in org.uzytkownicy.values()) == Counter(TABELA_3_8)


def test_jednostki_formy_i_poziomy(org):
    U = list(org.uzytkownicy.values())
    assert len(U) == 199
    assert Counter(u.forma for u in U) == {FormaWspolpracy.UMOWA_O_PRACE: 179, FormaWspolpracy.B2B: 12,
                                           FormaWspolpracy.STAZ: 8}
    j = Counter(u.jednostka for u in U)
    assert (j["Plemię A"] - 4, j["Plemię B"] - 4, j["Plemię C"]) == (64, 46, 28)     # bez stażystów (Z1.1)
    assert (j["Sprzedaż"], j["Finanse"], j["HR"], j["Marketing"]) == (22, 7, 9, 4)
    assert Counter(u.poziom for u in U) == {"P1": 3, "P2": 8, "P3": 16, "P4": 164, "P5": 8}


def test_b2b_wg_zalacznika_1(org):
    b2b = Counter(u.rola_funkcyjna + (u.plemie or "") for u in org.uzytkownicy.values()
                  if u.forma is FormaWspolpracy.B2B)
    assert b2b == {"T1A": 6, "T1B": 3, "T9C": 2, "T8": 1}
    assert all(u.kierownik_umowy_id for u in org.uzytkownicy.values() if u.forma is FormaWspolpracy.B2B)


def test_przelozeni_tylko_na_umowie_o_prace(org):
    U = list(org.uzytkownicy.values())
    bez = [u for u in U if not u.przelozony_id]
    assert [u.stanowisko for u in bez] == ["prezes"]
    assert all(org.uzytkownik(u.przelozony_id).forma is FormaWspolpracy.UMOWA_O_PRACE for u in U if u.przelozony_id)


def test_kazdy_zasob_ma_wlasciciela_na_umowie_o_prace(org):
    for nr in range(1, 18):
        wl = org.wlasciciele(f"Z{nr}")
        assert len(wl) == 1 and wl[0].forma is FormaWspolpracy.UMOWA_O_PRACE, f"Z{nr}"


def test_przypisania_rol_uprzywilejowanych_bez_naruszen_sod(org):
    for u in org.uzytkownicy.values():
        for r in u.role_uprzywilejowane:
            assert sprawdz_przypisanie_roli(u, r) == [], (u.id, r)
            assert f"{u.id}-adm" in org.konta and org.konto(f"{u.id}-adm").typ is TypKonta.ADMINISTRACYJNE


def test_generator_deterministyczny(org):
    drugi = generuj_organizacje()
    assert list(drugi.uzytkownicy) == list(org.uzytkownicy)


def test_sz1_dla_wszystkich_programistow_plemienia_a(org):
    """Uogólnienie SZ1: każdy programista plemienia A czyta repozytorium swojego klienta, a żadnego innego."""
    programisci = [u for u in org.uzytkownicy.values() if u.rola_funkcyjna == "T1" and u.plemie == "A"]
    assert len(programisci) == 35
    for u in programisci:
        for z in [f"A{i}" for i in range(1, 8)]:
            d = decyduj(Zadanie(u.id, Operacja.R, f"repo_{z}", Srodowisko(T)), org)
            assert d.zezwolono == (z == u.zespol), (u.id, z, str(d))


def test_nda_zgodne_z_klientem_zespolu(org):
    for u in org.uzytkownicy.values():
        if u.plemie == "A" and u.zespol:
            assert KLIENCI[int(u.zespol[1]) - 1] in u.oswiadczenia_nda


def test_m4_i_m5(org):
    s = statystyki(org)
    assert 7.5 <= s["m4"] <= 7.8               # ok. 1 : 7,7 (tab. 3.20)
    assert s["m5"] < 1
    assert s["przed"] < s["mozliwe_pary"] == 16_915


def test_stan_przed_zawiera_slabosci(org):
    U = list(org.uzytkownicy.values())
    stazysta = next(u for u in U if u.rola_funkcyjna == "T2")
    assert ("Z4", "D") in uprawnienia_przed(stazysta)                    # S3 + S7 → SZ8
    devops = next(u for u in U if u.rola_funkcyjna == "T9")
    assert uprawnienia_przed(devops)[("Z8", "M")] == "S8"
    it = next(u for u in U if u.rola_funkcyjna == "T11")
    assert ("Z13", "W") in uprawnienia_przed(it)                         # S12 → SZ6
    assert all(z != "Z17" for u in U for z, _ in uprawnienia_przed(u))   # brak IAM w stanie „przed”


def test_czas_decyzji_pdp_m7_wstepnie(org):
    """Wstępny pomiar M7: 95. percentyl czasu decyzji PDP < 10 ms (pełny pomiar w E8)."""
    czasy = []
    for u in list(org.uzytkownicy.values())[:60]:
        for o in list(org.obiekty)[:40]:
            t0 = time.perf_counter()
            decyduj(Zadanie(u.id, Operacja.R, o, Srodowisko(T)), org)
            czasy.append(time.perf_counter() - t0)
    czasy.sort()
    assert czasy[int(len(czasy) * 0.95)] < 0.010
