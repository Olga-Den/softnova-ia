# Wyniki metryk oceny modelu (tabela 3.20)

Wygenerowano: 2026-10-14 17:47 poleceniem `python -m dostep metryki` (czas obliczeń 14 s). Środowisko: Python 3.13.16, Linux 6.18.44-fc-v114, x86_64, 2 rdzeni logicznych; procesor: x86_64.

Dane: przykładowa organizacja (scenariusze SZ1–SZ10, ZP01–ZP23) oraz pełna organizacja SoftNova – 199 osób, generator deterministyczny (ziarno 2026), zegar modelu 2026-10-14 10:00. Wyniki M1–M6 i M8–M10 są powtarzalne; M7 zależy od komputera.

## Tabela zbiorcza

| ID | Metryka | Wynik | Oczekiwana wartość | Spełnione | Wymagania |
|---|---|---|---|---|---|
| M1 | poprawność decyzji | 100,0% (512/512) | 100% | tak | WF-01–WF-14 |
| M2 | skuteczność SoD | 100,0% (95/95) | 100% | tak | WF-08, WF-09 |
| M3 | uprawnienia nadmiarowe | 0 | 0 | tak | WF-16 |
| M4 | stosunek ról do użytkowników | 1 : 7,65 (26 ról / 199 osób) | ok. 1 : 7,7 | tak | WN-03 |
| M5 | liczba przypisań | 0,213 ((522 UA + 198 PA) / 3383) | < 1 | tak | WN-03 |
| M6 | nieuzasadnione odmowy | 0 | 0 | tak | WN-07 |
| M7 | czas decyzji (95. percentyl) | PDP 0,082 ms; API 18,18 ms | < 10 ms (PDP); < 100 ms (API) | tak | WN-04 |
| M8 | automatyzacja nadawania | 98,0% uprawnień bez wniosku; śr. 0,98 wniosku na osobę (maks.) | wysoki / niska | tak | WN-07 |
| M9 | kompletność dziennika | 100,0% (64/64) | 100% | tak | WF-18, WN-05 |
| M10 | zawężenie uprawnień przez ABAC | 83,3% (średnio dla ról T1–T5 i B4) | > 0 | tak | WF-10 |

## M1 – poprawność decyzji

**Wynik:** 100,0% (512/512) (oczekiwane: 100%).

**Metodyka.** Odsetek decyzji PDP zgodnych z oczekiwanymi: (a) scenariusze zagrożeń SZ1–SZ10 i uzupełnienia (UP1, USL1, USL2) – oczekiwana odmowa, (b) scenariusze zwykłej pracy ZP01–ZP23 – oczekiwane zezwolenie, (c) uogólnienie SZ1 na pełną organizację. Decyzja jest zgodna, gdy zgadza się wynik i w uzasadnieniu występują oczekiwane reguły. Każdy scenariusz działa na świeżej kopii przykładowej organizacji.

| ID | scenariusz | oczekiwane | wynik PDP | reguły w uzasadnieniu | zgodne |
|---|---|---|---|---|---|
| SZ1 | programista zespołu klienta X czyta repozytorium klienta Y | odmów | odmów (krok 1) | WT1, RC1 | tak |
| SZ2a | kontraktor B2B po wygaśnięciu umowy loguje się do CI/CD | odmów | odmów (krok 1) | WT3 | tak |
| SZ2b | kontraktor B2B po wygaśnięciu umowy odczytuje sekrety potoku | odmów | odmów (krok 1) | WT3, WF-15 | tak |
| SZ3a | programista przeniesiony z plemienia B nie ma już dostępu do produkcji | odmów | odmów (krok 6) | RE1 | tak |
| SZ3b | po przeniesieniu nie zapisuje w zadaniach dawnego zespołu (RC12 – tylko odczyt) | odmów | odmów (krok 2) | RC1 | tak |
| SZ4a | przejęte konto programisty poza dyżurem – odczyt bazy klientów | odmów | odmów (krok 6) | RE4 | tak |
| SZ4b | przejęte konto na dyżurze, ale z urządzenia prywatnego | odmów | odmów (krok 1) | WT2, RC8 | tak |
| SZ5a | księgowy sam zatwierdza przelew na rzecz fikcyjnego kontrahenta | odmów | odmów (krok 2) | RC13, SO3 | tak |
| SZ5b | główna księgowa zatwierdza przelew, który sama przygotowała | odmów | odmów (krok 3) | SO3 | tak |
| SZ6a | członek IT nadaje sobie dostęp w IAM ze zwykłego konta | odmów | odmów (krok 6) | – (domyślna odmowa: brak uprawnienia w roli i katalogu) | tak |
| SZ6b | członek IT z konta administracyjnego bez aktywnej roli w sesji | odmów | odmów (krok 6) | – (domyślna odmowa: brak uprawnienia w roli i katalogu) | tak |
| SZ6c | członek IT z konta administracyjnego odczytuje dane kadrowe | odmów | odmów (krok 6) | – (domyślna odmowa: brak uprawnienia w roli i katalogu) | tak |
| SZ7a | programista zatwierdza własną zmianę w kodzie | odmów | odmów (krok 3) | SO1 | tak |
| SZ7b | programista zatwierdza własne wdrożenie na produkcję | odmów | odmów (krok 3) | SO2 | tak |
| SZ8a | stażysta usuwa repozytorium | odmów | odmów (krok 6) | – (domyślna odmowa: brak uprawnienia w roli i katalogu) | tak |
| SZ8b | stażysta zapisuje poza własną gałęzią | odmów | odmów (krok 2) | RC9 | tak |
| SZ10 | account manager eksportuje pełne dane klienta prowadzonego przez innych | odmów | odmów (krok 2) | RC3 | tak |
| UP1 | account manager bez upoważnienia RODO otwiera kartę swojego klienta | odmów | odmów (krok 1) | WT7 | tak |
| USL1 | potok CI/CD wdraża wydanie, którego nikt nie zatwierdził | odmów | odmów (krok 3) | SO2 | tak |
| USL2 | ktoś loguje się interaktywnie na konto usługowe potoku | odmów | odmów (krok 6) | WF-13 | tak |
| ZP01 | programista czyta wiki | zezwól | zezwól (krok 4) | WT3 | tak |
| ZP02 | programista czyta zadania zespołu | zezwól | zezwól (krok 4) | WT3, WT1, RC1 | tak |
| ZP03 | programista czyta repozytorium projektu | zezwól | zezwól (krok 4) | WT3, WT1, RC8, RC1 | tak |
| ZP04 | programista zapisuje w repozytorium projektu | zezwól | zezwól (krok 4) | WT3, WT1, RC8, RC1 | tak |
| ZP05 | programista składa wniosek w IAM | zezwól | zezwól (krok 4) | WT3, WT2, WT7, RC8 | tak |
| ZP06 | inny programista zespołu zatwierdza zmianę | zezwól | zezwól (krok 4) | WT3, WT1, RC8, RC1, SO1 | tak |
| ZP07 | tester odbiera testy zmiany | zezwól | zezwól (krok 4) | WT3, WT1, RC8, RC1, SO9 | tak |
| ZP08 | PO zatwierdza wdrożenie | zezwól | zezwól (krok 4) | WT3, WT1, RC8, RC1, SO2 | tak |
| ZP09 | stażysta zapisuje we własnej gałęzi | zezwól | zezwól (krok 4) | WT3, WT1, RC8, RC1, RC9 | tak |
| ZP10 | programista na dyżurze czyta infrastrukturę produkcji | zezwól | zezwól (krok 5) | WT3, WT2, WT7, RC8, RE1 | tak |
| ZP11 | programista na dyżurze modyfikuje infrastrukturę przez VPN | zezwól | zezwól (krok 5) | WT3, WT2, WT7, RC8, RE1 | tak |
| ZP12 | główna księgowa zatwierdza przelew do 50 000 zł | zezwól | zezwól (krok 4) | WT3, WT7, RC8, RC13, SO3 | tak |
| ZP13 | COO zatwierdza przelew powyżej 50 000 zł | zezwól | zezwól (krok 4) | WT3, WT7, RC8, RC13, SO3 | tak |
| ZP14 | księgowy czyta przelew | zezwól | zezwól (krok 4) | WT3, WT7, RC8 | tak |
| ZP15 | account manager czyta kartę swojego klienta | zezwól | zezwól (krok 4) | WT3, WT7, RC8, RC3 | tak |
| ZP16 | account manager aktualizuje kartę swojego klienta | zezwól | zezwól (krok 4) | WT3, WT7, RC8, RC3 | tak |
| ZP17 | account manager czyta dane podstawowe innego klienta | zezwól | zezwól (krok 4) | WT3, WT7, RC8, RC3 | tak |
| ZP18 | specjalista kadr czyta dane kadrowe | zezwól | zezwól (krok 4) | WT3, WT2, WT7, RC8, RC14 | tak |
| ZP19 | specjalista kadr czyta dane o zdrowiu | zezwól | zezwól (krok 4) | WT3, WT2, WT7, RC8, RC14 | tak |
| ZP20 | kierownik HR zatwierdza listę płac | zezwól | zezwól (krok 4) | WT3, WT2, WT7, RC8, RC13, RC14, SO4 | tak |
| … | … | … | … | … | … |

## M2 – skuteczność SoD

**Wynik:** 100,0% (95/95) (oczekiwane: 100%).

**Metodyka.** Stosunek zablokowanych prób naruszenia rozdziału obowiązków do wszystkich prób wprowadzonych w testach: (a) SO przy decyzji PDP (zatwierdzenie własnej operacji, zatwierdzenie przez niewłaściwą rolę, wdrożenie bez zatwierdzenia), (b) SO6 i SO8 w procesach wniosków, ról uprzywilejowanych i katalogu, (c) SS przy przypisaniu ról – próba wykonana dla każdej osoby z rolą objętą ograniczeniem w pełnej organizacji. Próba jest zablokowana, gdy operacja została odrzucona z powodu właściwego ograniczenia.

| rodzaj | ograniczenie | zablokowane / próby |
|---|---|---|
| SO (decyzja) | SO1 | 2/2 |
| SO (decyzja) | SO2 | 2/2 |
| SO (decyzja) | SO3 | 3/3 |
| SO (proces) | SO6 | 4/4 |
| SO (proces) | SO8 | 1/1 |
| SS (przypisanie) | SS1 | 12/12 |
| SS (przypisanie) | SS2 | 2/2 |
| SS (przypisanie) | SS3 | 7/7 |
| SS (przypisanie) | SS4 | 60/60 |
| SS (przypisanie) | SS5 | 2/2 |

## M3 – uprawnienia nadmiarowe

**Wynik:** 0 (oczekiwane: 0).

**Metodyka.** Pełna organizacja; 18 zdarzeń kadrowych (przeniesienia, w tym dyżurnych i osób z przydziałami z wniosków, zmiany stanowiska, w tym administratorów, czasowe przeniesienia, odejścia, koniec kontraktu B2B). Po 15 dniach (po okresie RC12) i wykonaniu zadań codziennych dla każdej osoby porównano efektywne uprawnienia (pary obiekt–operacja, na które PDP zezwala) z uprawnieniami osoby o tych samych bieżących atrybutach, lecz bez historii. Nadmiar = uprawnienia, których taka osoba by nie miała; dla osób odchodzących – każde uprawnienie.

| zdarzenie | osoba | uprawnienia przed zdarzeniem | po 15 dniach | odebrane | nadmiarowe |
|---|---|---|---|---|---|
| przeniesienie A→A | barbara.kolodziej | 46 | 40 | 18 | 0 |
| przeniesienie A→A | pawel.krol | 46 | 40 | 18 | 0 |
| przeniesienie A→A | jakub.sowa | 39 | 40 | 11 | 0 |
| przeniesienie A→A | natalia.wrona | 39 | 40 | 11 | 0 |
| przeniesienie B→A (dyżurny) | jakub.mazurek | 43 | 39 | 16 | 0 |
| przeniesienie B→A (dyżurny) | marcin.mazurek | 36 | 39 | 9 | 0 |
| przeniesienie A→B | rafal.wojcik | 24 | 22 | 12 | 0 |
| przeniesienie A→B | dariusz.kaczmarek | 22 | 20 | 10 | 0 |
| zmiana stanowiska → T1 | igor.dudek | 47 | 30 | 32 | 0 |
| zmiana stanowiska → T5 | michal.krol | 36 | 13 | 24 | 0 |
| zmiana stanowiska → T12 | jakub.wieczorek | 5 | 7 | 0 | 0 |
| czasowe przeniesienie A5→A6 i powrót | zofia.dudek | 39 | 39 | 0 | 0 |
| czasowe przeniesienie A5→A6 i powrót | rafal.walczak | 39 | 39 | 0 | 0 |
| odejście | szymon.kolodziej | 39 | 0 | 39 | 0 |
| odejście | filip.szulc | 24 | 0 | 24 | 0 |
| odejście | zofia.sowa | 5 | 0 | 5 | 0 |
| odejście | piotr.szulc | 40 | 0 | 40 | 0 |
| koniec kontraktu B2B | lukasz.wilk | 26 | 0 | 26 | 0 |

- Model odebrał automatycznie 295 uprawnień (pary obiekt–operacja) bez udziału administratora.

## M4 – stosunek ról do użytkowników

**Wynik:** 1 : 7,65 (26 ról / 199 osób) (oczekiwane: ok. 1 : 7,7).

**Metodyka.** Liczba ról organizacyjnych (rola bazowa + 25 ról funkcyjnych z tabeli 3.8) do liczby aktywnych użytkowników pełnej organizacji. Role administratorów, rola awaryjna i rola konta usługowego nie są rolami organizacyjnymi.

## M5 – liczba przypisań

**Wynik:** 0,213 ((522 UA + 198 PA) / 3383) (oczekiwane: < 1).

**Metodyka.** Σ(|Uᵢ| + |Pᵢ|) / Σ|Uᵢ|·|Pᵢ| [5, s. 19–20]. Licznik: przypisania w modelu – użytkownik–rola (rola bazowa, funkcyjna, role uprzywilejowane, konto usługowe) i rola–uprawnienie (pary zasób–operacja w macierzy). Mianownik: bezpośrednie przypisania (użytkownik, zasób–operacja) w stanie „przed”, odtworzonym z opisu w podrozdziale 3.2 (funkcja + nadmiar ze słabości S3, S7, S8, S12).

| rola | nazwa | osób | uprawnienia roli (PA) | śr. przypisań „przed” | śr. stałych, nie z roli |
|---|---|---|---|---|---|
| B1 | zarząd | 3 | 7 | 12,0 | 0,0 |
| B2 | prawnik | 1 | 4 | 13,0 | 0,0 |
| B3 | Inspektor Ochrony Danych | 1 | 1 | 10,0 | 0,0 |
| B4 | account manager | 7 | 5 | 10,6 | 0,0 |
| B5 | presales | 3 | 2 | 7,0 | 0,0 |
| B6 | wsparcie klienta | 12 | 4 | 9,3 | 0,0 |
| B7 | księgowy | 5 | 5 | 10,4 | 0,0 |
| B8 | kontroler | 2 | 1 | 6,0 | 0,0 |
| B9 | HR business partner | 3 | 3 | 8,7 | 0,0 |
| B10 | rekruter | 4 | 4 | 9,0 | 0,0 |
| B11 | specjalista kadr i płac | 2 | 3 | 8,0 | 0,0 |
| B12 | marketing | 4 | 5 | 10,0 | 0,0 |
| B13 | administracja biura | 3 | 4 | 9,3 | 0,0 |
| T1 | programista | 60 | 15 | 23,1 | 2,8 |
| T2 | stażysta-programista | 8 | 6 | 23,0 | 12,0 |
| T3 | tester | 24 | 11 | 16,3 | 0,0 |
| T4 | projektant UX / analityk | 12 | 3 | 8,7 | 0,0 |
| T5 | Product Owner | 12 | 5 | 10,0 | 0,0 |
| T6 | lider plemienia | 3 | 5 | 13,0 | 0,0 |
| T7 | chief architect | 1 | 4 | 13,0 | 0,0 |
| T8 | agile coach | 2 | 3 | 5,0 | 0,0 |
| T9 | DevOps/SRE | 10 | 7 | 29,4 | 17,0 |
| T10 | specjalista bezpieczeństwa | 5 | 6 | 13,8 | 2,0 |
| T11 | administrator IT | 7 | 0 | 36,1 | 30,6 |
| T12 | analityk danych / BI | 5 | 3 | 8,6 | 0,0 |

- Możliwych par (użytkownik, uprawnienie): 16915; przypisań „przed”: 3383 (funkcja 2795, S8 238, S12 214, S7 136).
- Uprawnienia stałe „przed”, które w modelu nie wynikają z roli (są tylko czasowe albo wcale): 660, w tym ponad maksimum modelu: 223.

## M6 – nieuzasadnione odmowy

**Wynik:** 0 (oczekiwane: 0).

**Metodyka.** Liczba odmów w scenariuszach zwykłej pracy, w których dostęp wynika z obowiązków: scenariusze ZP01–ZP23 oraz typowe czynności każdej osoby w pełnej organizacji (urządzenie firmowe, sieć biurowa, dzień roboczy 10:00). Czynności wymagające uprawnień uprzywilejowanych wykonywano tak, jak przewiduje model – po aktywacji roli w sesji (DevOps/SRE na produkcji); odmowa bez sesji jest zamierzona (brak stałego dostępu uprzywilejowanego).

| czynność | żądań | odmów |
|---|---|---|
| scenariusze zwykłej pracy ZP01–ZP23 (przykładowa organizacja) | 23 | 0 |
| każda osoba czyta intranet (Z2) | 199 | 0 |
| członkowie zespołów A czytają repozytorium swojego projektu | 67 | 0 |
| programiści A zapisują w repozytorium swojego projektu | 35 | 0 |
| programiści i testerzy B czytają moduł produktu SaaS (Z5) | 35 | 0 |
| członkowie zespołów pracują z zadaniami własnego zespołu (Z3) | 348 | 0 |
| account managerowie czytają karty przypisanych klientów (Z10) | 7 | 0 |
| analitycy czytają widoki raportowe | 5 | 0 |
| księgowi czytają przelewy (Z12) | 5 | 0 |
| programista plemienia B na dyżurze czyta infrastrukturę produkcji (RE1) | 1 | 0 |
| DevOps/SRE aktywuje administratora Z8 w sesji i pracuje na produkcji (R, M) | 18 | 0 |

## M7 – czas decyzji (95. percentyl)

**Wynik:** PDP 0,082 ms; API 18,18 ms (oczekiwane: < 10 ms (PDP); < 100 ms (API)).

**Metodyka.** PDP: 10000 losowych żądań (stałe ziarno) na pełnej organizacji – losowe konto zwykłe, obiekt i operacja; 200 wywołań rozgrzewających pominięto. API: kolejne żądania POST /api/decyzja przez warstwę FastAPI z zapisem decyzji w dzienniku w bazie danych. Czas mierzony zegarem wysokiej rozdzielczości (perf_counter). Wynik zależy od komputera – podać jego parametry w rozdziale 5.

| pomiar | żądań | średnia [ms] | mediana [ms] | p95 [ms] | p99 [ms] | maks. [ms] | próg p95 [ms] |
|---|---|---|---|---|---|---|---|
| PDP (bez bazy danych) | 10000 | 0,045 | 0,041 | 0,082 | 0,155 | 0,459 | < 10 |
| pełne żądanie przez API (SQLite) | 500 | 11,354 | 10,316 | 18,183 | 28,793 | 87,598 | < 100 |

## M8 – automatyzacja nadawania

**Wynik:** 98,0% uprawnień bez wniosku; śr. 0,98 wniosku na osobę (maks.) (oczekiwane: wysoki / niska).

**Metodyka.** Dla każdej osoby pełnej organizacji maksymalny zakres modelu (pary zasób–operacja) podzielono według sposobu uzyskania: z roli (automatycznie przy zatrudnieniu), automatycznie warunkowo (reguły RE i warunki WT5/WT6), przez aktywację w sesji, tylko na wniosek. Liczba wniosków na osobę = liczba pozycji katalogu z trybem „wniosek” dostępnych dla roli – górna granica wniosków potrzebnych do pełnego zakresu. Dla porównania: w stanie „przed” każde z 3383 bezpośrednich przypisań wymagało zgłoszenia (śr. 17,0 na osobę).

| sposób uzyskania | pary zasób–operacja | udział |
|---|---|---|
| z roli – w chwili zatrudnienia, z danych kadrowych | 3051 | 82,0% |
| automatycznie przy spełnieniu warunku (dyżur, incydent, sprawa IOD – RE, WT5, WT6) | 219 | 5,9% |
| przez aktywację roli uprzywilejowanej w sesji | 373 | 10,0% |
| tylko na wniosek (katalog, akceptacja wg tab. 3.9) | 76 | 2,0% |
| razem – maksymalny zakres modelu (pary zasób–operacja) | 3719 | 100% |

- Stan „przed”: 3383 przypisań nadawanych ręcznie na zgłoszenie = 17,0 na osobę; model: maks. 0,98 wniosku na osobę, reszta automatycznie.

## M9 – kompletność dziennika

**Wynik:** 100,0% (64/64) (oczekiwane: 100%).

**Metodyka.** Na przykładowej organizacji wykonano wszystkie scenariusze (decyzje PDP) oraz sekwencję operacji obejmującą każdy proces (wnioski, role uprzywilejowane, tryb awaryjny, zastępstwa, katalog, zdarzenia kadrowe, zadania codzienne, recertyfikacja). Liczba żądań do PEP porównana z liczbą wpisów „decyzja”; dla każdej operacji, która zmieniła stan przypisań (migawka przed i po), sprawdzono, czy powstał wpis zmiany. Dodatkowo zweryfikowano łańcuch skrótów i wykrycie podmiany wpisu.

| operacja | zdarzeń | wpisy w dzienniku | zarejestrowane |
|---|---|---|---|
| żądania dostępu (decyzje PDP) | 44 | 44 | tak |
| wniosek – akceptacja właściciela i realizacja | 1 | zmiana_przypisania | tak |
| przypisanie roli uprzywilejowanej | 1 | zmiana_przypisania | tak |
| aktywacja roli (po akceptacji właściciela) | 1 | aktywacja_roli | tak |
| aktywacja roli administratora Z10 | 1 | aktywacja_roli | tak |
| tryb awaryjny produkcji | 1 | tryb_awaryjny | tak |
| zastępstwo awaryjne 72 h | 1 | tryb_awaryjny | tak |
| wyznaczenie zastępcy (RE3) | 1 | zmiana_przypisania | tak |
| zmiana katalogu (SO8) | 1 | zmiana_katalogu | tak |
| oświadczenie NDA | 1 | zdarzenie_kadrowe, zmiana_przypisania | tak |
| przeniesienie | 1 | zdarzenie_kadrowe, zmiana_przypisania | tak |
| czasowe przeniesienie | 1 | zdarzenie_kadrowe, zmiana_przypisania | tak |
| koniec czasowego przeniesienia | 1 | zdarzenie_kadrowe, zmiana_przypisania | tak |
| zmiana stanowiska | 1 | zdarzenie_kadrowe, zmiana_przypisania | tak |
| dyżur | 1 | zdarzenie_kadrowe, zmiana_przypisania | tak |
| odejście | 1 | zdarzenie_kadrowe, zmiana_przypisania | tak |
| zatrudnienie | 1 | zdarzenie_kadrowe, zmiana_przypisania | tak |
| zadania codzienne (koniec umów, wygasanie) | 1 | zdarzenie_kadrowe, zmiana_przypisania | tak |
| recertyfikacja – odebranie (Z9:R:sekret_projektu (wniosek WN-1)) | 1 | recertyfikacja, zmiana_przypisania | tak |
| recertyfikacja – odebranie (administrator Z10) | 1 | recertyfikacja, zmiana_przypisania | tak |
| zadania codzienne po 6 miesiącach (blokady, wygasanie) | 1 | blokada_konta, zdarzenie_kadrowe, zmiana_przypisania | tak |

- Wpisów w dzienniku: 142; łańcuch skrótów poprawny: tak; podmiana wpisu wykryta: tak.

## M10 – zawężenie uprawnień przez ABAC

**Wynik:** 83,3% (średnio dla ról T1–T5 i B4) (oczekiwane: > 0).

**Metodyka.** Dla każdej osoby z rolą T1–T5 lub B4 w pełnej organizacji wyznaczono efektywne uprawnienia na poziomie obiektów (pary obiekt–operacja, na które PDP zezwala) przy samych rolach (bez warunków twardych i reguł zawężających) oraz po ich zastosowaniu (bez SO, by mierzyć wyłącznie ABAC). Zawężenie osoby = (przy rolach − po WT i RC) / przy rolach; wynik roli – średnia osób, wynik metryki – średnia sześciu ról.

| rola | nazwa | osób | śr. par przy samych rolach | śr. par po WT i RC | zawężenie |
|---|---|---|---|---|---|
| T1 | programista | 60 | 170,7 | 38,0 | 77,7% |
| T2 | stażysta-programista | 8 | 104,0 | 17,0 | 83,7% |
| T3 | tester | 24 | 143,0 | 21,3 | 85,0% |
| T4 | projektant UX / analityk | 12 | 86,0 | 11,9 | 86,0% |
| T5 | Product Owner | 12 | 110,0 | 13,6 | 87,7% |
| B4 | account manager | 7 | 123,1 | 26,1 | 79,8% |
