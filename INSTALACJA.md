# Instrukcja instalacji i pracy z projektem SoftNova IAM

Instrukcja prowadzi od pustego komputera do działającego rdzenia modelu. Główna ścieżka dotyczy
**Windows 10/11**, a różnice dla Linuksa i macOS są zebrane na końcu (część 11).

Etapy 1–6 wystarczają, żeby uruchomić rdzeń. Docker (etap 8) przyda się dopiero przy bazie danych
i aplikacji webowej, więc można go zainstalować później.

---

## 0. Co będzie potrzebne i po co

| Narzędzie | Wersja | Do czego służy | Kiedy potrzebne |
|---|---|---|---|
| **Python** | 3.12 (działa od 3.11) | język, w którym napisany jest cały system | od razu |
| **Visual Studio Code** | najnowsza | edytor kodu z terminalem | od razu |
| **Git** | najnowsza | historia zmian, później wysłanie na GitHub | od razu |
| **Docker Desktop** | najnowsza | baza PostgreSQL i aplikacja w kontenerach, uruchamiane jednym poleceniem | do aplikacji www (część 8a); można też bez Dockera, z SQLite |

Wymagania sprzętowe: 8 GB RAM (16 GB wygodniej, gdy działa Docker) i ok. 10 GB wolnego miejsca na dysku.

> **Ważne – ścieżka do projektu.** Projekt trzymaj w folderze **bez spacji i bez polskich czy
> cyrylicznych liter**, np. `C:\projekty\softnova-iam`. Nie umieszczaj go w
> `C:\Users\<nazwa>\Pulpit` ani w `Dokumenty`, jeśli nazwa użytkownika Windows zawiera znaki
> spoza ASCII. Python, pip i Docker potrafią się wtedy wywracać z niejasnymi błędami.

---

## 1. Instalacja Pythona

1. Wejdź na **https://www.python.org/downloads/** i pobierz **Python 3.12.x** dla Windows
   (przycisk „Download Python 3.12…” albo z listy *Windows installer (64-bit)*).
2. Uruchom instalator i **zanim klikniesz cokolwiek innego**, zaznacz na dole pierwszego okna:
   - ☑ **Add python.exe to PATH** – bez tego polecenie `python` nie zadziała w terminalu,
   - ☑ **Use admin privileges when installing py.exe**.
3. Kliknij **Install Now**.
4. Na końcu, jeśli pojawi się opcja **Disable path length limit**, kliknij ją.
5. Sprawdź instalację. Otwórz **nowe** okno PowerShell (Start → wpisz „PowerShell”) i wpisz:

   ```powershell
   python --version
   ```

   Powinno się pokazać `Python 3.12.x`.

> **Jeśli zamiast wersji otwiera się Microsoft Store:** Ustawienia → Aplikacje → Zaawansowane
> ustawienia aplikacji → **Aliasy wykonywania aplikacji** i wyłącz oba przełączniki „python.exe”
> oraz „python3.exe”. Potem otwórz nowe okno PowerShell.

---

## 2. Instalacja Gita

1. Pobierz instalator z **https://git-scm.com/download/win** (wersja 64-bit).
2. Przechodź przez instalator, zostawiając ustawienia domyślne, z dwiema zmianami:
   - *Choosing the default editor* → wybierz **Use Visual Studio Code as Git's default editor**,
   - *Adjusting the name of the initial branch* → wybierz **Override… → `main`**.
3. Po instalacji w **nowym** oknie PowerShell ustaw swoje dane (będą podpisem pod zmianami):

   ```powershell
   git --version
   git config --global user.name "Olga Denysiuk"
   git config --global user.email "twoj@email"
   ```

---

## 3. Instalacja Visual Studio Code

1. Pobierz z **https://code.visualstudio.com/** i zainstaluj. Na ekranie *Select Additional Tasks*
   zaznacz:
   - ☑ **Add "Open with Code" action to Windows Explorer file context menu**,
   - ☑ **Add "Open with Code" action to Windows Explorer directory context menu**,
   - ☑ **Add to PATH**.
2. Uruchom VS Code i otwórz panel rozszerzeń (**Ctrl+Shift+X**). Zainstaluj:
   - **Python** (wydawca: Microsoft) – razem z nim zainstaluje się *Pylance*,
   - opcjonalnie **Polish Language Pack for Visual Studio Code**, czyli menu po polsku,
   - później, przy etapie z Dockerem: **Docker** (wydawca: Microsoft).
3. Ustaw PowerShell jako domyślny terminal: **Ctrl+Shift+P** → wpisz
   `Terminal: Select Default Profile` → **PowerShell**.

---

## 4. Rozpakowanie projektu

1. Utwórz folder `C:\projekty`.
2. Kliknij paczkę `softnova-iam.zip` prawym przyciskiem → **Wyodrębnij wszystkie…** i jako
   miejsce docelowe wpisz **`C:\projekty`** (samo `C:\projekty`, bez nazwy paczki na końcu).
   Powstanie folder `C:\projekty\softnova-iam` z plikami `README.md`, `INSTALACJA.md`
   i folderami `dostep`, `testy` w środku. Jeśli wyszedł podwójny folder
   `softnova-iam\softnova-iam`, przenieś wewnętrzny o poziom wyżej.
3. Kliknij folder `softnova-iam` prawym przyciskiem → **Open with Code**
   (w Windows 11: *Pokaż więcej opcji* → *Open with Code*).
   Jeśli VS Code zapyta *Do you trust the authors…*, odpowiedz **Yes, I trust the authors**.
4. Otwórz terminal w VS Code: menu **Terminal → New Terminal** albo **Ctrl+`**.
   Terminal startuje od razu w folderze projektu, co widać po `PS C:\projekty\softnova-iam>`.

---

## 5. Środowisko wirtualne Pythona (venv)

Środowisko wirtualne to osobna „kopia” Pythona dla tego projektu. Biblioteki instalowane później
(FastAPI, sterownik PostgreSQL) trafią tylko tam i nie pomieszają się z innymi projektami.
Tworzy się je **raz**.

W terminalu VS Code wpisz:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

Po aktywacji na początku wiersza pojawi się `(.venv)`.

> **Jeśli pojawi się błąd „running scripts is disabled on this system”**, wpisz raz:
> ```powershell
> Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
> ```
> Potwierdź literą `T` (lub `Y`) i ponów `.venv\Scripts\Activate.ps1`.

Następnie powiedz VS Code, żeby używał tego środowiska: **Ctrl+Shift+P** →
`Python: Select Interpreter` → wybierz pozycję z `.venv` (np. `Python 3.12.x ('.venv')`).
Od tej pory każdy nowy terminal w VS Code sam aktywuje `.venv`.

Na koniec zainstaluj narzędzie do testów (przyda się później):

```powershell
python -m pip install --upgrade pip
python -m pip install pytest
```

---

## 6. Pierwsze uruchomienie – pokaz działania rdzenia

Rdzeń nie potrzebuje żadnych bibliotek ani bazy danych, więc działa od razu.

| Polecenie | Co robi |
|---|---|
| `python -m dostep` | przepuszcza wszystkie scenariusze (SZ1–SZ10 i zwykłą pracę) przez PDP i pokazuje decyzje |
| `python -m dostep SZ1` | jeden scenariusz z pełnym uzasadnieniem decyzji |
| `python -m dostep --lista` | konta i obiekty przykładowej organizacji (z nich budujesz własne żądania) |
| `python -m dostep anna R repo_y` | własne żądanie: **konto**, **operacja** (R, W, M, D, A), **obiekt** |
| `python -m dostep procesy` | pokaz procesów krok po kroku: wniosek i akceptacje, rola administratora w sesji, tryb awaryjny, wdrożenie przez potok CI/CD, przeniesienie i odejście pracownika, recertyfikacja |
| `python -m dostep dziennik` | ostatnie wpisy dziennika zdarzeń po pokazie procesów |
| `python -m dostep organizacja` | pełna organizacja SoftNova (199 osób) – zgodność z tab. 3.8 i Z1.1, porównanie ze stanem „przed”, metryki M4 i M5 |
| `python -m dostep metryki` | metryki M1–M10 z tabeli 3.20 – raport `wyniki/metryki.md` (tabele i metodyka do rozdziału 5) oraz pliki CSV; trwa ok. 15–30 s |
| `python -m dostep organizacja --csv wyniki` | to samo + pliki CSV (osoby, uprawnienia ról, stan „przed”, obiekty) w folderze `wyniki` – otwierają się w Excelu |

Przykład:

```text
PS C:\projekty\softnova-iam> python -m dostep anna R repo_y
anna → R na repo_y
  Decyzja: ODMÓW  (krok 1 algorytmu PDP)
    • WT1: brak oświadczenia o poufności wobec klienta Klient Y
    • RC1: obiekt należy do zespołu A2, a użytkownik do A1
```

Jak czytać wynik:
- **Decyzja** to *zezwól* albo *odmów*.
- **Krok** odpowiada kolejności z podrozdziału 3.5.6: 1 – warunki twarde, 2 – reguły zawężające,
  3 – SoD na poziomie obiektu, 4 – uprawnienie z roli, 5 – reguła rozszerzająca/katalog,
  6 – domyślna odmowa.
- **•** to uzasadnienie: identyfikatory reguł i opis, dlaczego są (nie)spełnione.
- **!** to sygnał dla zespołu bezpieczeństwa (próba naruszenia SoD, użycie trybu awaryjnego).

Ostatnia linia `python -m dostep` mówi, ile decyzji jest zgodnych z oczekiwanymi (to późniejsza metryka M1).

---

## 7. Git – zapisywanie postępów

Paczka zip nie zawiera historii Gita, więc repozytorium zakłada się raz:

```powershell
git init
git add .
git commit -m "Rdzeń modelu – wersja startowa"
```

Potem, po każdej sensownej zmianie:

```powershell
git status                 # co się zmieniło
git add .
git commit -m "Krótki opis zmiany"
```

Plik `.gitignore` już wyklucza `.venv` i pliki tymczasowe, więc nie trafią do repozytorium.

**Później – wysłanie na GitHub** (gdy zdecydujesz): załóż na github.com **prywatne** repozytorium
`softnova-iam` *bez* README, a potem:

```powershell
git remote add origin https://github.com/<twoj-login>/softnova-iam.git
git push -u origin main
```

---

## 8. Docker Desktop (potrzebny od etapu z bazą danych)

Docker uruchomi bazę PostgreSQL i aplikację FastAPI jednym poleceniem `docker compose up`.
Na komputerze, na którym będzie prezentacja, nie trzeba wtedy instalować bazy danych ręcznie.

1. **Sprawdź wirtualizację:** Menedżer zadań (Ctrl+Shift+Esc) → Wydajność → Procesor →
   *Wirtualizacja: Włączone*. Jeśli jest *Wyłączone*, trzeba ją włączyć w BIOS/UEFI
   (opcja *Intel VT-x* / *AMD-V* / *SVM*).
2. **Zainstaluj WSL 2:** uruchom PowerShell **jako administrator** (Start → PowerShell → prawy
   przycisk → *Uruchom jako administrator*) i wpisz:

   ```powershell
   wsl --install
   ```

   Uruchom komputer ponownie.
3. Pobierz **Docker Desktop for Windows** z **https://www.docker.com/products/docker-desktop/**
   i zainstaluj. Zostaw zaznaczone **Use WSL 2 instead of Hyper-V**. Uruchom ponownie, jeśli poprosi.
4. Uruchom Docker Desktop. Konto Docker nie jest potrzebne (*Continue without signing in* / *Skip*).
   Poczekaj, aż w lewym dolnym rogu pojawi się *Engine running*.
5. Sprawdź w terminalu:

   ```powershell
   docker --version
   docker compose version
   docker run hello-world
   ```

   Ostatnie polecenie powinno wypisać *Hello from Docker!*.

Docker Desktop zużywa sporo pamięci. Gdy nie pracujesz nad projektem, możesz go zamknąć
(ikona wieloryba przy zegarze → *Quit Docker Desktop*).

---

## 8a. Uruchomienie aplikacji www (baza danych + strona + API)

Aplikację można uruchomić na dwa sposoby. Na prezentację zalecany jest Docker, bo baza PostgreSQL startuje razem
z aplikacją i nic nie trzeba instalować ręcznie.

### Sposób A – Docker (PostgreSQL), jedno polecenie

1. Uruchom Docker Desktop i poczekaj na *Engine running*.
2. W terminalu VS Code, w folderze projektu:

   ```powershell
   docker compose up --build
   ```

   Za pierwszym razem Docker pobierze obrazy Pythona i PostgreSQL (kilka minut, ok. 500 MB).
   Gotowe, gdy pojawi się `Uvicorn running on http://0.0.0.0:8000`.
3. Otwórz w przeglądarce **http://localhost:8000** – strona pokazu. Dokumentacja API: **http://localhost:8000/docs**.
4. Zatrzymanie: **Ctrl+C** w terminalu. Ponowne uruchomienie: `docker compose up` (dane zostają w bazie).

| Polecenie | Co robi |
|---|---|
| `docker compose up --build` | buduje i uruchamia bazę i aplikację (po zmianach w kodzie – zawsze z `--build`) |
| `docker compose up -d` | to samo w tle; logi: `docker compose logs -f aplikacja` |
| `docker compose down` | zatrzymuje kontenery, **dane bazy zostają** |
| `docker compose down -v` | zatrzymuje i **usuwa bazę** (następny start – świeże dane) |

Przy pierwszym starcie baza dostaje *przykładową organizację* (postacie ze scenariuszy). Pełną organizację (199 osób)
wybierzesz na stronie startowej („Nowa baza”) albo zmieniając w `docker-compose.yml` `ZBIOR_DANYCH: pelna`
i uruchamiając `docker compose down -v`, a potem `docker compose up --build`.

### Sposób B – bez Dockera (SQLite w pliku)

W terminalu z aktywnym `(.venv)`:

```powershell
python -m pip install -r requirements.txt
uvicorn aplikacja.main:app --reload
```

Strona: **http://localhost:8000**. Baza to plik `softnova.db` w folderze projektu (usuń go, by zacząć od nowa).
`--reload` sam restartuje aplikację po zapisaniu zmian w kodzie – wygodne przy pracy.

### Testy i diagram ERD

```powershell
python -m pip install -r requirements-dev.txt
python -m pytest                       # wszystkie testy (rdzeń + aplikacja na SQLite)
python -m aplikacja.erd dokumentacja   # diagram ERD: dokumentacja/erd.png, .svg, .mmd
```

Gotowy diagram ERD jest już w folderze `dokumentacja` (do rozdziału 4), a raport metryk – w `dokumentacja/wyniki_metryk/metryki.md` (do rozdziału 5).

Pomiar czasu M7 zależy od komputera – do pracy najlepiej zmierzyć na własnym i podać jego parametry
(`python -m dostep metryki`). Czas przez API mierzony jest na tymczasowej bazie SQLite, więc pomiar nie zmienia
danych pokazu. Pomiar na PostgreSQL: `--baza-api <adres osobnej, pustej bazy>` (baza zostanie wypełniona danymi testowymi).

### Proponowany przebieg prezentacji (ok. 10 minut)

1. **Start** – organizacja, osoby, zbiór danych. Wybierz konto *Anna Nowak* (programistka zespołu A1).
2. **Sprawdź dostęp** – repozytorium klienta Y, operacja R → *ODMÓW (krok 1): WT1, RC1* (scenariusz SZ1);
   repozytorium klienta X → *ZEZWÓL* z regułami.
3. **Scenariusze** – „Uruchom wszystkie”: SZ1–SZ10 i zwykła praca, wynik 43/43 (metryki M1, M2, M6).
4. **Wnioski** – Anna prosi o sekrety projektu (Z9, KW4) → próbuje sama zaakceptować (SO6, odmowa) →
   przełącz na *Piotra* (przełożony) i *Wandę* (właścicielka) → akceptacje → wniosek zrealizowany →
   jako Anna „Sprawdź dostęp” do sekretów → *ZEZWÓL*.
5. **Sesje i tryb awaryjny** – *Henryk* (zwykłe konto) próbuje aktywować administratora → odmowa (WT4);
   konto *Henryk [administracyjne]* → prośba → *Natalia* zatwierdza. *Daria* (dyżur) uruchamia tryb awaryjny → alarm.
6. **Kadry** – jako *Natalia* (HR): odejście *Radosława* → konta zablokowane, zadania przekazane.
7. **Zegar** – „+6 mies.” → **Recertyfikacja** → „Uruchom kampanię” → *Wanda* potwierdza dostęp Anny.
8. **Dziennik** – wszystkie zdarzenia, sygnały, łańcuch skrótów *nienaruszony*; w bazie nie da się zmienić wpisu.
9. **Metryki** – po przełączeniu na pełną organizację: M4 = 1 : 7,65, M5 = 0,213.

---

## 9. Codzienna praca – ściąga

1. Otwórz VS Code (zwykle sam otworzy ostatni projekt) albo *Open with Code* na folderze.
2. Otwórz terminal (**Ctrl+`**) i sprawdź, czy jest `(.venv)`. Jeśli nie ma:
   `.venv\Scripts\Activate.ps1`.
3. Pracuj, a po zmianach uruchamiaj `python -m dostep`.
4. Na koniec zapisz zmiany: `git add .` i `git commit -m "…"`.

---

## 10. Mapa projektu – co gdzie jest

Każdy plik odpowiada konkretnemu fragmentowi rozdziału 3, więc łatwo go opisać w rozdziale 4.

| Plik | Zawartość | Źródło w pracy |
|---|---|---|
| `dostep/model.py` | klasy: Użytkownik, Konto, Sesja, Zasób, Obiekt, Decyzja… | rys. 3.3, tab. 3.14 |
| `dostep/polityka/zasoby.py` | zasoby Z1–Z17 z klasą, znacznikiem DO i właścicielem | tab. 3.7 |
| `dostep/polityka/role.py` | role RB, T1–T12, B1–B13, role administratorów, rola awaryjna | tab. 3.8, 3.11 |
| `dostep/polityka/macierz.py` | macierz uprawnień przyznanych | tab. Z2.1, Z2.2 |
| `dostep/polityka/katalog.py` | katalog uprawnień wnioskowalnych | tab. Z2.3 |
| `dostep/reguly.py` | WT1–WT6, RC1–RC19, RE1–RE4, SO1–SO9 | tab. 3.13, 3.15–3.17, Z2.4 |
| `dostep/pdp.py` | punkt decyzyjny – kolejność kroków 1–6 | podrozdz. 3.5.6 |
| `dostep/sod_statyczne.py` | SS1–SS5 przy przypisaniu roli | tab. 3.12 |
| `dostep/dziennik.py` | dziennik tylko do dopisywania, z łańcuchem skrótów | podrozdz. 3.5.7, WN-05 |
| `dostep/rejestr.py` | przechowywanie użytkowników, kont, obiektów, katalogu (PIP) | rys. 3.2 |
| `dostep/polityka/zakres.py` | maksimum z roli i katalogu, zakres upoważnienia RODO | 3.5.1, WT7 |
| `dostep/system.py` | fasada systemu: PEP, dziennik, sygnały, zadania przeglądu | rys. 3.2, WF-18 |
| `dostep/wnioski.py` | wniosek → akceptacje → automatyczna realizacja; zmiana katalogu | rys. 3.4, tab. 3.9, SO6, SO8 |
| `dostep/sesje.py` | role uprzywilejowane w sesji, tryb awaryjny, zastępstwa | tab. 3.11, 3.5.4, RE3 |
| `dostep/cykl_zycia.py` | zdarzenia kadrowe, blokady po 45 dniach, sygnał po 90 dniach | tab. 3.18, rys. 3.5 |
| `dostep/recertyfikacja.py` | recertyfikacja i wykazy „co ma użytkownik” / „kto ma dostęp” | 3.5.7, rys. 3.6, WF-17 |
| `dostep/pokaz_procesow.py` | pokaz procesów (`python -m dostep procesy`) | – |
| `dostep/organizacja.py` | generator pełnej organizacji – 199 osób, zespoły, chaptery, przełożeni, klienci | 3.1, Z1.1–Z1.3, tab. 3.8 |
| `dostep/stan_przed.py` | stan „przed” odtworzony z opisu, metryki M4 i M5 | 3.2, tab. 3.20 |
| `dostep/pokaz_organizacji.py` | zestawienie organizacji i eksport CSV | – |
| `dostep/metryki.py`, `dostep/raport_metryk.py` | pomiar metryk M1–M10 i raport do rozdziału 5 | tab. 3.20, rozdz. 5 |
| `aplikacja/pomiar_api.py` | pomiar czasu pełnego żądania przez API (M7) | WN-04 |
| `aplikacja/baza.py` | schemat bazy (21 tabel), zapis i odczyt stanu, wyzwalacz chroniący dziennik | ERD, WN-05 |
| `aplikacja/stan.py` | stan aplikacji: system w pamięci + zapis w bazie, zegar symulowany | – |
| `aplikacja/api.py` | API REST (FastAPI) – przypadki użycia z diagramu Z3.1 | rys. Z3.1, 3.2 |
| `aplikacja/strony.py`, `szablony/` | strona www do prezentacji | – |
| `aplikacja/erd.py` | generator diagramu ERD ze schematu bazy | rozdz. 4 |
| `Dockerfile`, `docker-compose.yml` | obraz aplikacji i uruchomienie z PostgreSQL | – |
| `dostep/przyklad.py` | przykładowa organizacja (kilkanaście osób) | podrozdz. 3.1 |
| `dostep/scenariusze.py` | scenariusze SZ1–SZ10 i zwykłej pracy z oczekiwanymi decyzjami | tab. 3.2 |
| `dostep/__main__.py` | pokaz z wiersza poleceń (`python -m dostep`) | – |
| `testy/` | testy automatyczne (pytest) – na później | rozdz. 5 |

Przykład zmiany polityki: w `dostep/polityka/macierz.py` usuń `"RC1"` z wiersza
`_w("T1", "Z4", "RWMA", "RC1 WT1", "SO1")`, zapisz i uruchom `python -m dostep SZ1`.
W uzasadnieniu zostanie wtedy tylko WT1. Potem przywróć zmianę (`git checkout dostep/polityka/macierz.py`).

Testy uruchomisz w dowolnym momencie poleceniem `python -m pytest`. Powinno być *passed* przy wszystkich.

---

## 11. Najczęstsze problemy

| Objaw | Rozwiązanie |
|---|---|
| `python` nie jest rozpoznawany / otwiera się Microsoft Store | PATH lub aliasy – patrz część 1; zamknij i otwórz terminal |
| `running scripts is disabled on this system` | `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` |
| `No module named dostep` | jesteś w złym folderze – terminal musi być w `C:\projekty\softnova-iam` (`cd C:\projekty\softnova-iam`) |
| brak `(.venv)` przed znakiem zachęty | `.venv\Scripts\Activate.ps1`; w VS Code: *Python: Select Interpreter* → `.venv` |
| krzaczki zamiast polskich liter | używaj terminala w VS Code lub *Windows Terminal*; w starym `cmd` wpisz `chcp 65001` |
| `docker: command not found` / *Docker Desktop is starting…* | uruchom Docker Desktop i poczekaj na *Engine running* |
| Docker: *WSL 2 installation is incomplete* | `wsl --update` w PowerShell jako administrator, restart |
| Docker: *Virtualization support not detected* | włącz wirtualizację w BIOS/UEFI (część 8, pkt 1) |
| `port is already allocated` / port 8000 zajęty | w `docker-compose.yml` zmień `"8000:8000"` na `"8001:8000"` i otwórz http://localhost:8001 (bez Dockera: `uvicorn aplikacja.main:app --port 8001`) |
| strona pokazuje stare dane po zmianach w kodzie | `docker compose up --build` (bez `--build` używany jest stary obraz) |
| chcę zacząć pokaz od zera | strona startowa → „Nowa baza” albo `docker compose down -v` |

---

## 12. Linux i macOS – różnice

| Krok | Linux (Ubuntu/Debian) | macOS |
|---|---|---|
| Python | `sudo apt install python3 python3-venv python3-pip` | instalator z python.org lub `brew install python@3.12` |
| Git | `sudo apt install git` | `xcode-select --install` lub `brew install git` |
| uruchamianie Pythona | `python3` zamiast `python` | `python3` zamiast `python` |
| aktywacja venv | `source .venv/bin/activate` | `source .venv/bin/activate` |
| Docker | Docker Engine wg docs.docker.com/engine/install + `sudo usermod -aG docker $USER` | Docker Desktop for Mac (Apple Silicon lub Intel) |

Pozostałe polecenia (`git …`, `python -m dostep …`, `docker compose …`) są identyczne.
