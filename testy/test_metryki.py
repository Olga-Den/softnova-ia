"""E8: metryki M1–M10 spełniają kryteria akceptacji z tabeli 3.20."""
import pytest

from dostep import metryki as M


@pytest.mark.parametrize("funkcja", [M.m1, M.m2, M.m3, M.m6, M.m8, M.m9, M.m10], ids=lambda f: f.__name__.upper())
def test_metryka_spelniona(funkcja):
    w = funkcja()
    assert w.spelnione, f"{w.id}: {w.wynik} (oczekiwane {w.oczekiwane}); {w.uwagi}"


def test_m4_m5():
    m4, m5 = M.m4_m5()
    assert m4.spelnione and m5.spelnione


def test_m7_pdp():
    w = M.m7(proby=2000, api=False)
    assert w.spelnione, w.wynik


def test_raport_markdown(tmp_path):
    from dostep.raport_metryk import zapisz
    wyniki = [M.m1(), *M.m4_m5()]
    zapisz(wyniki, tmp_path, 1.0)
    tekst = (tmp_path / "metryki.md").read_text(encoding="utf-8")
    assert "| M1 | poprawność decyzji" in tekst and "Metodyka" in tekst
    assert (tmp_path / "metryki.csv").exists()
