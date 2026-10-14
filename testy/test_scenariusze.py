"""Scenariusze zagrożeń SZ1–SZ10 i scenariusze zwykłej pracy – podstawa M1, M2, M6."""
import pytest

from dostep.model import Wynik
from dostep.scenariusze import SCENARIUSZE_ZAGROZEN, ZWYKLA_PRACA, Przypadek


def _sprawdz(swiat, p: Przypadek):
    if p.przygotuj:
        p.przygotuj(swiat)
    d = swiat.pdp(p.konto, p.operacja, p.obiekt, **p.srodowisko)
    opis = f"{p.id} ({p.opis}): {d}"
    assert d.wynik is Wynik(p.oczekiwany), opis
    assert p.reguly <= set(d.reguly), f"{opis}\nbrakujące reguły: {p.reguly - set(d.reguly)}"
    if p.krok is not None:
        assert d.krok == p.krok, opis
    assert d.uzasadnienie, "każda decyzja musi mieć uzasadnienie (WF-05)"
    return d


@pytest.mark.parametrize("p", SCENARIUSZE_ZAGROZEN, ids=lambda p: p.id)
def test_scenariusz_zagrozenia(swiat, p):
    _sprawdz(swiat, p)


@pytest.mark.parametrize("p", ZWYKLA_PRACA, ids=lambda p: p.id)
def test_zwykla_praca(swiat, p):
    _sprawdz(swiat, p)


def test_sz5_proba_naruszenia_sod_jest_sygnalizowana(swiat):
    d = swiat.pdp("felicja", "A", "przelew_felicji")
    assert any("rozdziału obowiązków" in s for s in d.sygnaly)
    assert any(w.zdarzenie == "sygnal" for w in swiat.dziennik.wpisy())


def test_sz9_zmiana_danych_kadrowych_jest_rozliczalna(swiat):
    """SZ9: użytkownik zmienia dane w systemie kadrowo-płacowym, a potem zaprzecza zmianie."""
    d = swiat.pdp("marta", "M", "kadry_anna")
    assert d.zezwolono
    wpis = swiat.dziennik.wpisy()[-1].slownik()
    assert (wpis["podmiot"], wpis["operacja"], wpis["obiekt"], wpis["wynik"]) == \
        ("marta", "M", "kadry_anna", "zezwól")
    assert swiat.dziennik.weryfikuj()


def test_sz9_wpisu_dziennika_nie_da_sie_zmienic(swiat):
    swiat.pdp("marta", "M", "kadry_anna")
    wpis = swiat.dziennik.wpisy()[0]
    with pytest.raises(AttributeError):
        wpis.zdarzenie = "nic się nie stało"  # wpis jest niezmienny (frozen)


def test_sz9_podmiana_wpisu_jest_wykrywana(swiat):
    swiat.pdp("marta", "M", "kadry_anna")
    swiat.pdp("marta", "R", "kadry_anna")
    oryginal = swiat.dziennik._wpisy[0]
    # Symulacja ataku na magazyn dziennika z pominięciem API: podmiana podmiotu.
    from dataclasses import replace
    swiat.dziennik._wpisy[0] = replace(oryginal, dane=tuple(
        (k, "ktoś_inny" if k == "podmiot" else v) for k, v in oryginal.dane))
    assert not swiat.dziennik.weryfikuj()


def test_decyzje_sa_deterministyczne(swiat):
    """WN-02: te same dane dają tę samą decyzję z tym samym uzasadnieniem."""
    a = swiat.pdp("anna", "R", "repo_y")
    b = swiat.pdp("anna", "R", "repo_y")
    assert (a.wynik, a.krok, a.reguly, a.uzasadnienie) == (b.wynik, b.krok, b.reguly, b.uzasadnienie)
