"""Testy poszczególnych reguł, ról uprzywilejowanych i statycznego SoD."""
from datetime import timedelta

from dostep.model import Incydent, Okres, Sesja, Siec, Urzadzenie, Zastepstwo
from dostep.pdp import decyduj
from dostep.sod_statyczne import sprawdz_nadanie_wlasnosci, sprawdz_przypisanie_roli
from testy.conftest import TERAZ, X


# --- Reguły zawężające -------------------------------------------------------

def test_rc8_urzadzenie_prywatne_tylko_kw1_kw2(swiat):
    assert swiat.pdp("anna", "R", "wiki", urzadzenie=Urzadzenie.PRYWATNE, siec=Siec.ZEWNETRZNA).zezwolono
    d = swiat.pdp("anna", "R", "repo_x", urzadzenie=Urzadzenie.PRYWATNE, siec=Siec.ZEWNETRZNA)
    assert not d.zezwolono and "RC8" in d.reguly


def test_rc8_kw3_z_firmowego_tylko_biuro_lub_vpn(swiat):
    assert swiat.pdp("anna", "R", "repo_x", siec=Siec.VPN).zezwolono
    assert "RC8" in swiat.pdp("anna", "R", "repo_x", siec=Siec.ZEWNETRZNA).reguly


def test_rc11_czasowe_przeniesienie(swiat):
    b = swiat.u("bartek")
    b.zespol_tymczasowy = "A1"
    b.oswiadczenia_nda.add(X)
    assert swiat.pdp("bartek", "W", "repo_x").zezwolono          # zespół docelowy – pełne uprawnienia
    assert swiat.pdp("bartek", "R", "repo_y").zezwolono          # zespół macierzysty – odczyt
    d = swiat.pdp("bartek", "W", "repo_y")
    assert not d.zezwolono and "RC11" in d.reguly


def test_rc12_odczyt_dawnego_zespolu_tylko_14_dni(swiat):
    d = swiat.u("daria")
    d.poprzedni_zespol, d.data_przeniesienia, d.zespol = "B1", TERAZ - timedelta(days=2), "A1"
    assert swiat.pdp("daria", "R", "zadanie_b1").zezwolono
    d.data_przeniesienia = TERAZ - timedelta(days=15)
    assert not swiat.pdp("daria", "R", "zadanie_b1").zezwolono


def test_rc13_prog_platnosci(swiat):
    d = swiat.pdp("felicja", "A", "przelew_duzy")
    assert not d.zezwolono and "RC13" in d.reguly


def test_re3_zastepca_przejmuje_uprawnienia_zatwierdzajace(swiat):
    swiat.u("edward").zastepstwa.append(
        Zastepstwo("felicja", Okres(TERAZ - timedelta(days=1), TERAZ + timedelta(days=6))))
    d = swiat.pdp("edward", "A", "przelew_felicji")
    assert d.zezwolono and any("RE3" in z for z in d.uzasadnienie)
    # ale nadal nie zatwierdzi własnego przelewu
    assert not swiat.pdp("edward", "A", "przelew_maly").zezwolono


def test_rc14_dane_o_zdrowiu_tylko_specjalista_kadr(swiat):
    d = swiat.pdp("natalia", "R", "zdrowie_anna")
    assert not d.zezwolono and "RC14" in d.reguly


def test_rc17_analityk_bez_danych_osobowych(swiat):
    d = swiat.pdp("tomasz", "R", "crm_x")
    assert not d.zezwolono and "RC17" in d.reguly


def test_so1_tester_nie_zatwierdza_zmiany_kodu(swiat):
    d = swiat.pdp("jola", "A", "mr_anny")
    assert not d.zezwolono and "SO1" in d.reguly


def test_so1_programista_innego_zespolu_nie_zatwierdza(swiat):
    swiat.u("bartek").oswiadczenia_nda.add(X)
    d = swiat.pdp("bartek", "A", "mr_anny")
    assert not d.zezwolono


# --- Reguły rozszerzające i katalog -----------------------------------------

def test_re4_incydent_dotyczacy_danych(swiat):
    swiat.u("emil").incydenty.append(Incydent("INC-7", TERAZ - timedelta(hours=1), dotyczy_danych=True))
    d = swiat.pdp("emil", "R", "prod_dane")
    assert d.zezwolono and d.krok == 5 and "RE4" in d.reguly
    assert any("powiadomienie właściciela" in s for s in d.sygnaly)
    # po 12 godzinach dostęp wygasa
    assert not swiat.pdp("emil", "R", "prod_dane", czas=TERAZ + timedelta(hours=12)).zezwolono


def test_re1_wygasa_2h_po_dyzurze(swiat):
    koniec = swiat.u("daria").dyzury[0].do
    assert swiat.pdp("daria", "R", "prod_infra", czas=koniec + timedelta(hours=1, minutes=59)).zezwolono
    assert not swiat.pdp("daria", "R", "prod_infra", czas=koniec + timedelta(hours=2, minutes=1)).zezwolono


def test_wt5_iod_tylko_przy_otwartej_sprawie(swiat):
    d = swiat.pdp("ula", "R", "crm_x")
    assert not d.zezwolono and "WT5" in d.reguly and d.krok == 1
    swiat.u("ula").sprawy_iod.append(Incydent("IOD-3", TERAZ - timedelta(days=1)))
    assert swiat.pdp("ula", "R", "crm_x").zezwolono


def test_uprawnienie_z_wniosku(swiat):
    from dostep.model import Przydzial, operacje
    assert not swiat.pdp("anna", "R", "sekret_a1").zezwolono
    swiat.u("anna").przydzialy.append(Przydzial("Z9", operacje("R"), "sekret_projektu",
                                                Okres(TERAZ, TERAZ + timedelta(days=30)), "WN-1"))
    d = swiat.pdp("anna", "R", "sekret_a1")
    assert d.zezwolono and "WF-15" in d.reguly


# --- Role uprzywilejowane w sesji -------------------------------------------

def _sesja(swiat, id_, konto, role, numer=None, godz=8):
    s = Sesja(id_, konto, {r: Okres(TERAZ - timedelta(minutes=5), TERAZ + timedelta(hours=godz)) for r in role},
              numer)
    swiat.rejestr.dodaj(s)
    return s


def test_administrator_w_sesji(swiat):
    _sesja(swiat, "S1", "sylwia-adm", ["ADM_Z8"])
    d = swiat.pdp("sylwia-adm", "M", "prod_infra", sesja="S1")
    assert d.zezwolono and d.krok == 4 and "WT4" in d.reguly
    # po upływie 8 godzin rola wygasa
    assert not swiat.pdp("sylwia-adm", "M", "prod_infra", sesja="S1", czas=TERAZ + timedelta(hours=9)).zezwolono


def test_rola_administratora_ze_zwyklego_konta_narusza_wt4(swiat):
    _sesja(swiat, "S2", "henryk", ["ADM_Z10"], numer="ZGL-1")
    d = swiat.pdp("henryk", "W", "crm_x", sesja="S2")
    assert not d.zezwolono and "WT4" in d.reguly


def test_sesja_innego_konta_nie_dziala(swiat):
    _sesja(swiat, "S3", "sylwia-adm", ["ADM_Z8"])
    assert not swiat.pdp("sylwia", "M", "prod_infra", sesja="S3").zezwolono


def test_rola_awaryjna_wymaga_incydentu_i_wywoluje_alarm(swiat):
    _sesja(swiat, "S4", "radek-adm", ["AWARYJNA_Z8"], godz=4)
    assert not swiat.pdp("radek-adm", "M", "prod_infra", sesja="S4").zezwolono
    swiat.rejestr.sesje["S4"].numer_zgloszenia = "INC-42"
    d = swiat.pdp("radek-adm", "M", "prod_infra", sesja="S4")
    assert d.zezwolono and any("ALARM" in s for s in d.sygnaly)


def test_konto_uslugowe_nie_loguje_sie_interaktywnie(swiat):
    d = swiat.pdp("cicd-potok", "R", "cicd_a1")
    assert not d.zezwolono and "WF-13" in d.reguly


# --- Statyczny SoD (tabela 3.12) --------------------------------------------

def _ids(naruszenia):
    return {n.regula for n in naruszenia}


def test_ss2_specjalista_kadr_nie_moze_byc_ksiegowym(swiat):
    assert "SS2" in _ids(sprawdz_przypisanie_roli(swiat.u("marta"), "B7"))


def test_ss3_account_manager_nie_moze_byc_ksiegowym(swiat):
    assert "SS3" in _ids(sprawdz_przypisanie_roli(swiat.u("kamil"), "B7"))


def test_ss4_programista_nie_dostaje_administratora_produkcji(swiat):
    assert {"SS4", "WF-03"} <= _ids(sprawdz_przypisanie_roli(swiat.u("anna"), "ADM_Z8"))


def test_ss4_wyjatek_dla_roli_awaryjnej(swiat):
    assert sprawdz_przypisanie_roli(swiat.u("anna"), "AWARYJNA_Z8") == []


def test_ss1_administrator_it_nie_administruje_siem(swiat):
    assert "SS1" in _ids(sprawdz_przypisanie_roli(swiat.u("henryk"), "ADM_Z16"))


def test_ss5_wlasciciel_kw4_nie_jest_jego_administratorem(swiat):
    radek = swiat.u("radek")
    assert "SS5" in _ids(sprawdz_przypisanie_roli(radek, "ADM_Z8"))
    assert sprawdz_przypisanie_roli(radek, "ADM_Z6") == []    # Z6 to KW3 – dozwolone
    assert "SS5" in _ids(sprawdz_nadanie_wlasnosci(swiat.u("sylwia"), "Z8"))


def test_wlasciciel_zasobu_tylko_na_umowie_o_prace(swiat):
    assert "WF-03" in _ids(sprawdz_nadanie_wlasnosci(swiat.u("cezary"), "Z4"))


# --- Metryka M10: zawężenie przez ABAC ---------------------------------------

def test_bez_abac_rola_daje_wiecej(swiat):
    z = swiat.zadanie("anna", "R", "repo_y")
    assert decyduj(z, swiat.rejestr, stosuj_abac=False).zezwolono
    assert not decyduj(z, swiat.rejestr).zezwolono
