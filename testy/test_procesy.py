"""Etap E3: wnioski, sesje uprzywilejowane, tryb awaryjny, zdarzenia kadrowe, recertyfikacja."""
from datetime import date, timedelta

from dostep.model import FormaWspolpracy, Okres, Uzytkownik
from dostep.polityka.katalog import PozycjaKatalogu
from dostep.model import operacje
from dostep.wnioski import StatusWniosku
from testy.conftest import TERAZ, X

GODZ = timedelta(hours=1)
DZIEN = timedelta(days=1)


def _sygnaly(swiat, fraza):
    return [t for _, t in swiat.system.sygnaly if fraza in t]


# ===========================================================================
# Wnioski (WF-06, WF-15, tab. 3.9, SO6)
# ===========================================================================

def test_wniosek_kw4_wymaga_przelozonego_i_wlasciciela(swiat):
    w = swiat.system.wnioski
    r = w.zloz("anna", "Z9", "R", TERAZ, typ_rekordu="sekret_projektu", uzasadnienie="konfiguracja potoku")
    assert r.ok, r
    wn = r.dane
    assert [x.rola for x in wn.wymagania] == ["przełożony", "właściciel zasobu"]
    assert wn.wymagania[0].kandydaci == ["piotr"] and wn.wymagania[1].kandydaci == ["wanda"]
    assert not swiat.pdp("anna", "R", "sekret_a1").zezwolono

    # SO6: wnioskująca nie akceptuje własnego wniosku
    r = w.akceptuj(wn.id, "anna", TERAZ)
    assert not r.ok and "SO6" in r.reguly and _sygnaly(swiat, "SO6")

    assert w.akceptuj(wn.id, "piotr", TERAZ + GODZ).ok
    # ta sama osoba nie może udzielić drugiej akceptacji
    assert "SO6" in w.akceptuj(wn.id, "piotr", TERAZ + GODZ).reguly
    r = w.akceptuj(wn.id, "wanda", TERAZ + 2 * GODZ)
    assert r.ok and wn.status is StatusWniosku.ZREALIZOWANY

    assert swiat.pdp("anna", "R", "sekret_a1", czas=TERAZ + 3 * GODZ).zezwolono
    # po 90 dniach uprawnienie wygasa samo (WF-12)
    assert not swiat.pdp("anna", "R", "sekret_a1", czas=TERAZ + timedelta(days=91)).zezwolono


def test_wniosek_spoza_katalogu_odrzucany_automatycznie(swiat):
    r = swiat.system.wnioski.zloz("anna", "Z13", "R", TERAZ)
    assert not r.ok and "WF-06" in r.reguly
    assert r.dane.status is StatusWniosku.ODRZUCONY_AUTOMATYCZNIE


def test_uprawnienie_z_reguly_rozszerzajacej_nie_jest_wnioskowalne(swiat):
    r = swiat.system.wnioski.zloz("anna", "Z8", "RM", TERAZ, typ_rekordu="infrastruktura")
    assert not r.ok and "RE1" in r.reguly


def test_wniosek_kw3_tylko_wlasciciel_i_nieobecnosc(swiat):
    swiat.u("radek").nieobecnosci.append(Okres(TERAZ - DZIEN, TERAZ + 5 * DZIEN))
    r = swiat.system.wnioski.zloz("igor", "Z6", "W", TERAZ)
    assert r.ok
    wym = r.dane.wymagania
    assert [x.rola for x in wym] == ["właściciel zasobu"]
    assert wym[0].kandydaci == ["celina"]        # właściciel nieobecny → przełożony (WN-07)
    assert swiat.system.wnioski.akceptuj(r.dane.id, "celina", TERAZ).ok
    assert swiat.pdp("igor", "W", "cicd_a1", czas=TERAZ + GODZ).zezwolono


def test_wniosek_za_inna_osobe_tylko_przelozony(swiat):
    w = swiat.system.wnioski
    assert w.zloz("piotr", "Z9", "R", TERAZ, typ_rekordu="sekret_projektu", beneficjent_id="anna").ok
    r = w.zloz("bartek", "Z9", "R", TERAZ, typ_rekordu="sekret_projektu", beneficjent_id="anna")
    assert not r.ok and "SO6" in r.reguly


def test_przelozony_wnioskujacy_nie_akceptuje_jako_przelozony(swiat):
    """Piotr składa wniosek za Annę – akceptację przełożonego przejmuje wyższy poziom (Łukasz)."""
    r = swiat.system.wnioski.zloz("piotr", "Z9", "R", TERAZ, typ_rekordu="sekret_projektu", beneficjent_id="anna")
    assert r.dane.wymagania[0].kandydaci == ["lukasz"]


def test_zmiana_katalogu_bez_administratora_systemu_niemozliwa(swiat):
    """SO8: dla Z11 nikt nie ma roli administratora – zmiany nie ma kto zatwierdzić."""
    poz = PozycjaKatalogu("T12", "Z11", operacje("R"), "wniosek", "zgloszenie", "zgłoszenia – analiza jakości")
    r = swiat.system.wnioski.zaproponuj_zmiane_katalogu("wanda", poz, "dodaj", TERAZ)
    assert not r.ok and "SO8" in r.reguly


def test_zmiana_katalogu_so8_i_nadzor_cto(swiat):
    w = swiat.system.wnioski
    poz = PozycjaKatalogu("T12", "Z10", operacje("R"), "wniosek", "dane_kontaktowe", "kontakty – analiza")
    r = w.zaproponuj_zmiane_katalogu("wanda", poz, "dodaj", TERAZ)
    assert r.ok
    assert not w.zaproponuj_zmiane_katalogu("anna", poz, "dodaj", TERAZ).ok   # tylko specjalista bezpieczeństwa
    assert "SO8" in w.zatwierdz_zmiane_katalogu(r.dane, "wanda", TERAZ).reguly  # autor nie zatwierdza
    assert w.zatwierdz_zmiane_katalogu(r.dane, "henryk", TERAZ + GODZ).ok   # administrator Z10
    assert poz in swiat.rejestr.katalog
    assert any(z.rodzaj == "nadzór CTO" and z.recenzent_id == "celina" for z in swiat.system.przeglady)
    # wniosek na nową pozycję – bez upoważnienia RODO odrzucony automatycznie (WT7)
    swiat.u("tomasz").upowaznienie = None
    r = w.zloz("tomasz", "Z10", "R", TERAZ + 2 * GODZ, typ_rekordu="dane_kontaktowe")
    assert not r.ok and "WT7" in r.reguly


# ===========================================================================
# Role uprzywilejowane w sesji (WF-13, tab. 3.11)
# ===========================================================================

def test_aktywacja_roli_administratora(swiat):
    s = swiat.system.sesje
    assert "WF-13" in s.aktywuj("henryk-adm", "ADM_Z10", TERAZ).reguly          # brak numeru zgłoszenia
    assert "WT4" in s.aktywuj("henryk", "ADM_Z10", TERAZ, numer_zgloszenia="ZGL-1").reguly
    assert "WF-13" in s.aktywuj("henryk-adm", "ADM_Z10", TERAZ, godziny=9, numer_zgloszenia="ZGL-1").reguly
    r = s.aktywuj("henryk-adm", "ADM_Z10", TERAZ, numer_zgloszenia="ZGL-1")
    assert r.ok
    assert swiat.pdp("henryk-adm", "W", "crm_x", sesja=r.dane).zezwolono
    assert not swiat.pdp("henryk-adm", "W", "crm_x", sesja=r.dane, czas=TERAZ + 9 * GODZ).zezwolono


def test_aktywacja_z13_wymaga_akceptacji_wlasciciela(swiat):
    s = swiat.system.sesje
    r = s.aktywuj("henryk-adm", "ADM_Z13", TERAZ, numer_zgloszenia="ZGL-7")
    assert r.ok and r.dane.startswith("AKT")
    assert not swiat.rejestr.sesje                                  # sesja jeszcze nie istnieje
    assert not s.zatwierdz_aktywacje(r.dane, "henryk", TERAZ).ok     # sam sobie nie zatwierdzi
    r2 = s.zatwierdz_aktywacje(r.dane, "natalia", TERAZ + GODZ)
    assert r2.ok
    assert swiat.pdp("henryk-adm", "R", "kadry_anna", sesja=r2.dane, czas=TERAZ + 2 * GODZ).zezwolono


def test_przypisanie_roli_uprzywilejowanej_ss(swiat):
    s = swiat.system.sesje
    r = s.przypisz_role("anna", "ADM_Z8", "radek", TERAZ)
    assert not r.ok and "SS4" in r.reguly and _sygnaly(swiat, "ADM_Z8")
    assert "SS5" in s.przypisz_role("radek", "ADM_Z8", "celina", TERAZ).reguly
    assert "SO6" in s.przypisz_role("sylwia", "ADM_Z9", "sylwia", TERAZ).reguly
    assert s.przypisz_role("sylwia", "ADM_Z9", "radek", TERAZ).ok
    assert "ADM_Z9" in swiat.u("sylwia").role_uprzywilejowane


# ===========================================================================
# Tryb awaryjny (WF-14)
# ===========================================================================

def test_tryb_awaryjny_osoba_z_dyzuru(swiat):
    s = swiat.system.sesje
    assert not s.tryb_awaryjny_produkcja("daria", None, TERAZ).ok          # bez numeru incydentu
    r = s.tryb_awaryjny_produkcja("daria", "INC-9", TERAZ)
    assert r.ok
    d = swiat.pdp("daria", "M", "prod_dane", sesja=r.dane, czas=TERAZ + GODZ)
    assert d.zezwolono and any("ALARM" in x for x in d.sygnaly)
    przeglad = [z for z in swiat.system.przeglady if z.rodzaj == "przegląd trybu awaryjnego"]
    assert przeglad and przeglad[0].recenzent_id == "radek"
    assert not swiat.pdp("daria", "M", "prod_dane", sesja=r.dane, czas=TERAZ + 5 * GODZ).zezwolono


def test_tryb_awaryjny_lidera_przeglada_lider_bezpieczenstwa(swiat):
    r = swiat.system.sesje.tryb_awaryjny_produkcja("radek-adm", "INC-10", TERAZ)
    assert r.ok
    assert [z.recenzent_id for z in swiat.system.przeglady if z.dotyczy == r.dane] == ["wanda"]


def test_tryb_awaryjny_poza_dyzurem_odrzucony(swiat):
    r = swiat.system.sesje.tryb_awaryjny_produkcja("emil", "INC-11", TERAZ)
    assert not r.ok and _sygnaly(swiat, "odrzucona próba trybu awaryjnego")


def test_zastepstwo_awaryjne_72h(swiat):
    s = swiat.system.sesje
    assert "WF-14" in s.zastepstwo_awaryjne("lukasz", "anna", "Z13", "R", TERAZ).reguly
    assert "WF-14" in s.zastepstwo_awaryjne("beata", "anna", "Z9", "R", TERAZ, "sekret_projektu").reguly
    r = s.zastepstwo_awaryjne("lukasz", "anna", "Z9", "R", TERAZ, "sekret_projektu")
    assert r.ok
    assert swiat.pdp("anna", "R", "sekret_a1", czas=TERAZ + GODZ).zezwolono
    # bez akceptacji właściciela po fakcie – wygasa po 72 h i znika przy przetwarzaniu terminów
    dzialania = swiat.system.przetworz_terminy(TERAZ + 73 * GODZ)
    assert any("brak akceptacji po fakcie" in x for x in dzialania)
    assert not swiat.u("anna").przydzialy


def test_zastepstwo_awaryjne_zaakceptowane_po_fakcie(swiat):
    s = swiat.system.sesje
    p = s.zastepstwo_awaryjne("lukasz", "anna", "Z9", "R", TERAZ, "sekret_projektu").dane
    assert not s.akceptuj_po_fakcie(p.wniosek_id, "lukasz", TERAZ + DZIEN).ok   # nie jest właścicielem Z9
    assert s.akceptuj_po_fakcie(p.wniosek_id, "wanda", TERAZ + DZIEN).ok
    assert swiat.pdp("anna", "R", "sekret_a1", czas=TERAZ + 5 * DZIEN).zezwolono


def test_wyznaczenie_zastepcy_re3(swiat):
    s = swiat.system.sesje
    assert not s.wyznacz_zastepce("felicja", "felicja", "edward", TERAZ, TERAZ + 5 * DZIEN, TERAZ).ok
    assert not s.wyznacz_zastepce("grzegorz", "felicja", "edward", TERAZ, TERAZ + 31 * DZIEN, TERAZ).ok
    assert s.wyznacz_zastepce("grzegorz", "felicja", "edward", TERAZ, TERAZ + 5 * DZIEN, TERAZ).ok
    d = swiat.pdp("edward", "A", "przelew_felicji", czas=TERAZ + GODZ)
    assert d.zezwolono and any("RE3" in z for z in d.uzasadnienie)


# ===========================================================================
# Zdarzenia kadrowe (tab. 3.18, WF-16)
# ===========================================================================

def test_zatrudnienie_i_oswiadczenie_nda(swiat):
    k = swiat.system.kadry
    nowy = Uzytkownik("nowak", "Jan Nowak", "T1", "P4", "Plemię A", zespol="A1", plemie="A", przelozony_id="piotr")
    assert k.zatrudnij(nowy, TERAZ).ok
    assert nowy.upowaznienie.zakres == {"Z8", "Z16"}   # Z11 tylko dla programistów plemienia B
    d = swiat.pdp("nowak", "R", "repo_x", czas=TERAZ + GODZ)
    assert not d.zezwolono and d.reguly == ["WT1"]
    k.zloz_oswiadczenie_nda("nowak", X, TERAZ + GODZ)
    assert swiat.pdp("nowak", "R", "repo_x", czas=TERAZ + 2 * GODZ).zezwolono


def test_przeniesienie_odbiera_dyzur_i_kw4(swiat):
    """SZ3 przez proces: Daria przeniesiona z B1 do A1 traci produkcję, 14 dni czyta stary zespół."""
    swiat.u("daria").przydzialy.append(
        __import__("dostep.model", fromlist=["Przydzial"]).Przydzial("Z9", operacje("R"), "sekret_projektu",
                                                                     Okres(TERAZ - DZIEN, TERAZ + 30 * DZIEN), "WN-0"))
    assert swiat.pdp("daria", "R", "prod_infra").zezwolono
    r = swiat.system.kadry.przenies("daria", "A1", TERAZ + GODZ, plemie="A", jednostka="Plemię A",
                                    przelozony_id="piotr")
    assert r.ok
    assert not swiat.u("daria").przydzialy
    assert not swiat.pdp("daria", "R", "prod_infra", czas=TERAZ + 2 * GODZ).zezwolono
    assert swiat.pdp("daria", "R", "zadanie_b1", czas=TERAZ + 2 * GODZ).zezwolono
    assert not swiat.pdp("daria", "W", "zadanie_b1", czas=TERAZ + 2 * GODZ).zezwolono
    assert not swiat.pdp("daria", "R", "zadanie_b1", czas=TERAZ + 15 * DZIEN).zezwolono


def test_czasowe_przeniesienie(swiat):
    k = swiat.system.kadry
    k.zloz_oswiadczenie_nda("bartek", X, TERAZ)
    k.przenies_czasowo("bartek", "A1", TERAZ)
    assert swiat.pdp("bartek", "W", "repo_x").zezwolono
    assert not swiat.pdp("bartek", "W", "repo_y").zezwolono
    k.zakoncz_przeniesienie_czasowe("bartek", TERAZ + DZIEN)
    assert not swiat.pdp("bartek", "W", "repo_x", czas=TERAZ + 2 * DZIEN).zezwolono


def test_zmiana_stanowiska_odbiera_poprzednia_role(swiat):
    r = swiat.system.kadry.zmien_stanowisko("sylwia", "T1", TERAZ)
    assert r.ok and any("ADM_Z8" in z for z in r.dane)
    assert "ADM_Z8" not in swiat.u("sylwia").role_uprzywilejowane


def test_odejscie_blokuje_konta_i_zostawia_slad(swiat):
    r = swiat.system.kadry.odejscie("radek", TERAZ)
    assert r.ok
    assert not swiat.rejestr.konto("radek").aktywne and not swiat.rejestr.konto("radek-adm").aktywne
    assert "radek" in swiat.rejestr.konta                       # konto wyłączone, nie usunięte
    assert _sygnaly(swiat, "konto usługowe cicd-potok") and _sygnaly(swiat, "zasoby bez właściciela")
    d = swiat.pdp("radek", "R", "wiki", czas=TERAZ + GODZ)
    assert not d.zezwolono and "WT3" in d.reguly


def test_przetwarzanie_terminow(swiat):
    swiat.u("marta").ostatnia_aktywnosc = TERAZ - 46 * DZIEN
    dzialania = swiat.system.przetworz_terminy(TERAZ)
    assert any("Cezary" in x for x in dzialania)                # koniec umowy B2B 10.10
    assert not swiat.rejestr.konto("cezary").aktywne
    assert not swiat.rejestr.konto("marta").aktywne             # 45 dni bez aktywności


def test_sygnal_uprawnienia_nieuzywanego_90_dni(swiat):
    from dostep.model import Przydzial
    swiat.u("anna").przydzialy.append(Przydzial("Z9", operacje("R"), "sekret_projektu",
                                                Okres(TERAZ - 100 * DZIEN, TERAZ + 100 * DZIEN), "WN-0"))
    swiat.system.przetworz_terminy(TERAZ)
    assert _sygnaly(swiat, "nieużywane od 90 dni")


# ===========================================================================
# Recertyfikacja i wykazy (WF-17)
# ===========================================================================

def _przydzial_anny(swiat, dni=365):
    w = swiat.system.wnioski
    wn = w.zloz("anna", "Z9", "R", TERAZ, typ_rekordu="sekret_projektu", okres_dni=dni).dane
    w.akceptuj(wn.id, "piotr", TERAZ)
    w.akceptuj(wn.id, "wanda", TERAZ)


def test_recertyfikacja_kw4_co_6_miesiecy(swiat):
    _przydzial_anny(swiat)
    rec = swiat.system.recertyfikacja
    assert not [p for p in rec.uruchom(TERAZ + 100 * DZIEN) if p.uzytkownik_id == "anna"]
    poz = [p for p in rec.uruchom(TERAZ + 183 * DZIEN) if p.uzytkownik_id == "anna"]
    assert len(poz) == 1 and poz[0].recenzent_id == "wanda"
    assert not rec.rozstrzygnij(poz[0].id, "anna", TERAZ + 184 * DZIEN, True).ok
    assert rec.rozstrzygnij(poz[0].id, "wanda", TERAZ + 184 * DZIEN, True).ok
    assert not [p for p in rec.uruchom(TERAZ + 185 * DZIEN) if p.uzytkownik_id == "anna"]


def test_recertyfikacja_eskalacja_i_odebranie(swiat):
    _przydzial_anny(swiat)
    rec = swiat.system.recertyfikacja
    start = TERAZ + 183 * DZIEN
    poz = [p for p in rec.uruchom(start) if p.uzytkownik_id == "anna"][0]
    swiat.system.przetworz_terminy(start + 15 * DZIEN)
    assert poz.status == "eskalowana" and poz.recenzent_id == "celina"
    swiat.system.przetworz_terminy(start + 31 * DZIEN)
    assert poz.status == "odebrana" and not swiat.u("anna").przydzialy


def test_recertyfikacja_rol_uprzywilejowanych_i_b2b(swiat):
    k = swiat.system.kadry
    kontr = Uzytkownik("kontr", "Konrad B2B", "T1", "P4", "Plemię A", zespol="A1", plemie="A",
                       forma=FormaWspolpracy.B2B, data_konca_umowy=date(2027, 12, 31),
                       przelozony_id="piotr", kierownik_umowy_id="lukasz")
    k.zatrudnij(kontr, TERAZ)
    poz = swiat.system.recertyfikacja.uruchom(TERAZ + 92 * DZIEN)
    adm = {p.klucz: p.recenzent_id for p in poz if p.uzytkownik_id == "henryk"}
    assert adm == {"ADM_Z10": "zbigniew", "ADM_Z13": "natalia", "ADM_Z17": "wanda"}
    assert [p.recenzent_id for p in poz if p.uzytkownik_id == "kontr"] == ["lukasz"]


def test_wykazy_uprawnien(swiat):
    _przydzial_anny(swiat)
    wiersze = swiat.system.recertyfikacja.wykaz_uzytkownika("anna", TERAZ)
    assert any(w["zasob"] == "Z4" and w["zrodlo"] == "rola T1" for w in wiersze)
    assert any(w["zasob"] == "Z9" and w["zrodlo"].startswith("wniosek") for w in wiersze)
    kto = {w["uzytkownik"]: w["operacje"] for w in swiat.system.recertyfikacja.kto_ma_dostep("repo_x", TERAZ)}
    assert kto["anna"] == "RWMA" and "bartek" not in kto and kto["lukasz"] == "R"


# ===========================================================================
# Dziennik i sygnały (WF-18, M9)
# ===========================================================================

def test_powtarzajace_sie_odmowy(swiat):
    for i in range(5):
        swiat.pdp("anna", "R", "repo_y", czas=TERAZ + i * timedelta(minutes=2))
    assert _sygnaly(swiat, "powtarzające się odmowy")


def test_kazda_zmiana_przypisania_w_dzienniku(swiat):
    _przydzial_anny(swiat)
    swiat.system.kadry.odejscie("bartek", TERAZ)
    zdarzenia = [w.zdarzenie for w in swiat.dziennik.wpisy()]
    assert {"wniosek_zlozony", "akceptacja", "zmiana_przypisania", "zdarzenie_kadrowe"} <= set(zdarzenia)
    assert swiat.dziennik.weryfikuj()


def test_odejscie_przekazuje_otwarte_zadania(swiat):
    s = swiat.system
    s.sesje.tryb_awaryjny_produkcja("daria", "INC-9", TERAZ)
    wn = s.wnioski.zloz("igor", "Z6", "W", TERAZ).dane            # akceptuje Radek (właściciel Z6)
    s.kadry.odejscie("radek", TERAZ + GODZ)
    assert all(z.recenzent_id == "celina" for z in s.przeglady if z.rodzaj == "przegląd trybu awaryjnego")
    assert wn.wymagania[0].kandydaci == ["celina"]
    assert not s.wnioski.akceptuj(wn.id, "radek", TERAZ + 2 * GODZ).ok   # odchodzący nie akceptuje
    assert s.wnioski.akceptuj(wn.id, "celina", TERAZ + 2 * GODZ).ok
