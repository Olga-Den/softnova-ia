"""E5–E7: aplikacja (FastAPI + baza). Domyślnie SQLite; z PostgreSQL – ustaw TEST_DATABASE_URL."""
import os
import statistics
import time

import pytest
import sqlalchemy as sa

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from aplikacja.main import utworz_aplikacje  # noqa: E402


@pytest.fixture
def url(tmp_path):
    return os.environ.get("TEST_DATABASE_URL") or f"sqlite:///{tmp_path / 'test.db'}"


@pytest.fixture
def klient(url):
    with TestClient(utworz_aplikacje(url, "przyklad")) as c:
        c.post("/api/demo/reset/przyklad")
        yield c


def jako(konto):
    return {"X-Konto": konto}


def test_decyzja_przez_api(klient):
    d = klient.post("/api/decyzja", json=dict(operacja="R", obiekt="repo_y"), headers=jako("anna")).json()
    assert d["wynik"] == "odmów" and {"WT1", "RC1"} <= set(d["reguly"]) and d["krok"] == 1
    d = klient.post("/api/decyzja", json=dict(operacja="R", obiekt="repo_x"), headers=jako("anna")).json()
    assert d["zezwolono"]


def test_bez_konta_401(klient):
    assert klient.post("/api/decyzja", json=dict(operacja="R", obiekt="repo_x")).status_code == 401


def test_przeplyw_wniosku_i_trwalosc(klient, url):
    r = klient.post("/api/wnioski", json=dict(zasob="Z9", operacje="R", typ_rekordu="sekret_projektu"),
                    headers=jako("anna")).json()
    assert r["ok"], r
    wn = r["id"]
    assert not klient.post(f"/api/wnioski/{wn}/akceptacja", json={}, headers=jako("anna")).json()["ok"]   # SO6
    assert klient.post(f"/api/wnioski/{wn}/akceptacja", json={}, headers=jako("piotr")).json()["ok"]
    assert klient.post(f"/api/wnioski/{wn}/akceptacja", json={}, headers=jako("wanda")).json()["ok"]
    assert klient.post("/api/decyzja", json=dict(operacja="R", obiekt="sekret_a1"), headers=jako("anna")).json()["zezwolono"]

    # restart aplikacji – stan wczytany z bazy, dziennik ciągły
    with TestClient(utworz_aplikacje(url)) as c2:
        assert c2.post("/api/decyzja", json=dict(operacja="R", obiekt="sekret_a1"),
                       headers=jako("anna")).json()["zezwolono"]
        w = c2.get("/api/dziennik/weryfikacja").json()
        assert w["lancuch_w_bazie_poprawny"] and w["wpisy"] > 5
        assert any(x["id"] == wn and x["status"] == "zrealizowany" for x in c2.get("/api/wnioski", headers=jako("anna")).json()["moje"])


def test_zegar_i_wygasanie_sesji(klient):
    r = klient.post("/api/sesje", json=dict(rola="ADM_Z10", numer_zgloszenia="ZGL-1"), headers=jako("henryk-adm")).json()
    assert r["ok"]
    ses = r["id"]
    z = dict(operacja="W", obiekt="crm_x", sesja=ses)
    assert klient.post("/api/decyzja", json=z, headers=jako("henryk-adm")).json()["zezwolono"]
    klient.post("/api/demo/czas", json=dict(godziny=9))
    assert not klient.post("/api/decyzja", json=z, headers=jako("henryk-adm")).json()["zezwolono"]


def test_kadry_tylko_hr(klient):
    assert klient.post("/api/kadry/odejscie", json=dict(uzytkownik="bartek"), headers=jako("anna")).status_code == 403
    r = klient.post("/api/kadry/odejscie", json=dict(uzytkownik="bartek"), headers=jako("natalia")).json()
    assert r["ok"]
    d = klient.post("/api/decyzja", json=dict(operacja="R", obiekt="wiki"), headers=jako("bartek")).json()
    assert d["wynik"] == "odmów" and "WT3" in d["reguly"]


def test_potok_cicd_przez_api(klient):
    z = dict(operacja="W", obiekt="wydanie_a1", konto="cicd-potok", interaktywne=False)
    assert "SO2" in klient.post("/api/decyzja", json=z, headers=jako("radek")).json()["reguly"]
    assert klient.post("/api/decyzja", json=dict(operacja="A", obiekt="wdrozenie_a1"), headers=jako("olek")).json()["zezwolono"]
    assert klient.post("/api/decyzja", json=z, headers=jako("radek")).json()["zezwolono"]


def test_dziennik_w_bazie_niezmienny(klient, url):
    klient.post("/api/decyzja", json=dict(operacja="R", obiekt="repo_x"), headers=jako("anna"))
    silnik = sa.create_engine(url)
    for polecenie in ("UPDATE dziennik SET zdarzenie='x'", "DELETE FROM dziennik"):
        with pytest.raises(sa.exc.DBAPIError):
            with silnik.begin() as p:
                p.execute(sa.text(polecenie))
    silnik.dispose()


def test_strony_html(klient):
    for adres in ["/", "/decyzja", "/scenariusze?uruchom=wszystkie", "/wnioski", "/sesje", "/kadry",
                  "/recertyfikacja", "/uprawnienia?obiekt=repo_x", "/dziennik", "/metryki"]:
        assert klient.get(adres).status_code == 200, adres
    klient.cookies.set("konto", "anna")
    r = klient.post("/decyzja", data=dict(obiekt="repo_y", operacja="R"))
    assert r.status_code == 200 and "WT1" in r.text
    r = klient.post("/wnioski", data=dict(pozycja="Z13|R|"), follow_redirects=False)
    assert r.status_code == 303


def test_czas_odpowiedzi_api_m7(klient):
    """Wstępny pomiar M7: 95. percentyl pełnego żądania przez API < 100 ms."""
    czasy = []
    for i in range(60):
        t0 = time.perf_counter()
        klient.post("/api/decyzja", json=dict(operacja="R", obiekt=["repo_x", "repo_y", "crm_x"][i % 3]),
                    headers=jako(["anna", "kamil", "bartek"][i % 3]))
        czasy.append(time.perf_counter() - t0)
    czasy.sort()
    assert czasy[int(len(czasy) * 0.95)] < 0.100, statistics.mean(czasy)
