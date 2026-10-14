"""Model koncepcyjny (rysunek 3.3) – klasy domenowe bez bazy danych i API (WN-01).

Nazwy w kodzie są po polsku, ale bez polskich znaków (łatwiej je pisać),
komentarze i komunikaty – z polskimi znakami.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from enum import Enum, IntEnum


# ---------------------------------------------------------------------------
# Słowniki (zamknięte zbiory wartości)
# ---------------------------------------------------------------------------

class Operacja(str, Enum):
    """Pięć ogólnych typów operacji (podrozdział 3.5.1)."""
    R = "R"  # odczyt
    W = "W"  # zapis (utworzenie)
    M = "M"  # modyfikacja
    D = "D"  # usunięcie
    A = "A"  # zatwierdzenie operacji zainicjowanej przez inną osobę


def operacje(tekst: str) -> frozenset[Operacja]:
    """Zamienia zapis z macierzy, np. "RWMA", na zbiór operacji."""
    return frozenset(Operacja(znak) for znak in tekst)


class Klasa(IntEnum):
    """Klasy wrażliwości informacji (podrozdział 3.5.2)."""
    KW1 = 1  # publiczne
    KW2 = 2  # wewnętrzne
    KW3 = 3  # poufne
    KW4 = 4  # ściśle poufne


class FormaWspolpracy(str, Enum):
    UMOWA_O_PRACE = "umowa o pracę"
    B2B = "B2B"
    STAZ = "staż"


class TypKonta(str, Enum):
    ZWYKLE = "zwykłe"
    ADMINISTRACYJNE = "administracyjne"
    USLUGOWE = "usługowe"


class TypRoli(str, Enum):
    BAZOWA = "bazowa"
    FUNKCYJNA = "funkcyjna"
    UPRZYWILEJOWANA = "uprzywilejowana"
    USLUGOWA = "usługowa"  # rola konta usługowego (np. potoku CI/CD)


class Urzadzenie(str, Enum):
    FIRMOWE = "firmowe"
    PRYWATNE = "prywatne"


class Siec(str, Enum):
    BIURO = "biuro"
    VPN = "VPN"
    ZEWNETRZNA = "zewnętrzna"


class Wynik(str, Enum):
    ZEZWOL = "zezwól"
    ODMOW = "odmów"


# ---------------------------------------------------------------------------
# Pomocnicze typy atrybutów
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Okres:
    """Przedział czasu [od, do] – dyżur, zastępstwo, aktywna rola w sesji itd."""
    od: datetime
    do: datetime

    def zawiera(self, chwila: datetime, zapas: timedelta = timedelta(0)) -> bool:
        return self.od <= chwila <= self.do + zapas


@dataclass
class Incydent:
    """Incydent lub sprawa IOD przypisana użytkownikowi (źródło: system zgłoszeń)."""
    id: str
    otwarty_o: datetime
    zamkniety_o: datetime | None = None
    dotyczy_danych: bool = False  # incydent dotyczący danych klientów (RE4)

    def otwarty(self, chwila: datetime) -> bool:
        return self.otwarty_o <= chwila and (self.zamkniety_o is None or chwila < self.zamkniety_o)


@dataclass
class Zastepstwo:
    """Zastępstwo wyznaczone przez przełożonego (RE3) – maks. 30 dni."""
    zastepowany_id: str
    okres: Okres


@dataclass
class Przydzial:
    """Uprawnienie z katalogu nadane po zaakceptowanym wniosku – na czas określony (WF-12)."""
    zasob: str
    operacje: frozenset[Operacja]
    typ_rekordu: str | None = None  # None = wszystkie obiekty zasobu
    okres: Okres | None = None      # None = bez terminu
    wniosek_id: str | None = None
    awaryjny: bool = False          # nadany w trybie awaryjnym (zastępstwo 72 h) – wymaga akceptacji po fakcie
    ostatnia_recertyfikacja: datetime | None = None

    def klucz(self) -> str:
        ops = "".join(o.value for o in Operacja if o in self.operacje)
        return f"{self.zasob}:{ops}:{self.typ_rekordu or '*'}"

    def aktywny(self, chwila: datetime) -> bool:
        return self.okres is None or self.okres.zawiera(chwila)


@dataclass
class Upowaznienie:
    """Upoważnienie do przetwarzania danych osobowych (art. 29 RODO) – WT7.

    Źródło: rejestr upoważnień prowadzony przez IOD.
    """
    zakres: frozenset[str]          # zasoby ze znacznikiem DO objęte upoważnieniem
    od: datetime
    do: datetime | None = None      # None = bezterminowo (do odwołania)
    odwolane_o: datetime | None = None

    def wazne(self, chwila: datetime) -> bool:
        if chwila < self.od or (self.do and chwila > self.do):
            return False
        return self.odwolane_o is None or chwila < self.odwolane_o


# ---------------------------------------------------------------------------
# Klasy z diagramu 3.3
# ---------------------------------------------------------------------------

@dataclass
class Uzytkownik:
    """Użytkownik wraz z atrybutami podmiotu z tabeli 3.14 (PIP)."""
    id: str
    imie_nazwisko: str
    rola_funkcyjna: str               # dokładnie jedna rola funkcyjna, np. "T1"
    poziom: str                       # P1–P5
    jednostka: str                    # np. "Plemię A", "Finanse"
    forma: FormaWspolpracy = FormaWspolpracy.UMOWA_O_PRACE
    data_konca_umowy: date | None = None
    stanowisko: str = ""              # np. "COO", "główna księgowa", "lider chaptera"
    zespol: str | None = None         # zespół (squad), np. "A1"
    plemie: str | None = None         # "A", "B", "C"
    chapter: str | None = None        # np. "A-Backend"
    przelozony_id: str | None = None
    aktywny: bool = True

    # --- atrybuty z PIP (tabela 3.14) ---
    oswiadczenia_nda: set[str] = field(default_factory=set)        # klienci (WT1)
    dyzury: list[Okres] = field(default_factory=list)              # grafik dyżurów (RE1, RE2)
    zmiany_wsparcia: list[Okres] = field(default_factory=list)     # grafik wsparcia (RC16)
    incydenty: list[Incydent] = field(default_factory=list)        # przypisane incydenty (RE2, RE4, WT6)
    sprawy_iod: list[Incydent] = field(default_factory=list)       # sprawy IOD (WT5)
    przypisani_klienci: set[str] = field(default_factory=set)      # CRM (RC3)
    zespoly_wspierane: set[str] = field(default_factory=set)       # RC2 – chief architect, agile coach
    jednostki_hrbp: set[str] = field(default_factory=set)          # RC6, RC14
    zespol_tymczasowy: str | None = None                           # czasowe przeniesienie (RC1, RC11)
    poprzedni_zespol: str | None = None                            # RC12
    data_przeniesienia: datetime | None = None                     # RC12
    zastepstwa: list[Zastepstwo] = field(default_factory=list)     # RE3
    wyznaczony_wynagrodzenia_zarzadu: bool = False                 # RC15
    przydzialy: list[Przydzial] = field(default_factory=list)      # uprawnienia z katalogu
    role_uprzywilejowane: set[str] = field(default_factory=set)    # role, które może aktywować w sesji
    wlasciciel_zasobow: set[str] = field(default_factory=set)      # rola właściciela zasobu (tab. 3.11)
    upowaznienie: Upowaznienie | None = None                       # WT7 – rejestr upoważnień (IOD)
    kierownik_umowy_id: str | None = None                          # kto zawarł umowę B2B (recertyfikacja co 3 mies.)
    nieobecnosci: list[Okres] = field(default_factory=list)        # urlopy – akceptacja przechodzi wyżej (WN-07)
    ostatnia_aktywnosc: datetime | None = None                     # blokada po 45 dniach
    ostatnie_uzycie: dict[str, datetime] = field(default_factory=dict)  # klucz uprawnienia → ostatnie użycie
    data_zatrudnienia: datetime | None = None

    def nieobecny(self, chwila: datetime) -> bool:
        return any(o.zawiera(chwila) for o in self.nieobecnosci)


@dataclass
class Konto:
    """Konto użytkownika – zwykłe, administracyjne lub usługowe (WF-03, WF-13)."""
    id: str
    uzytkownik_id: str
    typ: TypKonta = TypKonta.ZWYKLE   # dla konta usługowego uzytkownik_id = właściciel konta
    aktywne: bool = True
    rola: str | None = None           # rola konta usługowego, np. "USL_CICD"
    zablokowane_o: datetime | None = None
    powod_blokady: str = ""


@dataclass
class Sesja:
    """Sesja z rolami uprzywilejowanymi aktywowanymi na czas zadania."""
    id: str
    konto_id: str
    aktywne_role: dict[str, Okres] = field(default_factory=dict)
    numer_zgloszenia: str | None = None  # zgłoszenie albo incydent


@dataclass(frozen=True)
class Zasob:
    """Zasób informacyjny z tabeli 3.7."""
    id: str
    nazwa: str
    klasa: Klasa
    dane_osobowe: bool  # znacznik DO
    wlasciciel: str     # opis stanowiska właściciela


@dataclass
class Obiekt:
    """Konkretny obiekt w zasobie (repozytorium, faktura, rekord kadrowy…).

    Atrybuty zasobu z tabeli 3.14: grupa obiektu (zespół, klient, jednostka),
    typ rekordu, autor operacji.
    """
    id: str
    zasob: str
    nazwa: str
    zespol: str | None = None
    plemie: str | None = None
    jednostka: str | None = None
    klient: str | None = None
    typ_rekordu: str | None = None
    autor_id: str | None = None            # kto zainicjował operację (SO)
    proces: str | None = None              # ograniczenie SO, któremu podlega zatwierdzenie
    kwota: float | None = None             # płatności (RC13, SO3)
    dotyczy_osoby_id: str | None = None    # np. zmiana wynagrodzenia (SO5, RC7)
    komisja: set[str] = field(default_factory=set)  # komisja rekrutacyjna (RC6)
    obslugujacy_id: str | None = None      # zgłoszenie w Z11 (RC4)
    aktywna_oferta: bool = False           # klient z aktywną ofertą (RC3)
    termin_przechowywania: date | None = None  # RC19
    zatwierdzone_przez: list[str] = field(default_factory=list)  # kto zatwierdził (A) – historia obiektu (SO)
    zrodlo_id: str | None = None           # np. wydanie w Z8 → zatwierdzone wdrożenie w Z6 (SO2)


@dataclass(frozen=True)
class Srodowisko:
    """Atrybuty środowiska: czas, urządzenie, sieć."""
    czas: datetime
    urzadzenie: Urzadzenie = Urzadzenie.FIRMOWE
    siec: Siec = Siec.BIURO
    interaktywne: bool = True   # False – żądanie automatu (konto usługowe)


@dataclass(frozen=True)
class Zadanie:
    """Żądanie dostępu przekazywane przez PEP do PDP."""
    konto_id: str
    operacja: Operacja
    obiekt_id: str
    srodowisko: Srodowisko
    sesja_id: str | None = None


@dataclass
class Decyzja:
    """Decyzja PDP z uzasadnieniem (WF-05, WN-02)."""
    wynik: Wynik
    krok: int                          # krok algorytmu z podrozdziału 3.5.6, który rozstrzygnął
    uzasadnienie: list[str]            # czytelne zdania
    reguly: list[str]                  # identyfikatory reguł (rozstrzygające lub spełnione)
    zrodlo: str = ""                   # skąd uprawnienie (rola, sesja, katalog)
    sygnaly: list[str] = field(default_factory=list)  # alarmy i powiadomienia (WF-18)

    @property
    def zezwolono(self) -> bool:
        return self.wynik is Wynik.ZEZWOL

    def __str__(self) -> str:
        return f"{self.wynik.value.upper()} (krok {self.krok}): " + "; ".join(self.uzasadnienie)
