"""Warstwa warunkowa (ABAC): warunki twarde WT, reguły zawężające RC, reguły rozszerzające RE
oraz ograniczenia SoD na poziomie obiektu SO (tabele 3.13, 3.15–3.17, Z2.4).

Każda reguła to funkcja przyjmująca Kontekst i zwracająca:
  * None – reguła nie dotyczy tego żądania,
  * Ocena(spelniona=True/False, komentarz) – wynik sprawdzenia.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Callable

from dostep.model import (
    Klasa, Konto, Obiekt, Operacja, Siec, Srodowisko, TypKonta, Urzadzenie, Uzytkownik, Zasob,
)
from dostep.polityka.role import role_efektywne

PROG_PLATNOSCI = 50_000          # tabela 3.9 – założenie własne
OKRES_PO_PRZENIESIENIU = timedelta(days=14)   # RC12
ZAPAS_PO_DYZURZE = timedelta(hours=2)         # RE1
MAKS_PRZY_INCYDENCIE = timedelta(hours=12)    # RE1, RE4
MAKS_ZASTEPSTWO = timedelta(days=30)          # RE3


def zl(kwota: float) -> str:
    """Kwota w formacie polskim: 50 000 zł."""
    return f"{kwota:,.0f}".replace(",", "\u00a0") + " zł"


@dataclass(frozen=True)
class Ocena:
    regula: str
    spelniona: bool
    komentarz: str

    @property
    def rodzaj(self) -> str:
        """WT, RC, RE, SO albo WF – prefiks identyfikatora."""
        return "".join(z for z in self.regula if z.isalpha())[:2]


@dataclass
class Kontekst:
    uzytkownik: Uzytkownik
    konto: Konto
    obiekt: Obiekt
    zasob: Zasob
    operacja: Operacja
    srodowisko: Srodowisko
    pobierz_uzytkownika: Callable[[str], Uzytkownik]
    pobierz_obiekt: Callable[[str], Obiekt] | None = None

    @property
    def czas(self) -> datetime:
        return self.srodowisko.czas

    @property
    def role(self) -> list[str]:
        return role_efektywne(self.uzytkownik.rola_funkcyjna)


def _ok(regula: str, komentarz: str) -> Ocena:
    return Ocena(regula, True, komentarz)


def _nie(regula: str, komentarz: str) -> Ocena:
    return Ocena(regula, False, komentarz)


# ===========================================================================
# Warunki twarde (tabela 3.15)
# ===========================================================================

def wt1(k: Kontekst) -> Ocena | None:
    """Oświadczenie o poufności wobec klienta, którego dotyczy obiekt (Z3, Z4, Z6, Z7)."""
    if k.zasob.id not in ("Z3", "Z4", "Z6", "Z7") or not k.obiekt.klient:
        return None
    if k.obiekt.klient in k.uzytkownik.oswiadczenia_nda:
        return _ok("WT1", f"złożono oświadczenie o poufności wobec klienta {k.obiekt.klient}")
    return _nie("WT1", f"brak oświadczenia o poufności wobec klienta {k.obiekt.klient}")


def wt2(k: Kontekst) -> Ocena | None:
    """Zasoby KW4 tylko z urządzenia firmowego, z sieci biurowej lub przez VPN."""
    if k.zasob.klasa is not Klasa.KW4:
        return None
    s = k.srodowisko
    if s.urzadzenie is Urzadzenie.FIRMOWE and s.siec in (Siec.BIURO, Siec.VPN):
        return _ok("WT2", f"urządzenie firmowe, sieć: {s.siec.value}")
    return _nie("WT2", f"zasób KW4 wymaga urządzenia firmowego i sieci biurowej lub VPN "
                       f"(jest: {s.urzadzenie.value}, {s.siec.value})")


def wt3(k: Kontekst) -> Ocena | None:
    """Konto jest aktywne, a umowa nie wygasła (wszystkie zasoby)."""
    u = k.uzytkownik
    if not k.konto.aktywne:
        return _nie("WT3", f"konto {k.konto.id} jest zablokowane")
    if not u.aktywny:
        return _nie("WT3", "użytkownik nie współpracuje już z organizacją")
    if u.data_konca_umowy and k.czas.date() > u.data_konca_umowy:
        return _nie("WT3", f"umowa ({u.forma.value}) wygasła {u.data_konca_umowy.isoformat()}")
    return _ok("WT3", "konto aktywne, umowa obowiązuje")


def wt4(k: Kontekst) -> Ocena | None:
    """Uprawnienie uprzywilejowane używane tylko z konta administracyjnego."""
    if k.konto.typ is TypKonta.ADMINISTRACYJNE:
        return _ok("WT4", "użyto konta administracyjnego")
    return _nie("WT4", f"rola administratora wymaga konta administracyjnego (konto {k.konto.typ.value})")


def wt5(k: Kontekst) -> Ocena:
    """Otwarta sprawa IOD (audyt lub naruszenie danych)."""
    sprawy = [s.id for s in k.uzytkownik.sprawy_iod if s.otwarty(k.czas)]
    if sprawy:
        return _ok("WT5", f"otwarta sprawa IOD {', '.join(sprawy)}")
    return _nie("WT5", "brak otwartej sprawy IOD")


def wt6(k: Kontekst) -> Ocena:
    """Zgłoszony incydent przypisany użytkownikowi."""
    inc = [i.id for i in k.uzytkownik.incydenty if i.otwarty(k.czas)]
    if inc:
        return _ok("WT6", f"przypisany incydent {', '.join(inc)}")
    return _nie("WT6", "brak przypisanego otwartego incydentu")


def wt7(k: Kontekst) -> Ocena | None:
    """Ważne upoważnienie do przetwarzania danych osobowych obejmujące zasób (zasoby ze znacznikiem DO).

    Nie dotyczy własnych danych użytkownika (np. własnego wniosku w Z17) ani kont usługowych.
    """
    if not k.zasob.dane_osobowe or k.konto.typ is TypKonta.USLUGOWE:
        return None
    u, o = k.uzytkownik, k.obiekt
    if o.typ_rekordu == "wniosek" and o.autor_id == u.id:
        return _ok("WT7", "własne dane użytkownika (własny wniosek)")
    up = u.upowaznienie
    if up is None:
        return _nie("WT7", "brak upoważnienia do przetwarzania danych osobowych (art. 29 RODO)")
    if not up.wazne(k.czas):
        return _nie("WT7", "upoważnienie do przetwarzania danych osobowych wygasło lub zostało odwołane")
    if k.zasob.id not in up.zakres:
        return _nie("WT7", f"upoważnienie nie obejmuje zasobu {k.zasob.id} ({k.zasob.nazwa})")
    return _ok("WT7", f"ważne upoważnienie do przetwarzania danych osobowych w {k.zasob.id}")


# ===========================================================================
# Reguły zawężające (tabela Z2.4)
# ===========================================================================

def _zespoly_uzytkownika(u: Uzytkownik) -> set[str]:
    return {z for z in (u.zespol, u.zespol_tymczasowy) if z}


def rc1(k: Kontekst) -> Ocena | None:
    """Obiekt należy do zespołu lub projektu użytkownika (+ RC12 po przeniesieniu)."""
    u, o = k.uzytkownik, k.obiekt
    # Lider plemienia – warunek „[plemię]” z tabeli Z2.1 traktowany jako RC1 na poziomie plemienia.
    if u.rola_funkcyjna == "T6" and u.plemie and o.plemie == u.plemie:
        return _ok("RC1", f"obiekt należy do plemienia {u.plemie} kierowanego przez użytkownika")
    if o.zespol:
        if o.zespol in _zespoly_uzytkownika(u):
            return _ok("RC1", f"obiekt należy do zespołu {o.zespol} użytkownika")
        # RC12: przez 14 dni po przeniesieniu – odczyt zasobów dotychczasowego zespołu, bez KW4.
        if (u.poprzedni_zespol == o.zespol and u.data_przeniesienia
                and k.czas <= u.data_przeniesienia + OKRES_PO_PRZENIESIENIU
                and k.operacja is Operacja.R and k.zasob.klasa is not Klasa.KW4):
            return _ok("RC1", f"RC12: odczyt zasobów poprzedniego zespołu {o.zespol} "
                              f"do {(u.data_przeniesienia + OKRES_PO_PRZENIESIENIU).date()}")
        return _nie("RC1", f"obiekt należy do zespołu {o.zespol}, a użytkownik do "
                           f"{', '.join(sorted(_zespoly_uzytkownika(u))) or 'żadnego zespołu'}")
    if o.jednostka:
        if o.jednostka == u.jednostka:
            return _ok("RC1", f"obiekt należy do jednostki użytkownika ({u.jednostka})")
        return _nie("RC1", f"obiekt należy do jednostki {o.jednostka}, użytkownik – {u.jednostka}")
    return _nie("RC1", "obiekt nie ma przypisanego zespołu ani jednostki")


def rc2(k: Kontekst) -> Ocena | None:
    """Obiekt należy do zespołu, z którym użytkownik aktualnie pracuje (T7, T8)."""
    if k.obiekt.zespol in k.uzytkownik.zespoly_wspierane:
        return _ok("RC2", f"użytkownik pracuje z zespołem {k.obiekt.zespol}")
    return _nie("RC2", f"użytkownik nie pracuje obecnie z zespołem {k.obiekt.zespol}")


def rc3(k: Kontekst) -> Ocena | None:
    """Klient przypisany lub z aktywną ofertą; pozostali – dane podstawowe; P2 – wszyscy."""
    u, o = k.uzytkownik, k.obiekt
    if u.poziom in ("P1", "P2"):
        return _ok("RC3", "poziom P2 – dostęp do wszystkich klientów")
    if o.klient in u.przypisani_klienci:
        return _ok("RC3", f"klient {o.klient} jest przypisany do użytkownika")
    if o.aktywna_oferta:
        return _ok("RC3", f"klient {o.klient} ma aktywną ofertę")
    if o.typ_rekordu == "dane_podstawowe" and k.operacja is Operacja.R:
        return _ok("RC3", "odczyt danych podstawowych klienta")
    return _nie("RC3", f"klient {o.klient} nie jest przypisany do użytkownika – dostępne tylko dane podstawowe")


def rc4(k: Kontekst) -> Ocena | None:
    """Zgłoszenie przekazano zespołowi użytkownika lub jest przez niego obsługiwane."""
    o, u = k.obiekt, k.uzytkownik
    if o.obslugujacy_id == u.id:
        return _ok("RC4", "zgłoszenie obsługiwane przez użytkownika")
    if o.zespol and o.zespol == u.zespol:
        return _ok("RC4", f"zgłoszenie przekazano zespołowi {o.zespol}")
    return _nie("RC4", "zgłoszenie nie dotyczy użytkownika ani jego zespołu")


def rc5(k: Kontekst) -> Ocena | None:
    """Faktura dotyczy jednostki kierowanej przez użytkownika."""
    if k.obiekt.jednostka == k.uzytkownik.jednostka:
        return _ok("RC5", f"faktura jednostki {k.obiekt.jednostka}")
    return _nie("RC5", f"faktura dotyczy jednostki {k.obiekt.jednostka}, nie kierowanej przez użytkownika")


def rc6(k: Kontekst) -> Ocena | None:
    """Członek komisji lub HRBP jednostki, której rekrutacja dotyczy (Z14)."""
    u, o = k.uzytkownik, k.obiekt
    if k.zasob.id != "Z14":
        return None
    if u.id in o.komisja:
        return _ok("RC6", "użytkownik jest członkiem komisji rekrutacyjnej")
    if u.rola_funkcyjna == "B9" and o.jednostka in u.jednostki_hrbp:
        return _ok("RC6", f"HRBP jednostki {o.jednostka}")
    return _nie("RC6", "użytkownik nie jest członkiem komisji ani HRBP tej jednostki")


def rc7(k: Kontekst) -> Ocena | None:
    """Lider chaptera widzi tylko bieżące wynagrodzenia członków swojego chaptera."""
    u, o = k.uzytkownik, k.obiekt
    if u.stanowisko != "lider chaptera":
        return _nie("RC7", "wgląd w wynagrodzenia mają tylko liderzy chapterów")
    if o.typ_rekordu != "wynagrodzenie_biezace" or not o.dotyczy_osoby_id:
        return _nie("RC7", "dostępne są tylko bieżące wynagrodzenia")
    osoba = k.pobierz_uzytkownika(o.dotyczy_osoby_id)
    if osoba.chapter and osoba.chapter == u.chapter:
        return _ok("RC7", f"członek chaptera {u.chapter}")
    return _nie("RC7", "osoba nie należy do chaptera użytkownika")


def rc8(k: Kontekst) -> Ocena | None:
    """Urządzenie prywatne – tylko KW1–KW2; KW3 – z sieci biurowej lub przez VPN."""
    s, klasa = k.srodowisko, k.zasob.klasa
    if klasa <= Klasa.KW2:
        return None
    if s.urzadzenie is Urzadzenie.PRYWATNE:
        return _nie("RC8", f"z urządzenia prywatnego dostępne są tylko zasoby KW1–KW2 (zasób {klasa.name})")
    if s.siec not in (Siec.BIURO, Siec.VPN):
        return _nie("RC8", f"zasób {klasa.name} wymaga sieci biurowej lub VPN")
    return _ok("RC8", "urządzenie i sieć dopuszczalne")


def rc9(k: Kontekst) -> Ocena | None:
    """Zapis tylko w gałęziach, których użytkownik jest autorem (stażysta)."""
    if k.operacja not in (Operacja.W, Operacja.M):
        return None
    if k.obiekt.autor_id == k.uzytkownik.id:
        return _ok("RC9", "gałąź utworzona przez użytkownika")
    return _nie("RC9", "stażysta zapisuje tylko w gałęziach, których jest autorem")


def rc10(k: Kontekst) -> Ocena | None:
    """Marketing – tylko kontakty ze zgodą marketingową."""
    if k.obiekt.typ_rekordu == "kontakt_ze_zgoda":
        return _ok("RC10", "kontakt ze zgodą marketingową")
    return _nie("RC10", "marketing widzi tylko kontakty ze zgodą marketingową")


def rc11(k: Kontekst) -> Ocena | None:
    """Przy czasowym przeniesieniu – w zespole macierzystym tylko odczyt (Z3–Z7)."""
    u, o = k.uzytkownik, k.obiekt
    if (k.zasob.id not in ("Z3", "Z4", "Z5", "Z6", "Z7") or not u.zespol_tymczasowy
            or o.zespol != u.zespol):
        return None
    if k.operacja is Operacja.R:
        return _ok("RC11", "odczyt w zespole macierzystym podczas czasowego przeniesienia")
    return _nie("RC11", f"podczas czasowego przeniesienia do {u.zespol_tymczasowy} "
                        f"w zespole macierzystym {u.zespol} dozwolony jest tylko odczyt")


def _kwalifikuje(osoba: Uzytkownik, o: Obiekt, pobierz: Callable[[str], Uzytkownik]) -> tuple[bool, str]:
    """Czy osoba może zatwierdzić operację według hierarchii zatwierdzeń (tabela 3.9)."""
    if o.proces == "SO3":
        if o.kwota is not None and o.kwota > PROG_PLATNOSCI:
            return osoba.stanowisko == "COO", f"płatność {zl(o.kwota)} > {zl(PROG_PLATNOSCI)} – zatwierdza COO"
        return osoba.stanowisko == "główna księgowa", f"płatność do {zl(PROG_PLATNOSCI)} – zatwierdza główna księgowa"
    if o.proces == "SO4":
        return osoba.stanowisko == "kierownik HR", "listę płac zatwierdza kierownik HR"
    if o.proces == "SO5":
        if o.dotyczy_osoby_id and pobierz(o.dotyczy_osoby_id).poziom in ("P1", "P2"):
            return osoba.rola_funkcyjna == "B1", "zmianę wynagrodzenia osoby z poziomu P2 zatwierdza członek zarządu"
        return osoba.stanowisko == "kierownik HR", "zmianę wynagrodzenia zatwierdza kierownik HR"
    if o.proces == "SO7":
        return osoba.rola_funkcyjna == "B1", "umowę z klientem zatwierdza zarząd"
    return True, "brak dodatkowych wymagań co do poziomu"


def rc13(k: Kontekst) -> Ocena | None:
    """Zatwierdzenie wymaga poziomu i progu zgodnego z hierarchią zatwierdzeń (+ RE3)."""
    if k.operacja is not Operacja.A or k.zasob.id not in ("Z10", "Z12", "Z13", "Z15"):
        return None
    ok, opis = _kwalifikuje(k.uzytkownik, k.obiekt, k.pobierz_uzytkownika)
    if ok:
        return _ok("RC13", opis)
    # RE3: zastępca uzyskuje uprawnienia zatwierdzające osoby zastępowanej.
    for z in k.uzytkownik.zastepstwa:
        if z.okres.zawiera(k.czas) and z.okres.do - z.okres.od <= MAKS_ZASTEPSTWO:
            zastepowany = k.pobierz_uzytkownika(z.zastepowany_id)
            if _kwalifikuje(zastepowany, k.obiekt, k.pobierz_uzytkownika)[0]:
                return _ok("RC13", f"{opis}; RE3: zastępstwo za {zastepowany.imie_nazwisko}")
    return _nie("RC13", opis)


def rc14(k: Kontekst) -> Ocena | None:
    """Dane o zdrowiu – tylko specjalista kadr i płac; HRBP – dane przypisanych jednostek."""
    if k.zasob.id != "Z13":
        return None
    u, o = k.uzytkownik, k.obiekt
    if o.typ_rekordu == "dane_o_zdrowiu" and u.rola_funkcyjna != "B11":
        return _nie("RC14", "dane o zdrowiu dostępne tylko dla specjalisty kadr i płac (art. 9 RODO)")
    if u.rola_funkcyjna == "B9" and u.poziom not in ("P1", "P2") and o.jednostka not in u.jednostki_hrbp:
        return _nie("RC14", f"HRBP nie obsługuje jednostki {o.jednostka}")
    return _ok("RC14", "dostęp do danych kadrowych zgodny z przypisaniem")


def rc15(k: Kontekst) -> Ocena | None:
    """Wynagrodzenia zarządu – tylko wyznaczony specjalista kadr i płac oraz główna księgowa."""
    if k.zasob.id not in ("Z12", "Z13") or k.obiekt.typ_rekordu != "wynagrodzenie_zarzadu":
        return None
    u = k.uzytkownik
    if u.wyznaczony_wynagrodzenia_zarzadu or u.stanowisko == "główna księgowa":
        return _ok("RC15", "osoba wyznaczona do obsługi wynagrodzeń zarządu")
    return _nie("RC15", "wynagrodzenia zarządu obsługuje tylko wyznaczona osoba")


def rc16(k: Kontekst) -> Ocena | None:
    """Wsparcie klienta – dostęp w czasie zmiany w grafiku."""
    if any(z.zawiera(k.czas) for z in k.uzytkownik.zmiany_wsparcia):
        return _ok("RC16", "użytkownik jest na zmianie w grafiku wsparcia")
    return _nie("RC16", "użytkownik nie jest teraz na zmianie w grafiku wsparcia")


def rc17(k: Kontekst) -> Ocena | None:
    """Analityk – tylko widoki raportowe, bez danych osobowych."""
    if k.obiekt.typ_rekordu == "widok_raportowy":
        return _ok("RC17", "widok raportowy bez danych osobowych")
    return _nie("RC17", "analityk ma dostęp tylko do widoków raportowych")


def rc18(k: Kontekst) -> Ocena | None:
    """IOD w repozytorium umów – tylko umowy powierzenia."""
    if k.obiekt.typ_rekordu == "umowa_powierzenia":
        return _ok("RC18", "umowa powierzenia przetwarzania danych")
    return _nie("RC18", "IOD ma dostęp tylko do umów powierzenia")


def rc19(k: Kontekst) -> Ocena | None:
    """Usunięcie dopuszczalne po upływie okresu przechowywania (Z14, Z15)."""
    if k.operacja is not Operacja.D or k.zasob.id not in ("Z14", "Z15"):
        return None
    t = k.obiekt.termin_przechowywania
    if t and k.czas.date() > t:
        return _ok("RC19", f"okres przechowywania upłynął {t.isoformat()}")
    return _nie("RC19", "okres przechowywania jeszcze nie upłynął" if t else "brak określonego okresu przechowywania")


# ===========================================================================
# Reguły rozszerzające (tabela 3.17) – warunki pozycji katalogu
# ===========================================================================

def _otwarte_incydenty(u: Uzytkownik, t: datetime, tylko_dane: bool = False):
    return [i for i in u.incydenty if i.otwarty(t) and (i.dotyczy_danych or not tylko_dane)]


def re1(k: Kontekst) -> Ocena:
    """Dyżur + 2 h; przy otwartym incydencie do jego zamknięcia, maks. 12 h po dyżurze."""
    u, t = k.uzytkownik, k.czas
    for d in u.dyzury:
        if d.zawiera(t, ZAPAS_PO_DYZURZE):
            return _ok("RE1", f"dyżur {d.od:%d.%m %H:%M}–{d.do:%H:%M} (+2 h)")
        if d.zawiera(t, MAKS_PRZY_INCYDENCIE) and _otwarte_incydenty(u, t):
            return _ok("RE1", "otwarty incydent po dyżurze (maks. 12 h)")
    return _nie("RE1", "użytkownik nie pełni teraz dyżuru")


def re2(k: Kontekst) -> Ocena:
    """Jak RE1 albo przypisany incydent."""
    if re1(k).spelniona:
        return _ok("RE2", "dyżur")
    if _otwarte_incydenty(k.uzytkownik, k.czas):
        return _ok("RE2", "obsługa przypisanego incydentu")
    return _nie("RE2", "brak dyżuru i przypisanego incydentu")


def re4(k: Kontekst) -> Ocena:
    """Incydent dotyczący danych – R danych klientów w Z8, maks. 12 h."""
    for i in _otwarte_incydenty(k.uzytkownik, k.czas, tylko_dane=True):
        if k.czas <= i.otwarty_o + MAKS_PRZY_INCYDENCIE:
            return _ok("RE4", f"incydent dotyczący danych {i.id}")
    return _nie("RE4", "brak przypisanego incydentu dotyczącego danych (lub minęło 12 h)")


# ===========================================================================
# Rejestr reguł
# ===========================================================================

REGULY: dict[str, Callable[[Kontekst], Ocena | None]] = {
    "WT1": wt1, "WT2": wt2, "WT3": wt3, "WT4": wt4, "WT5": wt5, "WT6": wt6, "WT7": wt7,
    "RC1": rc1, "RC2": rc2, "RC3": rc3, "RC4": rc4, "RC5": rc5, "RC6": rc6, "RC7": rc7,
    "RC8": rc8, "RC9": rc9, "RC10": rc10, "RC11": rc11, "RC13": rc13, "RC14": rc14,
    "RC15": rc15, "RC16": rc16, "RC17": rc17, "RC18": rc18, "RC19": rc19,
    "RE1": re1, "RE2": re2, "RE4": re4,
}

# Reguły sprawdzane przy KAŻDYM żądaniu, niezależnie od źródła uprawnienia.
# Każda sama decyduje, czy dotyczy żądania (zwraca None, gdy nie).
REGULY_OGOLNE = ("WT3", "WT2", "WT1", "WT7", "RC8", "RC11", "RC13", "RC14", "RC15", "RC19")


def ocen(id_reguly: str, k: Kontekst) -> Ocena | None:
    return REGULY[id_reguly](k)


# ===========================================================================
# Ograniczenia SoD na poziomie obiektu (tabela 3.13)
# ===========================================================================

def _sprawdz_wykonanie_wdrozenia(k: Kontekst) -> list[Ocena]:
    """SO2 – wykonanie wdrożenia przez konto usługowe potoku tylko po zatwierdzeniu przez inną osobę."""
    o = k.obiekt
    if not o.zrodlo_id or k.pobierz_obiekt is None:
        return [_nie("SO2", "wydanie nie jest powiązane z wdrożeniem w CI/CD")]
    zrodlo = k.pobierz_obiekt(o.zrodlo_id)
    zatwierdzajacy = [z for z in zrodlo.zatwierdzone_przez if z != zrodlo.autor_id]
    if zatwierdzajacy:
        return [_ok("SO2", f"wdrożenie {zrodlo.id} zatwierdził(a): {', '.join(zatwierdzajacy)}")]
    return [_nie("SO2", f"wdrożenie {zrodlo.id} nie zostało zatwierdzone przez osobę inną niż autor")]


def sprawdz_so(k: Kontekst) -> list[Ocena]:
    """Sprawdzane przy każdym zatwierdzeniu (A) oraz przy wykonaniu wdrożenia (SO2).
    Zwraca listę ocen (puste = nie dotyczy)."""
    if k.konto.typ is TypKonta.USLUGOWE and k.operacja is Operacja.W and k.obiekt.proces == "SO2":
        return _sprawdz_wykonanie_wdrozenia(k)
    if k.operacja is not Operacja.A:
        return []
    u, o, role = k.uzytkownik, k.obiekt, k.role
    so = o.proces or "WF-09"
    oceny: list[Ocena] = []

    # Zasada ogólna (WF-09): nikt nie zatwierdza operacji, którą sam zainicjował.
    if u.id in o.zatwierdzone_przez:
        oceny.append(_nie(so, "użytkownik już zatwierdził tę operację"))
    if o.autor_id == u.id:
        oceny.append(_nie(so, "użytkownik nie może zatwierdzić operacji, którą sam zainicjował"))
    else:
        oceny.append(_ok(so, "zatwierdzający jest inną osobą niż autor"))

    zespoly = _zespoly_uzytkownika(u)
    if o.proces == "SO1":
        if "T1" not in role:
            oceny.append(_nie("SO1", "zmianę w kodzie zatwierdza programista"))
        elif o.zespol not in zespoly:
            gdzie = "zespołu projektu" if o.zasob == "Z4" else "zespołu właściciela modułu"
            oceny.append(_nie("SO1", f"zatwierdzający musi być z {gdzie} ({o.zespol})"))
    elif o.proces == "SO2":
        if not ({"T1", "T5"} & set(role)):
            oceny.append(_nie("SO2", "wdrożenie zatwierdza PO lub inny programista zespołu"))
        elif o.zespol not in zespoly:
            oceny.append(_nie("SO2", f"zatwierdzający musi być z zespołu {o.zespol}"))
    elif o.proces == "SO5":
        if o.dotyczy_osoby_id == u.id:
            oceny.append(_nie("SO5", "nikt nie zatwierdza zmiany własnego wynagrodzenia"))
    elif o.proces == "SO9":
        if "T3" not in role:
            oceny.append(_nie("SO9", "odbiór testów zatwierdza tester"))
    return oceny
