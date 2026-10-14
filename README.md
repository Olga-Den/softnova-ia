# SoftNova IAM – model zarządzania dostępem

Prototyp do pracy inżynierskiej (PWr, W4): hybrydowy model RBAC + ABAC (wariant rolocentryczny)
z rozdziałem obowiązków, dla organizacji modelowej SoftNova sp. z o.o.
Specyfikacja: rozdział 3 pracy i załączniki 1–3.

## Stan

| Etap | Zakres | Stan |
|---|---|---|
| E1–E2 | model (rys. 3.3), polityka jako dane, PDP, reguły WT/RC/RE, SoD SS/SO, testy SZ1–SZ10 | gotowe |
| E3 | WT7 (upoważnienie RODO), konto usługowe CI/CD, wnioski, sesje, tryb awaryjny, zdarzenia kadrowe, recertyfikacja | gotowe |
| E4 | generator 199 osób (Z1.1–Z1.3, tab. 3.8), stan „przed” (3.2), M4 i M5, eksport CSV | gotowe |
| E5–E7 | baza (PostgreSQL / SQLite, 21 tabel, dziennik chroniony wyzwalaczem), API FastAPI, strona www, Docker Compose, ERD | gotowe |
| E8 | metryki M1–M10 – wszystkie spełnione; raport do rozdz. 5 (`dokumentacja/wyniki_metryk/metryki.md`) | gotowe |

## Struktura

```
dostep/                 rdzeń – czysty Python, bez bazy i API (WN-01)
  model.py              klasy z diagramu 3.3
  polityka/             zasoby (3.7), role (3.8, 3.11), macierz (Z2.1–Z2.2), katalog (Z2.3)
  reguly.py             WT1–WT6, RC1–RC19, RE1–RE4, SO1–SO9
  pdp.py                punkt decyzyjny – kolejność z podrozdziału 3.5.6
  sod_statyczne.py      SS1–SS5 przy przypisaniu roli
  dziennik.py           dziennik tylko do dopisywania, łańcuch skrótów SHA-256
  rejestr.py            źródło atrybutów (PIP) w pamięci
  przyklad.py           przykładowa organizacja (kilkanaście osób)
  scenariusze.py        SZ1–SZ10 i zwykła praca jako dane
  system.py             fasada: PEP, dziennik, sygnały, zadania przeglądu
  wnioski.py            wnioski (tab. 3.9, SO6) i zmiana katalogu (SO8)
  sesje.py              role uprzywilejowane w sesji, tryb awaryjny, zastępstwa (RE3)
  cykl_zycia.py         zdarzenia kadrowe (tab. 3.18), blokady 45/90 dni
  recertyfikacja.py     recertyfikacja (12/6/3 mies.) i wykazy uprawnień
  pokaz_procesow.py     pokaz procesów krok po kroku
  organizacja.py        generator pełnej organizacji – 199 osób
  stan_przed.py         stan „przed” z podrozdziału 3.2, metryki M4 i M5
  pokaz_organizacji.py  zestawienie organizacji i eksport CSV
  metryki.py            metryki M1–M10 (tabela 3.20)
  raport_metryk.py      raport metryk: Markdown + CSV
  __main__.py           pokaz z wiersza poleceń
aplikacja/               powłoka demonstracyjna (E5–E7)
  baza.py               schemat bazy, zapis/odczyt stanu, wyzwalacz chroniący dziennik
  stan.py               stan aplikacji, zegar symulowany
  api.py                API REST (FastAPI)
  strony.py, szablony/  strona www do prezentacji
  erd.py                diagram ERD ze schematu
  pomiar_api.py         pomiar czasu żądania przez API (M7)
dokumentacja/           erd.png/.svg/.mmd/.dot, wyniki_metryk/ (raport M1–M10 + CSV)
testy/                  pytest: scenariusze, reguły, procesy, organizacja, aplikacja
Dockerfile, docker-compose.yml
```

## Uruchomienie

Pełna instrukcja instalacji (Python, VS Code, Git, Docker): **[INSTALACJA.md](INSTALACJA.md)**.

```bash
python -m dostep              # pokaz: wszystkie scenariusze przez PDP
python -m dostep SZ1          # jeden scenariusz z uzasadnieniem
python -m dostep anna R repo_y  # własne żądanie: konto, operacja, obiekt
python -m dostep procesy      # pokaz procesów: wnioski, sesje, tryb awaryjny, kadry, recertyfikacja
python -m dostep dziennik     # wpisy dziennika po pokazie procesów
python -m dostep organizacja  # pełna organizacja (199 osób), M4 i M5; dodaj --csv wyniki, by zapisać CSV
python -m dostep metryki      # metryki M1–M10 → wyniki/metryki.md (raport do rozdz. 5)
python -m pytest              # testy automatyczne (wymaga: pip install -r requirements-dev.txt)
docker compose up --build     # aplikacja www z PostgreSQL → http://localhost:8000
uvicorn aplikacja.main:app    # aplikacja www bez Dockera (SQLite)
```

## Konwencje

- Wszystko po polsku; nazwy w kodzie bez polskich znaków (`uzytkownik`, `zasob`),
  komentarze i komunikaty z polskimi znakami.
- Każda decyzja ma uzasadnienie z identyfikatorami reguł (WF-05, WN-02).
- Przypadki testowe są danymi (`dostep/scenariusze.py`) – ten sam zbiór posłuży do metryk.
