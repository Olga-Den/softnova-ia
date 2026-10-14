"""Zasoby informacyjne organizacji – tabela 3.7."""
from dostep.model import Klasa, Zasob

_K1, _K2, _K3, _K4 = Klasa.KW1, Klasa.KW2, Klasa.KW3, Klasa.KW4

ZASOBY: dict[str, Zasob] = {z.id: z for z in [
    Zasob("Z1", "strona internetowa i blog", _K1, False, "kierownik marketingu"),
    Zasob("Z2", "intranet (wiki)", _K2, False, "office manager"),
    Zasob("Z3", "system zadań", _K2, False, "lider IT wewnętrznego"),
    Zasob("Z4", "repozytoria projektów klienckich", _K3, False, "lider plemienia A"),
    Zasob("Z5", "repozytorium produktu SaaS", _K3, False, "lider plemienia B"),
    Zasob("Z6", "system CI/CD", _K3, False, "lider DevOps/SRE"),
    Zasob("Z7", "środowiska testowe", _K2, False, "lider DevOps/SRE"),
    Zasob("Z8", "produkcja SaaS z bazą klientów", _K4, True, "lider DevOps/SRE"),
    Zasob("Z9", "menedżer sekretów", _K4, False, "lider bezpieczeństwa"),
    Zasob("Z10", "CRM", _K3, True, "dyrektor sprzedaży"),
    Zasob("Z11", "system wsparcia klienta", _K3, True, "kierownik wsparcia"),
    Zasob("Z12", "system finansowo-księgowy", _K3, True, "główna księgowa"),
    Zasob("Z13", "system kadrowo-płacowy", _K4, True, "kierownik HR"),
    Zasob("Z14", "system rekrutacyjny", _K3, True, "kierownik HR"),
    Zasob("Z15", "repozytorium umów i NDA", _K3, True, "prawnik"),
    Zasob("Z16", "dzienniki zdarzeń i SIEM", _K3, True, "lider bezpieczeństwa"),
    Zasob("Z17", "system zarządzania dostępem (IAM)", _K4, True, "lider bezpieczeństwa"),
]}


def zasob(id_zasobu: str) -> Zasob:
    return ZASOBY[id_zasobu]
