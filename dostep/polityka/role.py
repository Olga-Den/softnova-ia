"""Katalog ról (tabela 3.8) i role uprzywilejowane (tabela 3.11)."""
from dataclasses import dataclass

from dostep.model import TypRoli


@dataclass(frozen=True)
class Rola:
    id: str
    nazwa: str
    typ: TypRoli
    dziedziczy: tuple[str, ...] = ()          # hierarchia ograniczona (podrozdział 3.5.3)
    # tylko dla ról uprzywilejowanych:
    zasob: str | None = None                   # którego systemu dotyczy
    kto_moze: tuple[str, ...] = ()             # role funkcyjne, które mogą ją uzyskać
    maks_godzin: int | None = None             # maksymalny czas aktywacji w sesji
    wymaga_zgloszenia: bool = False            # numer zgłoszenia / incydentu przy aktywacji
    wymaga_akceptacji_wlasciciela: bool = False


_B, _F, _U, _S = TypRoli.BAZOWA, TypRoli.FUNKCYJNA, TypRoli.UPRZYWILEJOWANA, TypRoli.USLUGOWA

_ROLE_FUNKCYJNE = [
    ("T1", "programista", ("RB", "T2")),   # programista dziedziczy rolę stażysty-programisty
    ("T2", "stażysta-programista", ("RB",)),
    ("T3", "tester", ("RB",)),
    ("T4", "projektant UX / analityk", ("RB",)),
    ("T5", "Product Owner", ("RB",)),
    ("T6", "lider plemienia", ("RB",)),
    ("T7", "chief architect", ("RB",)),
    ("T8", "agile coach", ("RB",)),
    ("T9", "DevOps/SRE", ("RB",)),
    ("T10", "specjalista bezpieczeństwa", ("RB",)),
    ("T11", "administrator IT", ("RB",)),
    ("T12", "analityk danych / BI", ("RB",)),
    ("B1", "zarząd", ("RB",)),
    ("B2", "prawnik", ("RB",)),
    ("B3", "Inspektor Ochrony Danych", ("RB",)),
    ("B4", "account manager", ("RB",)),
    ("B5", "presales", ("RB",)),
    ("B6", "wsparcie klienta", ("RB",)),
    ("B7", "księgowy", ("RB",)),
    ("B8", "kontroler", ("RB",)),
    ("B9", "HR business partner", ("RB",)),
    ("B10", "rekruter", ("RB",)),
    ("B11", "specjalista kadr i płac", ("RB",)),
    ("B12", "marketing", ("RB",)),
    ("B13", "administracja biura", ("RB",)),
]


def _role_administratorow() -> list[Rola]:
    """Role administratorów systemów – po jednej na zasób (tabela 3.11)."""
    role = []
    for nr in range(1, 18):
        z = f"Z{nr}"
        if 4 <= nr <= 9:
            kto, godz, zgl, akc = ("T9",), 8, False, False
        elif z == "Z16":
            kto, godz, zgl, akc = ("T10",), 8, True, False
        elif z in ("Z13", "Z17"):
            kto, godz, zgl, akc = ("T11",), 8, True, True
        else:
            kto, godz, zgl, akc = ("T11",), 8, True, False
        role.append(Rola(f"ADM_{z}", f"administrator {z}", _U, zasob=z, kto_moze=kto,
                         maks_godzin=godz, wymaga_zgloszenia=zgl,
                         wymaga_akceptacji_wlasciciela=akc))
    return role


ROLE: dict[str, Rola] = {r.id: r for r in [
    Rola("RB", "rola bazowa", _B),
    *[Rola(i, n, _F, d) for i, n, d in _ROLE_FUNKCYJNE],
    *_role_administratorow(),
    # Rola awaryjna produkcji: krótszy czas, obowiązkowy numer incydentu, alarm przy każdym użyciu.
    Rola("AWARYJNA_Z8", "rola awaryjna produkcji", _U, zasob="Z8", kto_moze=("T9", "T1"),
         maks_godzin=4, wymaga_zgloszenia=True),
    # Konto usługowe potoku CI/CD (uzupełnienie Z2.1): wykonuje zatwierdzone wdrożenia (SO2).
    Rola("USL_CICD", "konto usługowe potoku CI/CD", _S),
]}


def rola(id_roli: str) -> Rola:
    return ROLE[id_roli]


def role_efektywne(rola_funkcyjna: str) -> list[str]:
    """Rola funkcyjna wraz z rolami dziedziczonymi (RB, a dla T1 także T2)."""
    wynik, do_odwiedzenia = [], [rola_funkcyjna]
    while do_odwiedzenia:
        r = do_odwiedzenia.pop(0)
        if r not in wynik:
            wynik.append(r)
            do_odwiedzenia.extend(ROLE[r].dziedziczy)
    return wynik


def czy_uprzywilejowana(id_roli: str) -> bool:
    return ROLE[id_roli].typ is TypRoli.UPRZYWILEJOWANA
