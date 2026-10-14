"""Raport metryk M1–M10 do rozdziału 5: tabela zbiorcza, metodyka, szczegóły (Markdown + CSV)."""
from __future__ import annotations

import csv
import os
import platform
import sys
import time
from datetime import datetime
from pathlib import Path

from dostep.metryki import WynikMetryki, wszystkie

WYMAGANIA = {"M1": "WF-01–WF-14", "M2": "WF-08, WF-09", "M3": "WF-16", "M4": "WN-03", "M5": "WN-03", "M6": "WN-07",
             "M7": "WN-04", "M8": "WN-07", "M9": "WF-18, WN-05", "M10": "WF-10"}


def _srodowisko() -> str:
    return (f"Python {platform.python_version()}, {platform.system()} {platform.release()}, "
            f"{platform.machine()}, {os.cpu_count()} rdzeni logicznych; procesor: {platform.processor() or 'nieznany'}")


def _tabela_md(naglowek: list[str], wiersze: list[list]) -> str:
    linie = ["| " + " | ".join(naglowek) + " |", "|" + "---|" * len(naglowek)]
    linie += ["| " + " | ".join(str(x).replace("|", "/") for x in w) + " |" for w in wiersze]
    return "\n".join(linie)


def markdown(wyniki: list[WynikMetryki], czas_s: float) -> str:
    czesci = [
        "# Wyniki metryk oceny modelu (tabela 3.20)",
        "",
        f"Wygenerowano: {datetime.now():%Y-%m-%d %H:%M} poleceniem `python -m dostep metryki` "
        f"(czas obliczeń {czas_s:.0f} s). Środowisko: {_srodowisko()}.",
        "",
        "Dane: przykładowa organizacja (scenariusze SZ1–SZ10, ZP01–ZP23) oraz pełna organizacja SoftNova – 199 osób, "
        "generator deterministyczny (ziarno 2026), zegar modelu 2026-10-14 10:00. Wyniki M1–M6 i M8–M10 są powtarzalne; "
        "M7 zależy od komputera.",
        "",
        "## Tabela zbiorcza",
        "",
        _tabela_md(["ID", "Metryka", "Wynik", "Oczekiwana wartość", "Spełnione", "Wymagania"],
                   [[w.id, w.nazwa, w.wynik, w.oczekiwane,
                     "–" if w.spelnione is None else ("tak" if w.spelnione else "**nie**"), WYMAGANIA[w.id]]
                    for w in wyniki]),
        "",
    ]
    for w in wyniki:
        czesci += [f"## {w.id} – {w.nazwa}", "", f"**Wynik:** {w.wynik} (oczekiwane: {w.oczekiwane}).", "",
                   f"**Metodyka.** {w.metodyka}", ""]
        if w.szczegoly:
            wiersze = w.szczegoly if len(w.szczegoly) <= 40 else w.szczegoly[:40] + [["…"] * len(w.naglowek)]
            czesci += [_tabela_md(w.naglowek, wiersze), ""]
        for u in w.uwagi:
            czesci += [f"- {u}"]
        if w.uwagi:
            czesci.append("")
    return "\n".join(czesci)


def zapisz(wyniki: list[WynikMetryki], folder: Path, czas_s: float) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "metryki.md").write_text(markdown(wyniki, czas_s), encoding="utf-8")

    def plik(nazwa, naglowek, wiersze):
        with open(folder / nazwa, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f, delimiter=";")
            w.writerow(naglowek)
            w.writerows(wiersze)

    plik("metryki.csv", ["ID", "metryka", "wynik", "oczekiwane", "spełnione", "wymagania"],
         [[w.id, w.nazwa, w.wynik, w.oczekiwane, w.spelnione, WYMAGANIA[w.id]] for w in wyniki])
    for w in wyniki:
        if w.szczegoly:
            plik(f"{w.id.lower()}_szczegoly.csv", w.naglowek, w.szczegoly)
        if hasattr(w, "dane_proby"):
            plik("m2_proby.csv", ["rodzaj", "ograniczenie", "próba", "zablokowana"], w.dane_proby)
        if hasattr(w, "czasy_pdp"):
            plik("m7_czasy_pdp_ms.csv", ["czas_ms"], [[f"{c:.4f}".replace(".", ",")] for c in w.czasy_pdp])


def main(argv: list[str]) -> int:
    api = "--bez-api" not in argv
    folder = Path(argv[argv.index("--wyniki") + 1]) if "--wyniki" in argv else Path("wyniki")
    baza_api = argv[argv.index("--baza-api") + 1] if "--baza-api" in argv else None
    print("Liczę metryki M1–M10 (ok. 15–30 s)…", flush=True)
    t0 = time.time()
    wyniki = wszystkie(api=api, baza_api=baza_api)
    czas_s = time.time() - t0
    szer = max(len(w.wynik) for w in wyniki)
    print()
    for w in wyniki:
        znak = "✔" if w.spelnione else ("–" if w.spelnione is None else "✘")
        print(f"{znak} {w.id:4} {w.nazwa:32} {w.wynik:{szer}}   oczekiwane: {w.oczekiwane}")
    zapisz(wyniki, folder, czas_s)
    print(f"\nRaport: {(folder / 'metryki.md').resolve()}  (+ pliki CSV w tym samym folderze)")
    return 0 if all(w.spelnione is not False for w in wyniki) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
