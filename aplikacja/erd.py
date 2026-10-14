"""Generator diagramu ERD (do rozdziału 4) prosto ze schematu bazy – diagram jest zawsze zgodny z kodem.

Uruchomienie:  python -m aplikacja.erd [folder]
Tworzy:        erd.dot (Graphviz), erd.mmd (Mermaid) oraz erd.png i erd.svg, jeśli zainstalowano Graphviz (`dot`).
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

from aplikacja.baza import meta

GRUPY = {
    "Polityka (tab. 3.7, 3.8, Z2.1–Z2.3)": ["zasoby", "role", "uprawnienia_rol", "katalog"],
    "Tożsamość i przypisania": ["uzytkownicy", "konta", "przypisania_uprzywilejowane", "wlasciciele_zasobow",
                                "upowaznienia", "przydzialy", "sesje", "sesje_role"],
    "Obiekty chronione": ["obiekty"],
    "Procesy": ["wnioski", "wymagania_wnioskow", "prosby", "zadania_przegladu", "pozycje_recertyfikacji"],
    "Rozliczalność": ["dziennik", "sygnaly", "ustawienia"],
}
KOLORY = ["#e3ecfb", "#e6f4ea", "#fdf3d8", "#f3e8fb", "#fbe4e4"]


def _typ(kolumna) -> str:
    nazwa = type(kolumna.type).__name__.lower()
    return {"string": "varchar", "variant": "json", "json": "json", "datetime": "timestamp"}.get(nazwa, nazwa)


def dot() -> str:
    linie = ['digraph ERD {', '  graph [rankdir=LR, fontname="Helvetica", fontsize=11, nodesep=0.35, ranksep=0.9];',
             '  node [shape=plain, fontname="Helvetica", fontsize=10];', '  edge [arrowhead=crow, arrowtail=tee, dir=both, color="#555555"];']
    for i, (grupa, tabele) in enumerate(GRUPY.items()):
        linie.append(f'  subgraph cluster_{i} {{ label="{grupa}"; style="rounded,dashed"; color="#999999";')
        for nazwa in tabele:
            t = meta.tables[nazwa]
            wiersze = "".join(
                f'<tr><td align="left" port="{c.name}">{"<b>" if c.primary_key else ""}{c.name}{"</b>" if c.primary_key else ""}'
                f'{" (FK)" if c.foreign_keys else ""}</td><td align="left"><font color="#666666">{_typ(c)}</font></td></tr>'
                for c in t.columns)
            linie.append(f'    {nazwa} [label=<<table border="0" cellborder="1" cellspacing="0" cellpadding="3">'
                         f'<tr><td colspan="2" bgcolor="{KOLORY[i]}"><b>{nazwa}</b></td></tr>{wiersze}</table>>];')
        linie.append("  }")
    for t in meta.tables.values():
        for fk in t.foreign_key_constraints:
            cel = fk.elements[0].column.name
            linie.append(f"  {fk.referred_table.name}:{cel}:e -> {t.name}:{fk.column_keys[0]}:w;")
    linie.append("}")
    return "\n".join(linie)


def mermaid() -> str:
    linie = ["erDiagram"]
    for t in meta.tables.values():
        linie.append(f"  {t.name} {{")
        for c in t.columns:
            klucz = " PK" if c.primary_key else (" FK" if c.foreign_keys else "")
            linie.append(f"    {_typ(c)} {c.name}{klucz}")
        linie.append("  }")
    for t in meta.tables.values():
        for fk in t.foreign_key_constraints:
            linie.append(f'  {fk.referred_table.name} ||--o{{ {t.name} : "{",".join(fk.column_keys)}"')
    return "\n".join(linie)


def main(folder: str = ".") -> None:
    cel = Path(folder)
    cel.mkdir(parents=True, exist_ok=True)
    (cel / "erd.dot").write_text(dot(), encoding="utf-8")
    (cel / "erd.mmd").write_text(mermaid(), encoding="utf-8")
    print(f"Zapisano {cel / 'erd.dot'} i {cel / 'erd.mmd'} ({len(meta.tables)} tabel)")
    if shutil.which("dot"):
        for fmt in ("png", "svg"):
            subprocess.run(["dot", f"-T{fmt}", "-Gdpi=150", str(cel / "erd.dot"), "-o", str(cel / f"erd.{fmt}")], check=True)
        print(f"Zapisano {cel / 'erd.png'} i {cel / 'erd.svg'}")
    else:
        print("Graphviz nie jest zainstalowany – plik erd.mmd można wkleić na mermaid.live, by uzyskać obraz.")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else ".")
