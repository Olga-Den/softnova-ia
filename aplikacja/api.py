"""API REST (FastAPI) – przypadki użycia z diagramu Z3.1.

Tożsamość: nagłówek `X-Konto` albo ciasteczko `konto` (logowanie symulowane – praca dotyczy
autoryzacji i rozliczalności, nie uwierzytelniania; podrozdział 1.2).

  /api/decyzja                 Wyznacz decyzję dostępową (PEP → PDP)
  /api/wnioski…                Złóż wniosek / zaakceptuj lub odrzuć
  /api/sesje…, /api/tryb-awaryjny, /api/zastepstwa…   Aktywuj rolę w sesji, tryb awaryjny
  /api/kadry/…                 Zmień przypisania ról (zdarzenie kadrowe – aktor: system kadrowy, tu: HR)
  /api/recertyfikacja/…        Przeprowadź recertyfikację
  /api/uprawnienia/…, /api/obiekty/{id}/dostep, /api/dziennik…   Przeglądaj uprawnienia i dziennik
  /api/katalog/…               Zarządzaj katalogiem (SO8)
  /api/demo/…                  Sterowanie pokazem: reset danych, zegar, zadania codzienne (w realnym systemie – harmonogram)
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Cookie, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field

from dostep.model import Decyzja, FormaWspolpracy, Siec, Urzadzenie, Uzytkownik, operacje
from dostep.polityka.katalog import PozycjaKatalogu
from dostep.polityka.role import ROLE
from dostep.polityka.zasoby import ZASOBY
from dostep.system import Rezultat

api = APIRouter(prefix="/api")


def stan(request: Request):
    return request.app.state.stan


def aktor(request: Request, x_konto: str | None = Header(default=None), konto: str | None = Cookie(default=None)) -> str:
    """Konto, w imieniu którego działa żądanie."""
    id_ = x_konto or konto
    if not id_ or id_ not in request.app.state.stan.system.rejestr.konta:
        raise HTTPException(401, "Wybierz konto (nagłówek X-Konto lub logowanie na stronie)")
    return id_


def decyzja_json(d: Decyzja) -> dict:
    return dict(wynik=d.wynik.value, zezwolono=d.zezwolono, krok=d.krok, reguly=d.reguly,
                uzasadnienie=d.uzasadnienie, zrodlo=d.zrodlo, sygnaly=d.sygnaly)


def rezultat_json(r: Rezultat) -> dict:
    dane = r.dane if isinstance(r.dane, (str, int, float, type(None))) else getattr(r.dane, "id", None)
    return dict(ok=r.ok, komunikat=r.komunikat, reguly=r.reguly, id=dane)


def _hr(s, konto: str) -> None:
    u = s.system.uzytkownik_konta(konto)
    if u.rola_funkcyjna not in ("B9", "B11"):
        raise HTTPException(403, "Zdarzenia kadrowe wprowadza system kadrowy – w pokazie: pracownik HR (rola B9 lub B11)")


# ---------------------------------------------------------------------------
# Modele żądań
# ---------------------------------------------------------------------------
class ZadanieDostepu(BaseModel):
    operacja: Literal["R", "W", "M", "D", "A"]
    obiekt: str
    urzadzenie: Literal["firmowe", "prywatne"] = "firmowe"
    siec: Literal["biuro", "VPN", "zewnętrzna"] = "biuro"
    sesja: str | None = None
    interaktywne: bool = True
    konto: str | None = Field(None, description="nadpisuje aktora (np. konto usługowe potoku)")


class NowyWniosek(BaseModel):
    zasob: str
    operacje: str
    typ_rekordu: str | None = None
    uzasadnienie: str = ""
    okres_dni: int = 90
    beneficjent: str | None = None


class Akceptacja(BaseModel):
    zgoda: bool = True
    komentarz: str = ""


class Aktywacja(BaseModel):
    rola: str
    godziny: int | None = None
    numer_zgloszenia: str | None = None


class TrybAwaryjny(BaseModel):
    numer_incydentu: str


class ZastepstwoAwaryjne(BaseModel):
    beneficjent: str
    zasob: str
    operacje: str
    typ_rekordu: str | None = None


class Zastepca(BaseModel):
    zastepowany: str
    zastepca: str
    dni: int = 7


class ZdarzenieKadrowe(BaseModel):
    uzytkownik: str
    zespol: str | None = None
    plemie: str | None = None
    jednostka: str | None = None
    przelozony: str | None = None
    rola: str | None = None
    poziom: str | None = None
    klient: str | None = None
    godziny: int = 12
    # zatrudnienie
    imie_nazwisko: str | None = None
    forma: Literal["umowa o pracę", "B2B", "staż"] = "umowa o pracę"
    koniec_umowy: date | None = None


class DecyzjaRecertyfikacji(BaseModel):
    zachowaj: bool
    komentarz: str = ""


class ZmianaKatalogu(BaseModel):
    rola: str
    zasob: str
    operacje: str
    sposob: str = "wniosek"
    typ_rekordu: str | None = None
    opis: str = ""
    dzialanie: Literal["dodaj", "usun"] = "dodaj"


class Zegar(BaseModel):
    godziny: float | None = None
    ustaw: datetime | None = None


# ---------------------------------------------------------------------------
# Informacje ogólne
# ---------------------------------------------------------------------------
@api.get("/stan", summary="Zbiór danych, zegar, liczby")
def api_stan(s=Depends(stan)):
    r = s.system.rejestr
    return dict(zbior=s.zbior, czas=s.czas, osoby=len(r.uzytkownicy), konta=len(r.konta), obiekty=len(r.obiekty),
                wpisy_dziennika=len(s.system.dziennik))


@api.get("/konta")
def api_konta(s=Depends(stan)):
    r = s.system.rejestr
    return [dict(konto=k.id, typ=k.typ.value, aktywne=k.aktywne, uzytkownik=k.uzytkownik_id,
                 imie_nazwisko=r.uzytkownik(k.uzytkownik_id).imie_nazwisko,
                 rola=r.uzytkownik(k.uzytkownik_id).rola_funkcyjna) for k in r.konta.values()]


@api.get("/obiekty")
def api_obiekty(s=Depends(stan)):
    return [dict(id=o.id, zasob=o.zasob, nazwa=o.nazwa, klasa=ZASOBY[o.zasob].klasa.name, typ_rekordu=o.typ_rekordu,
                 zespol=o.zespol, klient=o.klient) for o in s.system.rejestr.obiekty.values()]


# ---------------------------------------------------------------------------
# PEP – decyzja dostępowa
# ---------------------------------------------------------------------------
@api.post("/decyzja", summary="Wyznacz decyzję dostępową")
def api_decyzja(z: ZadanieDostepu, s=Depends(stan), konto: str = Depends(aktor)):
    konto = z.konto or konto
    if konto not in s.system.rejestr.konta or z.obiekt not in s.system.rejestr.obiekty:
        raise HTTPException(404, "nieznane konto lub obiekt")
    d = s.decyzja(konto, z.operacja, z.obiekt, urzadzenie=Urzadzenie(z.urzadzenie), siec=Siec(z.siec),
                  sesja_id=z.sesja, interaktywne=z.interaktywne)
    return decyzja_json(d)


# ---------------------------------------------------------------------------
# Wnioski
# ---------------------------------------------------------------------------
@api.post("/wnioski", summary="Złóż wniosek o uprawnienie")
def api_zloz(w: NowyWniosek, s=Depends(stan), konto: str = Depends(aktor)):
    return rezultat_json(s.zmiana(lambda: s.system.wnioski.zloz(
        konto, w.zasob, w.operacje.upper(), s.czas, w.typ_rekordu or None, w.uzasadnienie, w.okres_dni,
        w.beneficjent or None)))


@api.get("/wnioski")
def api_wnioski(s=Depends(stan), konto: str = Depends(aktor)):
    u = s.system.uzytkownik_konta(konto)
    def opis(w):
        return dict(id=w.id, wnioskujacy=w.wnioskujacy_id, beneficjent=w.beneficjent_id, uprawnienie=w.opis(),
                    status=w.status.value, powod=w.powod, zlozony_o=w.zlozony_o,
                    akceptacje=[dict(rola=x.rola, kandydaci=x.kandydaci, udzielona_przez=x.udzielona_przez)
                                for x in w.wymagania])
    wsz = s.system.wnioski.wnioski.values()
    return dict(moje=[opis(w) for w in wsz if u.id in (w.wnioskujacy_id, w.beneficjent_id)],
                do_akceptacji=[opis(w) for w in s.system.wnioski.oczekujace_dla(u.id)])


@api.post("/wnioski/{wniosek_id}/akceptacja", summary="Zaakceptuj lub odrzuć wniosek")
def api_akceptuj(wniosek_id: str, a: Akceptacja, s=Depends(stan), konto: str = Depends(aktor)):
    return rezultat_json(s.zmiana(lambda: s.system.wnioski.akceptuj(wniosek_id, konto, s.czas, a.zgoda, a.komentarz)))


# ---------------------------------------------------------------------------
# Role uprzywilejowane, tryb awaryjny, zastępstwa
# ---------------------------------------------------------------------------
@api.post("/sesje", summary="Aktywuj rolę uprzywilejowaną w sesji")
def api_aktywuj(a: Aktywacja, s=Depends(stan), konto: str = Depends(aktor)):
    return rezultat_json(s.zmiana(lambda: s.system.sesje.aktywuj(konto, a.rola, s.czas, a.godziny,
                                                                 a.numer_zgloszenia or None)))


@api.post("/sesje/prosby/{prosba_id}/zatwierdz", summary="Właściciel zatwierdza aktywację (Z13, Z17)")
def api_zatwierdz_aktywacje(prosba_id: str, s=Depends(stan), konto: str = Depends(aktor)):
    return rezultat_json(s.zmiana(lambda: s.system.sesje.zatwierdz_aktywacje(prosba_id, konto, s.czas)))


@api.post("/sesje/{sesja_id}/zakoncz")
def api_zakoncz(sesja_id: str, s=Depends(stan), konto: str = Depends(aktor)):
    sesja = s.system.rejestr.sesja(sesja_id)
    if not sesja or sesja.konto_id != konto:
        raise HTTPException(403, "można zakończyć tylko własną sesję")
    return rezultat_json(s.zmiana(lambda: s.system.sesje.zakoncz(sesja_id, s.czas)))


@api.post("/tryb-awaryjny", summary="Uruchom tryb awaryjny produkcji")
def api_tryb_awaryjny(t: TrybAwaryjny, s=Depends(stan), konto: str = Depends(aktor)):
    return rezultat_json(s.zmiana(lambda: s.system.sesje.tryb_awaryjny_produkcja(konto, t.numer_incydentu, s.czas)))


@api.post("/zastepstwa/awaryjne", summary="Nagłe zastępstwo – uprawnienie na 72 h")
def api_zastepstwo(z: ZastepstwoAwaryjne, s=Depends(stan), konto: str = Depends(aktor)):
    return rezultat_json(s.zmiana(lambda: s.system.sesje.zastepstwo_awaryjne(
        konto, z.beneficjent, z.zasob, z.operacje.upper(), s.czas, z.typ_rekordu or None)))


@api.post("/zastepstwa/awaryjne/{przydzial_id}/akceptacja", summary="Akceptacja zastępstwa po fakcie")
def api_po_fakcie(przydzial_id: str, s=Depends(stan), konto: str = Depends(aktor)):
    return rezultat_json(s.zmiana(lambda: s.system.sesje.akceptuj_po_fakcie(przydzial_id, konto, s.czas)))


@api.post("/zastepstwa", summary="Wyznacz zastępcę z uprawnieniami zatwierdzającymi (RE3)")
def api_zastepca(z: Zastepca, s=Depends(stan), konto: str = Depends(aktor)):
    return rezultat_json(s.zmiana(lambda: s.system.sesje.wyznacz_zastepce(
        konto, z.zastepowany, z.zastepca, s.czas, s.czas + timedelta(days=z.dni), s.czas)))


# ---------------------------------------------------------------------------
# Zdarzenia kadrowe
# ---------------------------------------------------------------------------
@api.post("/kadry/{rodzaj}", summary="Zdarzenie kadrowe (tab. 3.18)")
def api_kadry(rodzaj: Literal["zatrudnienie", "przeniesienie", "przeniesienie-czasowe", "koniec-przeniesienia",
                              "zmiana-stanowiska", "odejscie", "dyzur", "oswiadczenie-nda"],
              z: ZdarzenieKadrowe, s=Depends(stan), konto: str = Depends(aktor)):
    _hr(s, konto)
    k, t = s.system.kadry, s.czas
    if rodzaj != "zatrudnienie" and z.uzytkownik not in s.system.rejestr.uzytkownicy:
        raise HTTPException(404, f"nieznany użytkownik {z.uzytkownik}")
    if rodzaj == "zatrudnienie":
        if not (z.rola and z.poziom and z.jednostka and z.imie_nazwisko):
            raise HTTPException(422, "zatrudnienie wymaga: imie_nazwisko, rola, poziom, jednostka")
        if z.uzytkownik in s.system.rejestr.uzytkownicy:
            raise HTTPException(409, "taki identyfikator już istnieje")
        nowy = Uzytkownik(z.uzytkownik, z.imie_nazwisko, z.rola, z.poziom, z.jednostka, forma=FormaWspolpracy(z.forma),
                          data_konca_umowy=z.koniec_umowy, zespol=z.zespol, plemie=z.plemie, przelozony_id=z.przelozony)
        dzialanie = lambda: k.zatrudnij(nowy, t)  # noqa: E731
    elif rodzaj == "przeniesienie":
        dzialanie = lambda: k.przenies(z.uzytkownik, z.zespol, t, z.plemie, z.jednostka, z.przelozony)  # noqa: E731
    elif rodzaj == "przeniesienie-czasowe":
        dzialanie = lambda: k.przenies_czasowo(z.uzytkownik, z.zespol, t)  # noqa: E731
    elif rodzaj == "koniec-przeniesienia":
        dzialanie = lambda: k.zakoncz_przeniesienie_czasowe(z.uzytkownik, t)  # noqa: E731
    elif rodzaj == "zmiana-stanowiska":
        dzialanie = lambda: k.zmien_stanowisko(z.uzytkownik, z.rola, t, z.poziom)  # noqa: E731
    elif rodzaj == "odejscie":
        dzialanie = lambda: k.odejscie(z.uzytkownik, t)  # noqa: E731
    elif rodzaj == "dyzur":
        dzialanie = lambda: k.dyzur(z.uzytkownik, t, t + timedelta(hours=z.godziny), t)  # noqa: E731
    else:
        dzialanie = lambda: k.zloz_oswiadczenie_nda(z.uzytkownik, z.klient, t)  # noqa: E731
    return rezultat_json(s.zmiana(dzialanie))


# ---------------------------------------------------------------------------
# Recertyfikacja, wykazy, katalog
# ---------------------------------------------------------------------------
@api.get("/recertyfikacja")
def api_recert(s=Depends(stan), konto: str = Depends(aktor)):
    u = s.system.uzytkownik_konta(konto)
    return [dict(vars(p)) for p in s.system.recertyfikacja.pozycje.values()
            if p.recenzent_id == u.id or p.uzytkownik_id == u.id]


@api.post("/recertyfikacja/{pozycja_id}", summary="Potwierdź albo odbierz przypisanie")
def api_rozstrzygnij(pozycja_id: str, d: DecyzjaRecertyfikacji, s=Depends(stan), konto: str = Depends(aktor)):
    return rezultat_json(s.zmiana(lambda: s.system.recertyfikacja.rozstrzygnij(
        pozycja_id, konto, s.czas, d.zachowaj, d.komentarz)))


@api.get("/uprawnienia/{uzytkownik_id}", summary="Wykaz uprawnień użytkownika (WF-17)")
def api_wykaz(uzytkownik_id: str, s=Depends(stan), konto: str = Depends(aktor)):
    if uzytkownik_id not in s.system.rejestr.uzytkownicy:
        raise HTTPException(404, "nieznany użytkownik")
    return s.system.recertyfikacja.wykaz_uzytkownika(uzytkownik_id, s.czas)


@api.get("/obiekty/{obiekt_id}/dostep", summary="Kto ma dostęp do obiektu (WF-17)")
def api_kto(obiekt_id: str, s=Depends(stan), konto: str = Depends(aktor)):
    if obiekt_id not in s.system.rejestr.obiekty:
        raise HTTPException(404, "nieznany obiekt")
    return s.system.recertyfikacja.kto_ma_dostep(obiekt_id, s.czas)


@api.post("/katalog/zmiany", summary="Zaproponuj zmianę katalogu (SO8)")
def api_katalog(z: ZmianaKatalogu, s=Depends(stan), konto: str = Depends(aktor)):
    if z.rola not in ROLE or z.zasob not in ZASOBY:
        raise HTTPException(404, "nieznana rola lub zasób")
    poz = PozycjaKatalogu(z.rola, z.zasob, operacje(z.operacje.upper()), z.sposob, z.typ_rekordu or None, z.opis)
    if z.dzialanie == "usun":
        poz = next((p for p in s.system.rejestr.katalog if (p.rola, p.zasob, p.operacje, p.typ_rekordu) ==
                    (poz.rola, poz.zasob, poz.operacje, poz.typ_rekordu)), poz)
    return rezultat_json(s.zmiana(lambda: s.system.wnioski.zaproponuj_zmiane_katalogu(konto, poz, z.dzialanie, s.czas)))


@api.post("/katalog/zmiany/{zmiana_id}/zatwierdz", summary="Administrator systemu zatwierdza zmianę katalogu")
def api_katalog_zatwierdz(zmiana_id: str, s=Depends(stan), konto: str = Depends(aktor)):
    return rezultat_json(s.zmiana(lambda: s.system.wnioski.zatwierdz_zmiane_katalogu(zmiana_id, konto, s.czas)))


# ---------------------------------------------------------------------------
# Dziennik, sygnały, przeglądy
# ---------------------------------------------------------------------------
@api.get("/dziennik")
def api_dziennik(limit: int = 100, s=Depends(stan)):
    return [dict(nr=w.nr, czas=w.czas, zdarzenie=w.zdarzenie, dane=dict(w.dane), skrot=w.skrot)
            for w in s.system.dziennik.wpisy()[-limit:]]


@api.get("/dziennik/weryfikacja", summary="Sprawdź łańcuch skrótów dziennika")
def api_weryfikacja(s=Depends(stan)):
    pamiec = s.system.dziennik.weryfikuj()
    z_bazy = s.magazyn.wczytaj_stan().dziennik
    return dict(wpisy=len(z_bazy), lancuch_w_bazie_poprawny=z_bazy.weryfikuj(), lancuch_w_pamieci_poprawny=pamiec)


@api.get("/sygnaly")
def api_sygnaly(s=Depends(stan)):
    return [dict(czas=c, tekst=t) for c, t in s.system.sygnaly]


@api.get("/przeglady")
def api_przeglady(s=Depends(stan)):
    return [dict(vars(z)) for z in s.system.przeglady]


@api.post("/przeglady/{zadanie_id}/zamknij")
def api_zamknij(zadanie_id: str, s=Depends(stan), konto: str = Depends(aktor)):
    return rezultat_json(s.zmiana(lambda: s.system.zamknij_przeglad(zadanie_id, konto, s.czas)))


# ---------------------------------------------------------------------------
# Sterowanie pokazem (w realnym systemie: harmonogram zadań i administrator wdrożenia)
# ---------------------------------------------------------------------------
@api.post("/demo/reset/{zbior}", summary="Nowa baza: przyklad albo pelna")
def api_reset(zbior: Literal["przyklad", "pelna"], s=Depends(stan)):
    s.reset(zbior)
    return api_stan(s)


@api.post("/demo/czas", summary="Przesuń lub ustaw zegar symulowany")
def api_czas(z: Zegar, s=Depends(stan)):
    if z.ustaw:
        s.ustaw_czas(z.ustaw)
    elif z.godziny:
        s.przesun_czas(z.godziny)
    return dict(czas=s.czas)


@api.post("/demo/zadania-codzienne", summary="Koniec umów, wygasanie, blokady, eskalacje (codzienne zadanie)")
def api_codzienne(s=Depends(stan)):
    return dict(dzialania=s.zmiana(lambda: s.system.przetworz_terminy(s.czas)))


@api.post("/demo/recertyfikacja", summary="Uruchom kampanię recertyfikacji")
def api_kampania(s=Depends(stan)):
    nowe = s.zmiana(lambda: s.system.recertyfikacja.uruchom(s.czas))
    return [dict(vars(p)) for p in nowe]
