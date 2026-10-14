"""Strona www do prezentacji (Jinja2, bez JavaScriptu po stronie budowania).

Każda akcja formularza wywołuje te same funkcje rdzenia co API, a wynik pokazuje się jako komunikat
(wzorzec POST → przekierowanie → GET).
"""
from __future__ import annotations

import json
from collections import defaultdict
from datetime import timedelta
from pathlib import Path
from urllib.parse import quote, unquote

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from dostep.model import FormaWspolpracy, Operacja, Siec, TypKonta, Urzadzenie, Uzytkownik
from dostep.polityka.role import ROLE, role_efektywne
from dostep.polityka.zasoby import ZASOBY
from dostep.przyklad import Przyklad
from dostep.scenariusze import WSZYSTKIE
from dostep.stan_przed import statystyki
from dostep.system import Rezultat

KATALOG_SZABLONOW = Path(__file__).parent / "szablony"
szablony = Jinja2Templates(directory=str(KATALOG_SZABLONOW))
szablony.env.globals["ROLE"] = ROLE
szablony.env.globals["ZASOBY"] = ZASOBY
szablony.env.globals["dict"] = dict
szablony.env.filters["czas"] = lambda t: t.strftime("%Y-%m-%d %H:%M") if t else "–"

strony = APIRouter(include_in_schema=False)


# ---------------------------------------------------------------------------
# Pomocnicze
# ---------------------------------------------------------------------------
def _stan(request: Request):
    return request.app.state.stan


def _konto(request: Request) -> str | None:
    k = request.cookies.get("konto")
    return k if k and k in _stan(request).system.rejestr.konta else None


def _render(request: Request, szablon: str, **dane) -> HTMLResponse:
    s = _stan(request)
    r = s.system.rejestr
    konto = _konto(request)
    u = r.uzytkownik(r.konto(konto).uzytkownik_id) if konto else None
    grupy = defaultdict(list)
    for k in sorted(r.konta.values(), key=lambda k: (r.uzytkownik(k.uzytkownik_id).jednostka, k.id)):
        grupy[r.uzytkownik(k.uzytkownik_id).jednostka].append(
            (k.id, f"{r.uzytkownik(k.uzytkownik_id).imie_nazwisko} – {ROLE[r.uzytkownik(k.uzytkownik_id).rola_funkcyjna].nazwa}"
                   + ("" if k.typ is TypKonta.ZWYKLE else f" [{k.typ.value}]") + ("" if k.aktywne else " (zablokowane)")))
    komunikat = None
    if "komunikat" in request.cookies:
        try:
            komunikat = json.loads(unquote(request.cookies["komunikat"]))
        except ValueError:
            komunikat = None
    odp = szablony.TemplateResponse(request, szablon, dict(
        stan=s, czas=s.czas, zbior=s.zbior, konto=konto, uzytkownik=u, grupy_kont=dict(grupy),
        komunikat=komunikat, strona=szablon.removesuffix(".html"), **dane))
    if komunikat is not None:
        odp.delete_cookie("komunikat")
    return odp


def _wroc(request: Request, wynik: Rezultat | dict | str, adres: str | None = None) -> RedirectResponse:
    if isinstance(wynik, Rezultat):
        k = dict(ok=wynik.ok, tekst=wynik.komunikat, reguly=wynik.reguly)
    elif isinstance(wynik, str):
        k = dict(ok=True, tekst=wynik, reguly=[])
    else:
        k = wynik
    odp = RedirectResponse(adres or request.headers.get("referer") or "/", status_code=303)
    odp.set_cookie("komunikat", quote(json.dumps(k, ensure_ascii=False)[:3500]), max_age=60)
    return odp


def _wymagaj_konta(request: Request) -> str | None:
    return _konto(request)


def _podwladni(s, u: Uzytkownik) -> list[Uzytkownik]:
    """Osoby, dla których użytkownik jest przełożonym (bezpośrednio lub wyżej w linii)."""
    wynik = []
    for x in s.system.rejestr.uzytkownicy.values():
        p = s.system.przelozony(x)
        while p is not None:
            if p.id == u.id:
                wynik.append(x)
                break
            p = s.system.przelozony(p)
    return sorted(wynik, key=lambda x: x.imie_nazwisko)


# ---------------------------------------------------------------------------
# Start, logowanie, sterowanie pokazem
# ---------------------------------------------------------------------------
@strony.get("/", response_class=HTMLResponse)
def start(request: Request):
    s = _stan(request)
    r = s.system.rejestr
    jednostki = defaultdict(list)
    for u in sorted(r.uzytkownicy.values(), key=lambda u: (u.jednostka, u.zespol or "", u.poziom, u.imie_nazwisko)):
        jednostki[u.jednostka].append((u, r.konta_uzytkownika(u.id)))
    return _render(request, "start.html", jednostki=dict(jednostki))


@strony.get("/zaloguj")
def zaloguj(request: Request, konto: str, dalej: str = "/"):
    odp = RedirectResponse(dalej if dalej.startswith("/") else "/", status_code=303)
    if konto in _stan(request).system.rejestr.konta:
        odp.set_cookie("konto", konto)
    return odp


@strony.post("/demo/czas")
def demo_czas(request: Request, godziny: float = Form(...)):
    nowy = _stan(request).przesun_czas(godziny)
    return _wroc(request, f"Zegar przesunięty: {nowy:%Y-%m-%d %H:%M}")


@strony.post("/demo/reset")
def demo_reset(request: Request, zbior: str = Form(...)):
    _stan(request).reset(zbior)
    odp = _wroc(request, "Utworzono nową bazę i nowy dziennik zdarzeń.", "/")
    odp.delete_cookie("konto")
    return odp


@strony.post("/demo/codzienne")
def demo_codzienne(request: Request):
    s = _stan(request)
    dzialania = s.zmiana(lambda: s.system.przetworz_terminy(s.czas))
    return _wroc(request, dict(ok=True, tekst="Zadania codzienne: " + ("; ".join(dzialania) or "brak zmian"), reguly=[]))


# ---------------------------------------------------------------------------
# Decyzja dostępowa (PEP)
# ---------------------------------------------------------------------------
def _obiekty_wg_zasobu(s):
    grupy = defaultdict(list)
    for o in sorted(s.system.rejestr.obiekty.values(), key=lambda o: (int(o.zasob[1:]), o.id)):
        grupy[f"{o.zasob} {ZASOBY[o.zasob].nazwa} ({ZASOBY[o.zasob].klasa.name})"].append(o)
    return dict(grupy)


def _sesje_konta(s, konto):
    return [x for x in s.system.rejestr.sesje.values()
            if x.konto_id == konto and any(o.zawiera(s.czas) for o in x.aktywne_role.values())]


@strony.get("/decyzja", response_class=HTMLResponse)
def decyzja_strona(request: Request):
    s = _stan(request)
    return _render(request, "decyzja.html", obiekty=_obiekty_wg_zasobu(s), sesje=_sesje_konta(s, _konto(request)),
                   decyzja=None, zadanie={})


@strony.post("/decyzja", response_class=HTMLResponse)
def decyzja_wykonaj(request: Request, obiekt: str = Form(...), operacja: str = Form(...),
                    urzadzenie: str = Form("firmowe"), siec: str = Form("biuro"), sesja: str = Form("")):
    s = _stan(request)
    konto = _konto(request)
    if not konto:
        return _wroc(request, dict(ok=False, tekst="Najpierw wybierz konto.", reguly=[]))
    konto_obj = s.system.rejestr.konto(konto)
    d = s.decyzja(konto, operacja, obiekt, urzadzenie=Urzadzenie(urzadzenie), siec=Siec(siec), sesja_id=sesja or None,
                  interaktywne=konto_obj.typ is not TypKonta.USLUGOWE)
    zadanie = dict(obiekt=obiekt, operacja=operacja, urzadzenie=urzadzenie, siec=siec, sesja=sesja)
    return _render(request, "decyzja.html", obiekty=_obiekty_wg_zasobu(s), sesje=_sesje_konta(s, konto),
                   decyzja=d, zadanie=zadanie, obiekt=s.system.rejestr.obiekt(obiekt))


# ---------------------------------------------------------------------------
# Scenariusze SZ1–SZ10 i zwykła praca (na świeżej przykładowej organizacji, w pamięci)
# ---------------------------------------------------------------------------
@strony.get("/scenariusze", response_class=HTMLResponse)
def scenariusze(request: Request, uruchom: str | None = None):
    wyniki = {}
    if uruchom:
        do_uruchomienia = WSZYSTKIE if uruchom == "wszystkie" else [p for p in WSZYSTKIE if p.id == uruchom]
        for p in do_uruchomienia:
            org = Przyklad()
            if p.przygotuj:
                p.przygotuj(org)
            wyniki[p.id] = org.pdp(p.konto, p.operacja, p.obiekt, **p.srodowisko)
    zgodne = sum(1 for p in WSZYSTKIE if p.id in wyniki and wyniki[p.id].wynik.value == p.oczekiwany)
    return _render(request, "scenariusze.html", przypadki=WSZYSTKIE, wyniki=wyniki, zgodne=zgodne)


# ---------------------------------------------------------------------------
# Wykazy (WF-17)
# ---------------------------------------------------------------------------
@strony.get("/uprawnienia", response_class=HTMLResponse)
def uprawnienia(request: Request, obiekt: str | None = None, uzytkownik: str | None = None):
    s = _stan(request)
    konto = _konto(request)
    kto = uzytkownik or (s.system.rejestr.konto(konto).uzytkownik_id if konto else None)
    wykaz = s.system.recertyfikacja.wykaz_uzytkownika(kto, s.czas) if kto else []
    dostep = s.system.recertyfikacja.kto_ma_dostep(obiekt, s.czas) if obiekt else None
    osoba = s.system.rejestr.uzytkownik(kto) if kto else None
    return _render(request, "uprawnienia.html", wykaz=wykaz, osoba=osoba, dostep=dostep, wybrany_obiekt=obiekt,
                   obiekty=_obiekty_wg_zasobu(s),
                   osoby=sorted(s.system.rejestr.uzytkownicy.values(), key=lambda x: x.imie_nazwisko))


# ---------------------------------------------------------------------------
# Wnioski
# ---------------------------------------------------------------------------
@strony.get("/wnioski", response_class=HTMLResponse)
def wnioski(request: Request):
    s = _stan(request)
    konto = _konto(request)
    u = s.system.rejestr.uzytkownik(s.system.rejestr.konto(konto).uzytkownik_id) if konto else None
    pozycje, moje, do_akc, podwladni = [], [], [], []
    if u:
        role = role_efektywne(u.rola_funkcyjna)
        pozycje = [p for p in s.system.rejestr.katalog if p.rola in role]
        moje = sorted([w for w in s.system.wnioski.wnioski.values() if u.id in (w.wnioskujacy_id, w.beneficjent_id)],
                      key=lambda w: w.zlozony_o, reverse=True)
        do_akc = s.system.wnioski.oczekujace_dla(u.id)
        podwladni = [x for x in _podwladni(s, u) if x.przelozony_id == u.id]
    return _render(request, "wnioski.html", pozycje=pozycje, moje=moje, do_akceptacji=do_akc, podwladni=podwladni,
                   uzytkownicy=s.system.rejestr.uzytkownicy)


@strony.post("/wnioski")
def wnioski_zloz(request: Request, pozycja: str = Form(""), zasob: str = Form(""), operacje: str = Form(""),
                 typ_rekordu: str = Form(""), uzasadnienie: str = Form(""), okres_dni: int = Form(90),
                 beneficjent: str = Form("")):
    s = _stan(request)
    konto = _konto(request)
    if not konto:
        return _wroc(request, dict(ok=False, tekst="Najpierw wybierz konto.", reguly=[]))
    if pozycja:   # „zasób|operacje|typ” z listy katalogu
        zasob, operacje, typ_rekordu = (pozycja.split("|") + ["", ""])[:3]
    if not zasob or not operacje:
        return _wroc(request, dict(ok=False, tekst="Wybierz pozycję katalogu albo podaj zasób i operacje.", reguly=[]))
    return _wroc(request, s.zmiana(lambda: s.system.wnioski.zloz(
        konto, zasob, operacje.upper(), s.czas, typ_rekordu or None, uzasadnienie, okres_dni, beneficjent or None)))


@strony.post("/wnioski/{wniosek_id}/{decyzja}")
def wnioski_akceptuj(request: Request, wniosek_id: str, decyzja: str, komentarz: str = Form("")):
    s = _stan(request)
    konto = _konto(request)
    return _wroc(request, s.zmiana(lambda: s.system.wnioski.akceptuj(
        wniosek_id, konto, s.czas, decyzja == "akceptuj", komentarz)))


# ---------------------------------------------------------------------------
# Sesje uprzywilejowane, tryb awaryjny, zastępstwa
# ---------------------------------------------------------------------------
@strony.get("/sesje", response_class=HTMLResponse)
def sesje(request: Request):
    s = _stan(request)
    konto = _konto(request)
    u = s.system.rejestr.uzytkownik(s.system.rejestr.konto(konto).uzytkownik_id) if konto else None
    prosby = {k: v for k, v in s.system.sesje.prosby.items() if v["status"] == "oczekuje" and u and u.id in v["kandydaci"]}
    po_fakcie = [z for z in s.system.przeglady if z.status == "otwarte" and z.rodzaj == "akceptacja po fakcie"
                 and u and z.recenzent_id == u.id]
    wszystkie_sesje = sorted(s.system.rejestr.sesje.values(), key=lambda x: x.id, reverse=True)
    return _render(request, "sesje.html", prosby=prosby, po_fakcie=po_fakcie, wszystkie_sesje=wszystkie_sesje,
                   podwladni=_podwladni(s, u) if u else [], konto_obj=s.system.rejestr.konto(konto) if konto else None)


@strony.post("/sesje/aktywuj")
def sesje_aktywuj(request: Request, rola: str = Form(...), godziny: int = Form(8), numer: str = Form("")):
    s = _stan(request)
    return _wroc(request, s.zmiana(lambda: s.system.sesje.aktywuj(_konto(request), rola, s.czas, godziny, numer or None)))


@strony.post("/sesje/prosby/{prosba_id}")
def sesje_zatwierdz(request: Request, prosba_id: str):
    s = _stan(request)
    return _wroc(request, s.zmiana(lambda: s.system.sesje.zatwierdz_aktywacje(prosba_id, _konto(request), s.czas)))


@strony.post("/sesje/{sesja_id}/zakoncz")
def sesje_zakoncz(request: Request, sesja_id: str):
    s = _stan(request)
    sesja = s.system.rejestr.sesja(sesja_id)
    if not sesja or sesja.konto_id != _konto(request):
        return _wroc(request, dict(ok=False, tekst="Można zakończyć tylko własną sesję.", reguly=[]))
    return _wroc(request, s.zmiana(lambda: s.system.sesje.zakoncz(sesja_id, s.czas)))


@strony.post("/tryb-awaryjny")
def tryb_awaryjny(request: Request, numer: str = Form("")):
    s = _stan(request)
    return _wroc(request, s.zmiana(lambda: s.system.sesje.tryb_awaryjny_produkcja(_konto(request), numer or None, s.czas)))


@strony.post("/zastepstwa/awaryjne")
def zastepstwo_awaryjne(request: Request, beneficjent: str = Form(...), pozycja: str = Form(...)):
    s = _stan(request)
    zasob, ops, typ = (pozycja.split("|") + ["", ""])[:3]
    return _wroc(request, s.zmiana(lambda: s.system.sesje.zastepstwo_awaryjne(
        _konto(request), beneficjent, zasob, ops, s.czas, typ or None)))


@strony.post("/zastepstwa/awaryjne/{przydzial_id}")
def zastepstwo_po_fakcie(request: Request, przydzial_id: str):
    s = _stan(request)
    return _wroc(request, s.zmiana(lambda: s.system.sesje.akceptuj_po_fakcie(przydzial_id, _konto(request), s.czas)))


@strony.post("/zastepstwa")
def zastepca(request: Request, zastepowany: str = Form(...), zastepca: str = Form(...), dni: int = Form(7)):
    s = _stan(request)
    return _wroc(request, s.zmiana(lambda: s.system.sesje.wyznacz_zastepce(
        _konto(request), zastepowany, zastepca, s.czas, s.czas + timedelta(days=dni), s.czas)))


# ---------------------------------------------------------------------------
# Zdarzenia kadrowe
# ---------------------------------------------------------------------------
@strony.get("/kadry", response_class=HTMLResponse)
def kadry(request: Request):
    s = _stan(request)
    r = s.system.rejestr
    zespoly = sorted({u.zespol for u in r.uzytkownicy.values() if u.zespol})
    jednostki = sorted({u.jednostka for u in r.uzytkownicy.values()})
    klienci = sorted({o.klient for o in r.obiekty.values() if o.klient})
    return _render(request, "kadry.html", osoby=sorted(r.uzytkownicy.values(), key=lambda x: x.imie_nazwisko),
                   zespoly=zespoly, jednostki=jednostki, klienci=klienci,
                   role_funkcyjne=[x for x in ROLE.values() if x.typ.value == "funkcyjna"])


@strony.post("/kadry/{rodzaj}")
def kadry_zdarzenie(request: Request, rodzaj: str, uzytkownik: str = Form(""), zespol: str = Form(""),
                    plemie: str = Form(""), jednostka: str = Form(""), przelozony: str = Form(""), rola: str = Form(""),
                    poziom: str = Form(""), klient: str = Form(""), godziny: int = Form(12),
                    imie_nazwisko: str = Form(""), forma: str = Form("umowa o pracę"), koniec_umowy: str = Form("")):
    s = _stan(request)
    konto = _konto(request)
    if not konto or s.system.uzytkownik_konta(konto).rola_funkcyjna not in ("B9", "B11"):
        return _wroc(request, dict(ok=False, reguly=["WF-16"], tekst="Zdarzenia kadrowe wprowadza system kadrowy – "
                                   "w pokazie zaloguj się jako pracownik HR (HR business partner lub specjalista kadr)."))
    k, t = s.system.kadry, s.czas
    if rodzaj == "zatrudnienie":
        from datetime import date
        if uzytkownik in s.system.rejestr.uzytkownicy or not (uzytkownik and imie_nazwisko and rola and poziom and jednostka):
            return _wroc(request, dict(ok=False, tekst="Podaj nowy identyfikator, imię i nazwisko, rolę, poziom i jednostkę.",
                                       reguly=[]))
        nowy = Uzytkownik(uzytkownik, imie_nazwisko, rola, poziom, jednostka, forma=FormaWspolpracy(forma),
                          data_konca_umowy=date.fromisoformat(koniec_umowy) if koniec_umowy else None,
                          zespol=zespol or None, plemie=plemie or None, przelozony_id=przelozony or None)
        dzialanie = lambda: k.zatrudnij(nowy, t)  # noqa: E731
    elif rodzaj == "przeniesienie":
        dzialanie = lambda: k.przenies(uzytkownik, zespol, t, plemie or None, jednostka or None, przelozony or None)  # noqa: E731
    elif rodzaj == "przeniesienie-czasowe":
        dzialanie = lambda: k.przenies_czasowo(uzytkownik, zespol, t)  # noqa: E731
    elif rodzaj == "koniec-przeniesienia":
        dzialanie = lambda: k.zakoncz_przeniesienie_czasowe(uzytkownik, t)  # noqa: E731
    elif rodzaj == "zmiana-stanowiska":
        dzialanie = lambda: k.zmien_stanowisko(uzytkownik, rola, t, poziom or None)  # noqa: E731
    elif rodzaj == "odejscie":
        dzialanie = lambda: k.odejscie(uzytkownik, t)  # noqa: E731
    elif rodzaj == "dyzur":
        dzialanie = lambda: k.dyzur(uzytkownik, t, t + timedelta(hours=godziny), t)  # noqa: E731
    elif rodzaj == "oswiadczenie-nda":
        dzialanie = lambda: k.zloz_oswiadczenie_nda(uzytkownik, klient, t)  # noqa: E731
    else:
        return _wroc(request, dict(ok=False, tekst=f"nieznane zdarzenie {rodzaj}", reguly=[]))
    return _wroc(request, s.zmiana(dzialanie))


# ---------------------------------------------------------------------------
# Recertyfikacja
# ---------------------------------------------------------------------------
@strony.get("/recertyfikacja", response_class=HTMLResponse)
def recertyfikacja(request: Request):
    s = _stan(request)
    konto = _konto(request)
    u_id = s.system.rejestr.konto(konto).uzytkownik_id if konto else None
    pozycje = sorted(s.system.recertyfikacja.pozycje.values(), key=lambda p: p.id, reverse=True)
    moje = [p for p in pozycje if p.recenzent_id == u_id and p.status in ("oczekuje", "eskalowana")]
    return _render(request, "recertyfikacja.html", pozycje=pozycje, moje=moje, uzytkownicy=s.system.rejestr.uzytkownicy)


@strony.post("/recertyfikacja/uruchom")
def recertyfikacja_uruchom(request: Request):
    s = _stan(request)
    nowe = s.zmiana(lambda: s.system.recertyfikacja.uruchom(s.czas))
    return _wroc(request, f"Kampania recertyfikacji: {len(nowe)} nowych pozycji do przeglądu.")


@strony.post("/recertyfikacja/{pozycja_id}/{decyzja}")
def recertyfikacja_rozstrzygnij(request: Request, pozycja_id: str, decyzja: str):
    s = _stan(request)
    return _wroc(request, s.zmiana(lambda: s.system.recertyfikacja.rozstrzygnij(
        pozycja_id, _konto(request), s.czas, decyzja == "potwierdz")))


# ---------------------------------------------------------------------------
# Dziennik, sygnały, przeglądy, metryki
# ---------------------------------------------------------------------------
@strony.get("/dziennik", response_class=HTMLResponse)
def dziennik(request: Request, ile: int = 150):
    s = _stan(request)
    z_bazy = s.magazyn.wczytaj_stan().dziennik
    wpisy = list(reversed(s.system.dziennik.wpisy()[-ile:]))
    return _render(request, "dziennik.html", wpisy=wpisy, lancuch=z_bazy.weryfikuj(), liczba=len(z_bazy),
                   sygnaly=list(reversed(s.system.sygnaly[-30:])),
                   przeglady=sorted(s.system.przeglady, key=lambda z: z.id, reverse=True),
                   uzytkownicy=s.system.rejestr.uzytkownicy, postgres=s.magazyn.postgres)


@strony.post("/przeglady/{zadanie_id}/zamknij")
def przeglad_zamknij(request: Request, zadanie_id: str):
    s = _stan(request)
    return _wroc(request, s.zmiana(lambda: s.system.zamknij_przeglad(zadanie_id, _konto(request), s.czas)))


@strony.get("/metryki", response_class=HTMLResponse)
def metryki(request: Request):
    s = _stan(request)
    return _render(request, "metryki.html", st=statystyki(s.system.rejestr), operacje=list(Operacja))
