"""Macierz uprawnień przyznanych – tabele Z2.1 i Z2.2 (oraz uprawnienia roli bazowej).

Każdy wpis mówi: rola X ma operacje O w zasobie Z, pod warunkiem spełnienia reguł
zawężających / warunków twardych wymienionych w nawiasie kwadratowym w tabeli.
Uprawnienia oznaczone w tabelach jako „kat.” nie są tu wpisane – są w katalogu
(katalog.py), bo nie wynikają z roli.

Ograniczenia SO są podane informacyjnie (kolumna `so`) – PDP stosuje je na podstawie
procesu, któremu podlega obiekt, więc działają niezależnie od wpisu.
"""
from dataclasses import dataclass

from dostep.model import Operacja, operacje

# Pseudo-rola dla wiersza „każda rola + poziom P2/P3” z tabeli Z2.2.
POZIOM_P2_P3 = "P2/P3"


@dataclass(frozen=True)
class Wpis:
    rola: str
    zasob: str
    operacje: frozenset[Operacja]
    reguly: tuple[str, ...] = ()               # WT i RC przypisane do wpisu
    so: tuple[str, ...] = ()                   # ograniczenia SoD (informacyjnie)
    typy_rekordu: frozenset[str] | None = None  # zawężenie do typów rekordu (np. W* testera)
    tylko_plemie: str | None = None            # np. programiści plemienia B w Z11
    uwaga: str = ""

    def obejmuje(self, operacja: Operacja, typ_rekordu: str | None) -> bool:
        if operacja not in self.operacje:
            return False
        if self.typy_rekordu is not None and typ_rekordu not in self.typy_rekordu:
            return False
        return True


def _w(rola, zasob, ops, reguly="", so="", typy=None, plemie=None, uwaga=""):
    return Wpis(rola, zasob, operacje(ops), tuple(reguly.split()), tuple(so.split()),
                frozenset(typy) if typy else None, plemie, uwaga)


MACIERZ: list[Wpis] = [
    # --- Rola bazowa (podrozdział 3.5.3) ---
    _w("RB", "Z1", "R"),
    _w("RB", "Z2", "R"),
    _w("RB", "Z3", "RWM", "RC1", uwaga="zadania własnej jednostki"),
    _w("RB", "Z17", "RW", typy={"wniosek"}, uwaga="składanie i podgląd własnych wniosków"),

    # --- Tabela Z2.1: pion technologiczny ---
    _w("T1", "Z4", "RWMA", "RC1 WT1", "SO1"),
    _w("T1", "Z5", "RWMA", "", "SO1"),
    _w("T1", "Z6", "RWA", "RC1", "SO2"),
    _w("T1", "Z7", "RW", "RC1"),
    _w("T1", "Z11", "RW", "RC4", plemie="B", uwaga="zgłoszenia przekazane zespołowi"),

    _w("T2", "Z4", "RW", "RC1 RC9 WT1"),
    _w("T2", "Z5", "RW", "RC9"),
    _w("T2", "Z6", "R"),
    _w("T2", "Z7", "R", "RC1"),

    _w("T3", "Z4", "RA", "RC1 WT1", "SO9"),
    _w("T3", "Z4", "W", "RC1 WT1", typy={"test_automatyczny"}, uwaga="tylko testy automatyczne"),
    _w("T3", "Z5", "RA", "", "SO9"),
    _w("T3", "Z5", "W", "", typy={"test_automatyczny"}, uwaga="tylko testy automatyczne"),
    _w("T3", "Z6", "RW", "RC1"),
    _w("T3", "Z7", "RWM", "RC1"),

    _w("T4", "Z4", "R", "RC1 WT1"),
    _w("T4", "Z5", "R"),
    _w("T4", "Z7", "R", "RC1"),

    _w("T5", "Z3", "A", "RC1"),
    _w("T5", "Z4", "R", "RC1 WT1"),
    _w("T5", "Z5", "R"),
    _w("T5", "Z6", "A", "RC1", "SO2"),
    _w("T5", "Z7", "R", "RC1"),

    _w("T6", "Z3", "R", "RC1", uwaga="zadania całego plemienia"),
    _w("T6", "Z4", "R", "WT1"),
    _w("T6", "Z5", "R"),
    _w("T6", "Z6", "R"),
    _w("T6", "Z7", "R"),

    _w("T7", "Z4", "R", "RC2 WT1"),
    _w("T7", "Z5", "R", "RC2"),
    _w("T7", "Z6", "R", "RC2"),
    _w("T7", "Z7", "R", "RC2"),

    _w("T8", "Z3", "RWM", "RC2"),

    _w("T9", "Z5", "R"),
    _w("T9", "Z6", "RWM"),
    _w("T9", "Z7", "RWM"),

    _w("T10", "Z5", "R"),
    _w("T10", "Z6", "R"),
    _w("T10", "Z7", "R"),
    _w("T10", "Z9", "R", typy={"metadane_sekretu"}, uwaga="tylko metadane sekretów"),
    _w("T10", "Z16", "R"),
    _w("T10", "Z16", "M", typy={"regula_siem"}, uwaga="reguły i alerty SIEM, nie wpisy dziennika"),

    # --- Tabela Z2.2: pozostałe jednostki ---
    _w("B1", "Z10", "R"),
    _w("B1", "Z12", "RA", "RC13", "SO3"),
    _w("B1", "Z13", "A", "RC13", "SO5"),
    _w("B1", "Z14", "R", "RC6"),
    _w("B1", "Z15", "RA", "", "SO7"),

    _w("B2", "Z15", "RWMD", "RC19"),

    _w("B3", "Z15", "R", "RC18"),

    _w("B4", "Z10", "RWM", "RC3"),
    _w("B4", "Z11", "R", "RC3"),
    _w("B4", "Z15", "R", "RC3"),

    _w("B5", "Z10", "RW", "RC3"),

    _w("B6", "Z10", "R", "RC4"),
    _w("B6", "Z11", "RWM", "RC16"),

    _w("B7", "Z12", "RWMA", "RC13", "SO3"),
    _w("B7", "Z15", "R", "RC13"),

    _w("B8", "Z12", "R"),

    _w("B9", "Z13", "RA", "RC13 RC14", "SO4 SO5"),
    _w("B9", "Z14", "R", "RC6"),

    _w("B10", "Z14", "RWMD", "RC19"),

    _w("B11", "Z13", "RWM", "RC15"),

    _w("B12", "Z1", "RWMD"),
    _w("B12", "Z10", "R", "RC10"),

    _w("B13", "Z2", "RWMD"),

    _w("T12", "Z10", "R", "RC17"),
    _w("T12", "Z11", "R", "RC17"),
    _w("T12", "Z12", "R", "RC17"),

    # --- „każda rola + poziom P2/P3” ---
    _w(POZIOM_P2_P3, "Z12", "RA", "RC5", uwaga="faktury jednostki"),
    _w(POZIOM_P2_P3, "Z13", "R", "RC7"),
    _w(POZIOM_P2_P3, "Z14", "R", "RC6"),
]

# --- Role uprzywilejowane: administrator systemu ma R W M D w swoim zasobie ---
for _nr in range(1, 18):
    MACIERZ.append(_w(f"ADM_Z{_nr}", f"Z{_nr}", "RWMD", "WT4"))
MACIERZ.append(_w("AWARYJNA_Z8", "Z8", "RM", uwaga="tryb awaryjny – alarm przy każdym użyciu"))

# --- Konto usługowe CI/CD (uzupełnienie tabeli Z2.1, ustalenie z 14.10.2026) ---
MACIERZ += [
    _w("USL_CICD", "Z6", "R"),
    _w("USL_CICD", "Z8", "W", "", "SO2", typy={"wydanie"}, uwaga="tylko wydanie zatwierdzone wg SO2"),
    _w("USL_CICD", "Z9", "R", typy={"sekret_projektu"}, uwaga="sekrety projektu dla potoku"),
]


def wpisy_dla(rola: str, zasob: str) -> list[Wpis]:
    return [w for w in MACIERZ if w.rola == rola and w.zasob == zasob]
