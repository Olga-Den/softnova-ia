"""Katalog uprawnień wnioskowalnych – tabela Z2.3.

Pozycja katalogu wyznacza maksimum tego, co rola może w ogóle uzyskać ponad macierz.
Sposób uzyskania:
  * "wniosek" – tylko po zaakceptowanym wniosku (Przydzial na koncie użytkownika),
  * "RE1", "RE2", "RE4" – automatycznie, gdy działa reguła rozszerzająca
    (lub po zaakceptowanym wniosku),
  * "WT5", "WT6" – automatycznie, gdy spełniony jest warunek twardy (sprawa IOD, incydent),
  * "sesja" – przez aktywację roli uprzywilejowanej w sesji (role ADM_*).
Wniosek spoza katalogu jest odrzucany automatycznie (WF-06).
"""
from dataclasses import dataclass

from dostep.model import Operacja, operacje
from dostep.polityka.zasoby import ZASOBY


@dataclass(frozen=True)
class PozycjaKatalogu:
    rola: str
    zasob: str
    operacje: frozenset[Operacja]
    sposob: str
    typ_rekordu: str | None = None
    opis: str = ""

    def obejmuje(self, zasob: str, operacja: Operacja, typ_rekordu: str | None) -> bool:
        return (self.zasob == zasob and operacja in self.operacje
                and (self.typ_rekordu is None or self.typ_rekordu == typ_rekordu))


def _k(rola, zasob, ops, sposob, typ=None, opis=""):
    return PozycjaKatalogu(rola, zasob, operacje(ops), sposob, typ, opis)


KATALOG: list[PozycjaKatalogu] = [
    # T1 programista
    _k("T1", "Z8", "RM", "RE1", "infrastruktura", "infrastruktura produkcji – dyżur"),
    _k("T1", "Z8", "R", "RE4", "dane_klientow", "dane klientów – incydent dotyczący danych"),
    _k("T1", "Z9", "R", "wniosek", "sekret_projektu", "sekrety projektu"),
    _k("T1", "Z16", "R", "RE2", "dziennik_projektu", "dzienniki projektu – dyżur lub incydent"),
    # T2 stażysta-programista
    _k("T2", "Z6", "W", "wniosek", opis="zapis w CI/CD"),
    _k("T2", "Z7", "W", "wniosek", opis="zapis w środowiskach testowych"),
    # T9 DevOps/SRE – dzienniki przy dyżurze/incydencie (macierz: R [RE2])
    _k("T9", "Z16", "R", "RE2", opis="dzienniki – dyżur lub incydent"),
    # T10 specjalista bezpieczeństwa – dane klientów tylko przy przypisanym incydencie
    *[_k("T10", z, "R", "WT6", opis="poufne dane klientów – incydent")
      for z in ("Z4", "Z10", "Z11", "Z15")],
    _k("T10", "Z8", "R", "WT6", "dane_klientow", "dane klientów w produkcji – incydent"),
    # B3 IOD – zasoby ze znacznikiem DO i Z16 przy otwartej sprawie
    *[_k("B3", z.id, "R", "WT5", opis="sprawa IOD")
      for z in ZASOBY.values() if z.dane_osobowe or z.id == "Z16"],
]

# Role uprzywilejowane dostępne „w sesji” (informacyjnie – kto może je aktywować,
# określa pole kto_moze w polityka/role.py).
KATALOG_ROL_W_SESJI: dict[str, list[str]] = {
    "T9": [f"ADM_Z{n}" for n in range(4, 10)] + ["AWARYJNA_Z8"],
    "T10": ["ADM_Z16"],
    "T11": [f"ADM_Z{n}" for n in (1, 2, 3, 10, 11, 12, 13, 14, 15, 17)],
    "T1": ["AWARYJNA_Z8"],
}


def pozycje_dla(rola: str) -> list[PozycjaKatalogu]:
    return [p for p in KATALOG if p.rola == rola]
