"""Warstwa bazy danych (E5) – schemat tabel (ERD) i zapis/odczyt stanu systemu dostępu.

Rdzeń (`dostep/`) nie zależy od bazy (WN-01). Ten moduł przekłada jego obiekty na tabele:
  * PostgreSQL (Docker) – docelowo,
  * SQLite – do uruchomienia bez Dockera i do testów.
Wybór przez zmienną środowiskową DATABASE_URL.

Dziennik zdarzeń jest tylko do dopisywania (WN-05): wyzwalacz w bazie blokuje UPDATE i DELETE,
a każdy wpis zawiera skrót SHA-256 poprzedniego (łańcuch weryfikowany przez `Dziennik.weryfikuj`).
"""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    JSON, Boolean, Column, Date, DateTime, Float, ForeignKey, ForeignKeyConstraint, Integer, MetaData, String,
    Table, Text, create_engine, delete, event, func, insert, select, text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.engine import Engine

from dostep.dziennik import Dziennik, WpisDziennika
from dostep.model import (
    FormaWspolpracy, Incydent, Konto, Obiekt, Okres, Operacja, Przydzial, Sesja, TypKonta, Upowaznienie,
    Uzytkownik, Zastepstwo,
)
from dostep.polityka.katalog import PozycjaKatalogu
from dostep.polityka.macierz import MACIERZ
from dostep.polityka.role import ROLE
from dostep.polityka.zasoby import ZASOBY
from dostep.recertyfikacja import PozycjaPrzegladu
from dostep.rejestr import Rejestr
from dostep.system import SystemDostepu, ZadaniePrzegladu
from dostep.wnioski import StatusWniosku, Wniosek, Wymaganie

Json = JSON().with_variant(JSONB(), "postgresql")
meta = MetaData()

# ---------------------------------------------------------------------------
# Polityka (tabele 3.7, 3.8, 3.11, Z2.1–Z2.3)
# ---------------------------------------------------------------------------
zasoby = Table("zasoby", meta,
               Column("id", String(8), primary_key=True),
               Column("nazwa", String(80), nullable=False),
               Column("klasa", String(4), nullable=False),
               Column("dane_osobowe", Boolean, nullable=False),
               Column("wlasciciel_opis", String(80)))

role = Table("role", meta,
             Column("id", String(16), primary_key=True),
             Column("nazwa", String(80), nullable=False),
             Column("typ", String(20), nullable=False),
             Column("dziedziczy", String(40)),
             Column("zasob_id", String(8), ForeignKey("zasoby.id")),
             Column("maks_godzin", Integer))

uprawnienia_rol = Table("uprawnienia_rol", meta,   # PA – macierz uprawnień przyznanych
                        Column("id", Integer, primary_key=True),
                        Column("rola_id", String(16), nullable=False),   # także pseudo-rola „P2/P3”
                        Column("zasob_id", String(8), ForeignKey("zasoby.id"), nullable=False),
                        Column("operacje", String(5), nullable=False),
                        Column("reguly", String(60)),
                        Column("so", String(30)),
                        Column("typy_rekordu", String(120)),
                        Column("tylko_plemie", String(2)))

katalog = Table("katalog", meta,                   # katalog uprawnień wnioskowalnych (zmieniany przez SO8)
                Column("id", Integer, primary_key=True),
                Column("rola_id", String(16), ForeignKey("role.id"), nullable=False),
                Column("zasob_id", String(8), ForeignKey("zasoby.id"), nullable=False),
                Column("operacje", String(5), nullable=False),
                Column("sposob", String(12), nullable=False),
                Column("typ_rekordu", String(40)),
                Column("opis", String(120)))

# ---------------------------------------------------------------------------
# Tożsamość: użytkownicy, konta, przypisania
# ---------------------------------------------------------------------------
uzytkownicy = Table("uzytkownicy", meta,
                    Column("id", String(60), primary_key=True),
                    Column("imie_nazwisko", String(120), nullable=False),
                    Column("rola_funkcyjna", String(16), ForeignKey("role.id"), nullable=False),  # UA (funkcja)
                    Column("poziom", String(2), nullable=False),
                    Column("jednostka", String(60), nullable=False),
                    Column("zespol", String(20)),
                    Column("plemie", String(2)),
                    Column("chapter", String(30)),
                    Column("stanowisko", String(60)),
                    Column("forma", String(20), nullable=False),
                    Column("data_konca_umowy", Date),
                    Column("przelozony_id", String(60)),
                    Column("kierownik_umowy_id", String(60)),
                    Column("aktywny", Boolean, nullable=False),
                    Column("zespol_tymczasowy", String(20)),
                    Column("poprzedni_zespol", String(20)),
                    Column("data_przeniesienia", DateTime),
                    Column("data_zatrudnienia", DateTime),
                    Column("ostatnia_aktywnosc", DateTime),
                    Column("wyznaczony_wynagrodzenia_zarzadu", Boolean, nullable=False, default=False),
                    Column("atrybuty", Json, nullable=False),   # atrybuty z PIP: NDA, dyżury, incydenty…
                    ForeignKeyConstraint(["przelozony_id"], ["uzytkownicy.id"], deferrable=True,
                                         initially="DEFERRED", name="fk_przelozony"))

konta = Table("konta", meta,
              Column("id", String(70), primary_key=True),
              Column("uzytkownik_id", String(60), ForeignKey("uzytkownicy.id"), nullable=False),
              Column("typ", String(20), nullable=False),
              Column("aktywne", Boolean, nullable=False),
              Column("rola_id", String(16), ForeignKey("role.id")),   # rola konta usługowego
              Column("zablokowane_o", DateTime),
              Column("powod_blokady", String(120)))

przypisania_uprzywilejowane = Table("przypisania_uprzywilejowane", meta,   # UA – role uprzywilejowane
                                    Column("uzytkownik_id", String(60), ForeignKey("uzytkownicy.id"), primary_key=True),
                                    Column("rola_id", String(16), ForeignKey("role.id"), primary_key=True))

wlasciciele_zasobow = Table("wlasciciele_zasobow", meta,
                            Column("uzytkownik_id", String(60), ForeignKey("uzytkownicy.id"), primary_key=True),
                            Column("zasob_id", String(8), ForeignKey("zasoby.id"), primary_key=True))

upowaznienia = Table("upowaznienia", meta,           # WT7 – rejestr upoważnień RODO
                     Column("uzytkownik_id", String(60), ForeignKey("uzytkownicy.id"), primary_key=True),
                     Column("zakres", String(120), nullable=False),
                     Column("od", DateTime, nullable=False),
                     Column("do", DateTime),
                     Column("odwolane_o", DateTime))

przydzialy = Table("przydzialy", meta,               # uprawnienia z katalogu nadane wnioskiem / awaryjnie
                   Column("id", Integer, primary_key=True),
                   Column("uzytkownik_id", String(60), ForeignKey("uzytkownicy.id"), nullable=False),
                   Column("zasob_id", String(8), ForeignKey("zasoby.id"), nullable=False),
                   Column("operacje", String(5), nullable=False),
                   Column("typ_rekordu", String(40)),
                   Column("od", DateTime),
                   Column("do", DateTime),
                   Column("wniosek_id", String(20)),
                   Column("awaryjny", Boolean, nullable=False),
                   Column("ostatnia_recertyfikacja", DateTime))

sesje = Table("sesje", meta,
              Column("id", String(20), primary_key=True),
              Column("konto_id", String(70), ForeignKey("konta.id"), nullable=False),
              Column("numer_zgloszenia", String(40)))

sesje_role = Table("sesje_role", meta,
                   Column("sesja_id", String(20), ForeignKey("sesje.id"), primary_key=True),
                   Column("rola_id", String(16), ForeignKey("role.id"), primary_key=True),
                   Column("od", DateTime, nullable=False),
                   Column("do", DateTime, nullable=False))

# ---------------------------------------------------------------------------
# Obiekty chronione
# ---------------------------------------------------------------------------
obiekty = Table("obiekty", meta,
                Column("id", String(60), primary_key=True),
                Column("zasob_id", String(8), ForeignKey("zasoby.id"), nullable=False),
                Column("nazwa", String(160), nullable=False),
                Column("zespol", String(20)),
                Column("plemie", String(2)),
                Column("jednostka", String(60)),
                Column("klient", String(60)),
                Column("typ_rekordu", String(40)),
                Column("autor_id", String(60)),
                Column("proces", String(12)),
                Column("kwota", Float),
                Column("dotyczy_osoby_id", String(60)),
                Column("obslugujacy_id", String(60)),
                Column("aktywna_oferta", Boolean, nullable=False),
                Column("termin_przechowywania", Date),
                Column("zrodlo_id", String(60)),
                Column("atrybuty", Json, nullable=False))   # komisja, historia zatwierdzeń

# ---------------------------------------------------------------------------
# Procesy
# ---------------------------------------------------------------------------
wnioski = Table("wnioski", meta,
                Column("id", String(20), primary_key=True),
                Column("wnioskujacy_id", String(60), ForeignKey("uzytkownicy.id"), nullable=False),
                Column("beneficjent_id", String(60), ForeignKey("uzytkownicy.id"), nullable=False),
                Column("zasob_id", String(8), ForeignKey("zasoby.id"), nullable=False),
                Column("operacje", String(5), nullable=False),
                Column("typ_rekordu", String(40)),
                Column("uzasadnienie", Text),
                Column("okres_dni", Integer, nullable=False),
                Column("zlozony_o", DateTime, nullable=False),
                Column("status", String(40), nullable=False),
                Column("powod", Text),
                Column("reguly", String(60)))

wymagania_wnioskow = Table("wymagania_wnioskow", meta,     # wymagane akceptacje (tab. 3.9, SO6)
                           Column("id", Integer, primary_key=True),
                           Column("wniosek_id", String(20), ForeignKey("wnioski.id"), nullable=False),
                           Column("rola", String(30), nullable=False),
                           Column("kandydaci", Json, nullable=False),
                           Column("udzielona_przez", String(60)),
                           Column("czas", DateTime))

prosby = Table("prosby", meta,      # prośby o aktywację ról (Z13, Z17) i zmiany katalogu (SO8)
               Column("id", String(20), primary_key=True),
               Column("rodzaj", String(20), nullable=False),
               Column("dane", Json, nullable=False))

zadania_przegladu = Table("zadania_przegladu", meta,
                          Column("id", String(20), primary_key=True),
                          Column("rodzaj", String(60), nullable=False),
                          Column("opis", Text, nullable=False),
                          Column("recenzent_id", String(60), nullable=False),
                          Column("utworzono", DateTime, nullable=False),
                          Column("termin", DateTime, nullable=False),
                          Column("dotyczy", String(40)),
                          Column("status", String(20), nullable=False),
                          Column("zamknieto_o", DateTime))

pozycje_recertyfikacji = Table("pozycje_recertyfikacji", meta,
                               Column("id", String(20), primary_key=True),
                               Column("uzytkownik_id", String(60), nullable=False),
                               Column("rodzaj", String(30), nullable=False),
                               Column("klucz", String(60), nullable=False),
                               Column("opis", Text, nullable=False),
                               Column("recenzent_id", String(60), nullable=False),
                               Column("utworzono", DateTime, nullable=False),
                               Column("ostatnie_uzycie", DateTime),
                               Column("status", String(20), nullable=False),
                               Column("rozstrzygnieto_o", DateTime))

sygnaly = Table("sygnaly", meta,
                Column("nr", Integer, primary_key=True),
                Column("czas", DateTime, nullable=False),
                Column("tekst", Text, nullable=False))

dziennik = Table("dziennik", meta,   # tylko dopisywanie – wyzwalacz blokuje UPDATE/DELETE
                 Column("nr", Integer, primary_key=True, autoincrement=False),
                 Column("czas", DateTime, nullable=False),
                 Column("zdarzenie", String(40), nullable=False),
                 Column("dane", Json, nullable=False),
                 Column("skrot_poprzedni", String(64), nullable=False),
                 Column("skrot", String(64), nullable=False))

ustawienia = Table("ustawienia", meta,   # zegar symulowany, zbiór danych, liczniki identyfikatorów…
                   Column("klucz", String(40), primary_key=True),
                   Column("wartosc", Json, nullable=False))

TABELE_STANU = [sesje_role, sesje, przydzialy, upowaznienia, przypisania_uprzywilejowane, wlasciciele_zasobow,
                konta, wymagania_wnioskow, wnioski, prosby, zadania_przegladu, pozycje_recertyfikacji,
                obiekty, katalog, uzytkownicy]   # kolejność usuwania (najpierw tabele zależne)

# ---------------------------------------------------------------------------
# Wyzwalacze chroniące dziennik (WN-05)
# ---------------------------------------------------------------------------
_PG_WYZWALACZ = [
    """CREATE OR REPLACE FUNCTION dziennik_tylko_dopisywanie() RETURNS trigger AS $$
       BEGIN RAISE EXCEPTION 'Dziennik zdarzeń jest tylko do dopisywania (WN-05)'; END; $$ LANGUAGE plpgsql""",
    "DROP TRIGGER IF EXISTS dziennik_blokada ON dziennik",
    """CREATE TRIGGER dziennik_blokada BEFORE UPDATE OR DELETE ON dziennik
       FOR EACH ROW EXECUTE FUNCTION dziennik_tylko_dopisywanie()""",
    "DROP TRIGGER IF EXISTS dziennik_blokada_truncate ON dziennik",
    """CREATE TRIGGER dziennik_blokada_truncate BEFORE TRUNCATE ON dziennik
       FOR EACH STATEMENT EXECUTE FUNCTION dziennik_tylko_dopisywanie()""",
]
_SQLITE_WYZWALACZ = [
    """CREATE TRIGGER IF NOT EXISTS dziennik_blokada_update BEFORE UPDATE ON dziennik
       BEGIN SELECT RAISE(ABORT, 'Dziennik zdarzeń jest tylko do dopisywania (WN-05)'); END""",
    """CREATE TRIGGER IF NOT EXISTS dziennik_blokada_delete BEFORE DELETE ON dziennik
       BEGIN SELECT RAISE(ABORT, 'Dziennik zdarzeń jest tylko do dopisywania (WN-05)'); END""",
]


# ---------------------------------------------------------------------------
# Konwersje pomocnicze
# ---------------------------------------------------------------------------
def _iso(t: datetime | date | None) -> str | None:
    return t.isoformat() if t else None


def _dt(s: str | None) -> datetime | None:
    return datetime.fromisoformat(s) if s else None


def _ops(zbior) -> str:
    return "".join(o.value for o in Operacja if o in zbior)


def _okresy(lista: list[Okres]) -> list[list[str]]:
    return [[o.od.isoformat(), o.do.isoformat()] for o in lista]


def _z_okresow(lista) -> list[Okres]:
    return [Okres(_dt(a), _dt(b)) for a, b in lista]


def _incydenty(lista: list[Incydent]) -> list[dict]:
    return [dict(id=i.id, otwarty_o=_iso(i.otwarty_o), zamkniety_o=_iso(i.zamkniety_o),
                 dotyczy_danych=i.dotyczy_danych) for i in lista]


def _z_incydentow(lista) -> list[Incydent]:
    return [Incydent(d["id"], _dt(d["otwarty_o"]), _dt(d["zamkniety_o"]), d["dotyczy_danych"]) for d in lista]


class Magazyn:
    """Zapis i odczyt stanu `SystemDostepu` w bazie danych."""

    def __init__(self, url: str) -> None:
        argumenty = {"connect_args": {"check_same_thread": False}} if url.startswith("sqlite") else {}
        self.silnik: Engine = create_engine(url, future=True, **argumenty)
        if url.startswith("sqlite"):
            @event.listens_for(self.silnik, "connect")
            def _klucze_obce(polaczenie, _):
                polaczenie.execute("PRAGMA foreign_keys=ON")

    @property
    def postgres(self) -> bool:
        return self.silnik.dialect.name == "postgresql"

    # ------------------------------------------------------------------
    def utworz_schemat(self) -> None:
        meta.create_all(self.silnik)
        with self.silnik.begin() as p:
            for polecenie in (_PG_WYZWALACZ if self.postgres else _SQLITE_WYZWALACZ):
                p.execute(text(polecenie))
            if p.execute(select(func.count()).select_from(zasoby)).scalar() == 0:
                self._zapisz_polityke(p)

    def _zapisz_polityke(self, p) -> None:
        p.execute(insert(zasoby), [dict(id=z.id, nazwa=z.nazwa, klasa=z.klasa.name, dane_osobowe=z.dane_osobowe,
                                        wlasciciel_opis=z.wlasciciel) for z in ZASOBY.values()])
        p.execute(insert(role), [dict(id=r.id, nazwa=r.nazwa, typ=r.typ.value, dziedziczy=" ".join(r.dziedziczy),
                                      zasob_id=r.zasob, maks_godzin=r.maks_godzin) for r in ROLE.values()])
        p.execute(insert(uprawnienia_rol), [dict(
            rola_id=w.rola, zasob_id=w.zasob, operacje=_ops(w.operacje), reguly=" ".join(w.reguly), so=" ".join(w.so),
            typy_rekordu=" ".join(sorted(w.typy_rekordu)) if w.typy_rekordu else None, tylko_plemie=w.tylko_plemie)
            for w in MACIERZ])

    def jest_stan(self) -> bool:
        with self.silnik.connect() as p:
            return p.execute(select(func.count()).select_from(uzytkownicy)).scalar() > 0

    def usun_wszystko(self) -> None:
        """Pełne usunięcie bazy (reset pokazu) – jedyna droga do wyczyszczenia dziennika."""
        meta.drop_all(self.silnik)
        if self.postgres:
            with self.silnik.begin() as p:
                p.execute(text("DROP FUNCTION IF EXISTS dziennik_tylko_dopisywanie() CASCADE"))

    # ------------------------------------------------------------------
    # Ustawienia
    # ------------------------------------------------------------------
    def ustawienie(self, klucz: str, domyslna=None):
        with self.silnik.connect() as p:
            w = p.execute(select(ustawienia.c.wartosc).where(ustawienia.c.klucz == klucz)).scalar()
        return domyslna if w is None else w

    def ustaw(self, klucz: str, wartosc, polaczenie=None) -> None:
        def _wykonaj(p):
            p.execute(delete(ustawienia).where(ustawienia.c.klucz == klucz))
            p.execute(insert(ustawienia).values(klucz=klucz, wartosc=wartosc))
        if polaczenie is not None:
            _wykonaj(polaczenie)
        else:
            with self.silnik.begin() as p:
                _wykonaj(p)

    # ------------------------------------------------------------------
    # Zapis stanu
    # ------------------------------------------------------------------
    def zapisz_stan(self, s: SystemDostepu) -> None:
        """Zapisuje cały stan w jednej transakcji; dziennik i sygnały tylko dopisuje."""
        r = s.rejestr
        with self.silnik.begin() as p:
            if self.postgres:
                p.execute(text("SET CONSTRAINTS ALL DEFERRED"))
            for t in TABELE_STANU:
                p.execute(delete(t))
            U = list(r.uzytkownicy.values())
            p.execute(insert(uzytkownicy), [self._wiersz_uzytkownika(u) for u in U])
            self._wstaw(p, przypisania_uprzywilejowane,
                        [dict(uzytkownik_id=u.id, rola_id=x) for u in U for x in sorted(u.role_uprzywilejowane)])
            self._wstaw(p, wlasciciele_zasobow,
                        [dict(uzytkownik_id=u.id, zasob_id=z) for u in U for z in sorted(u.wlasciciel_zasobow)])
            self._wstaw(p, upowaznienia, [dict(uzytkownik_id=u.id, zakres=" ".join(sorted(u.upowaznienie.zakres)),
                                               od=u.upowaznienie.od, do=u.upowaznienie.do,
                                               odwolane_o=u.upowaznienie.odwolane_o)
                                          for u in U if u.upowaznienie])
            self._wstaw(p, przydzialy, [dict(uzytkownik_id=u.id, zasob_id=x.zasob, operacje=_ops(x.operacje),
                                             typ_rekordu=x.typ_rekordu, od=x.okres.od if x.okres else None,
                                             do=x.okres.do if x.okres else None, wniosek_id=x.wniosek_id,
                                             awaryjny=x.awaryjny, ostatnia_recertyfikacja=x.ostatnia_recertyfikacja)
                                        for u in U for x in u.przydzialy])
            self._wstaw(p, konta, [dict(id=k.id, uzytkownik_id=k.uzytkownik_id, typ=k.typ.value, aktywne=k.aktywne,
                                        rola_id=k.rola, zablokowane_o=k.zablokowane_o, powod_blokady=k.powod_blokady)
                                   for k in r.konta.values()])
            self._wstaw(p, sesje, [dict(id=x.id, konto_id=x.konto_id, numer_zgloszenia=x.numer_zgloszenia)
                                   for x in r.sesje.values()])
            self._wstaw(p, sesje_role, [dict(sesja_id=x.id, rola_id=rola, od=o.od, do=o.do)
                                        for x in r.sesje.values() for rola, o in x.aktywne_role.items()])
            self._wstaw(p, obiekty, [self._wiersz_obiektu(o) for o in r.obiekty.values()])
            self._wstaw(p, katalog, [dict(rola_id=k.rola, zasob_id=k.zasob, operacje=_ops(k.operacje), sposob=k.sposob,
                                          typ_rekordu=k.typ_rekordu, opis=k.opis) for k in r.katalog])
            W = list(s.wnioski.wnioski.values())
            self._wstaw(p, wnioski, [dict(id=w.id, wnioskujacy_id=w.wnioskujacy_id, beneficjent_id=w.beneficjent_id,
                                          zasob_id=w.zasob, operacje=_ops(w.operacje), typ_rekordu=w.typ_rekordu,
                                          uzasadnienie=w.uzasadnienie, okres_dni=w.okres_dni, zlozony_o=w.zlozony_o,
                                          status=w.status.value, powod=w.powod, reguly=" ".join(w.reguly)) for w in W])
            self._wstaw(p, wymagania_wnioskow, [dict(wniosek_id=w.id, rola=x.rola, kandydaci=x.kandydaci,
                                                     udzielona_przez=x.udzielona_przez, czas=x.czas)
                                                for w in W for x in w.wymagania])
            self._wstaw(p, prosby, [dict(id=k, rodzaj="aktywacja", dane=v) for k, v in s.sesje.prosby.items()] +
                        [dict(id=k, rodzaj="zmiana_katalogu", dane={**v, "pozycja": self._pozycja_json(v["pozycja"])})
                         for k, v in s.wnioski.zmiany_katalogu.items()])
            self._wstaw(p, zadania_przegladu, [dict(vars(z)) for z in s.przeglady])
            self._wstaw(p, pozycje_recertyfikacji, [dict(vars(x)) for x in s.recertyfikacja.pozycje.values()])
            self._dopisz_dziennik_i_sygnaly(p, s)   # dziennik i sygnały – tylko nowe wpisy
            self.ustaw("stan_procesow", dict(
                liczniki=s.liczniki,
                recertyfikacja_ostatnia=[[u, k, _iso(t)] for (u, k), t in s.recertyfikacja.ostatnia.items()],
                zgloszone_nieuzywane=[list(x) for x in s.kadry.zgloszone_nieuzywane]), p)

    def zapisz_po_decyzji(self, s: SystemDostepu, uzytkownik_id: str, obiekt_id: str) -> None:
        """Szybki zapis po żądaniu dostępu: aktywność użytkownika, historia obiektu, nowe wpisy dziennika."""
        from sqlalchemy import update
        u = s.rejestr.uzytkownik(uzytkownik_id)
        o = s.rejestr.obiekt(obiekt_id)
        with self.silnik.begin() as p:
            w = self._wiersz_uzytkownika(u)
            p.execute(update(uzytkownicy).where(uzytkownicy.c.id == u.id)
                      .values(ostatnia_aktywnosc=w["ostatnia_aktywnosc"], atrybuty=w["atrybuty"]))
            p.execute(update(obiekty).where(obiekty.c.id == o.id).values(atrybuty=self._wiersz_obiektu(o)["atrybuty"]))
            self._dopisz_dziennik_i_sygnaly(p, s)

    def _dopisz_dziennik_i_sygnaly(self, p, s: SystemDostepu) -> None:
        ostatni = p.execute(select(func.coalesce(func.max(dziennik.c.nr), 0))).scalar()
        self._wstaw(p, dziennik, [dict(nr=w.nr, czas=w.czas, zdarzenie=w.zdarzenie, dane=dict(w.dane),
                                       skrot_poprzedni=w.skrot_poprzedni, skrot=w.skrot)
                                  for w in s.dziennik.wpisy() if w.nr > ostatni])
        ile = p.execute(select(func.count()).select_from(sygnaly)).scalar()
        self._wstaw(p, sygnaly, [dict(nr=i + 1, czas=c, tekst=t) for i, (c, t) in enumerate(s.sygnaly) if i >= ile])

    @staticmethod
    def _wstaw(p, tabela, wiersze) -> None:
        if wiersze:
            p.execute(insert(tabela), wiersze)

    @staticmethod
    def _pozycja_json(k: PozycjaKatalogu) -> dict:
        return dict(rola=k.rola, zasob=k.zasob, operacje=_ops(k.operacje), sposob=k.sposob,
                    typ_rekordu=k.typ_rekordu, opis=k.opis)

    @staticmethod
    def _wiersz_uzytkownika(u: Uzytkownik) -> dict:
        return dict(
            id=u.id, imie_nazwisko=u.imie_nazwisko, rola_funkcyjna=u.rola_funkcyjna, poziom=u.poziom,
            jednostka=u.jednostka, zespol=u.zespol, plemie=u.plemie, chapter=u.chapter, stanowisko=u.stanowisko,
            forma=u.forma.value, data_konca_umowy=u.data_konca_umowy, przelozony_id=u.przelozony_id,
            kierownik_umowy_id=u.kierownik_umowy_id, aktywny=u.aktywny, zespol_tymczasowy=u.zespol_tymczasowy,
            poprzedni_zespol=u.poprzedni_zespol, data_przeniesienia=u.data_przeniesienia,
            data_zatrudnienia=u.data_zatrudnienia, ostatnia_aktywnosc=u.ostatnia_aktywnosc,
            wyznaczony_wynagrodzenia_zarzadu=u.wyznaczony_wynagrodzenia_zarzadu,
            atrybuty=dict(
                oswiadczenia_nda=sorted(u.oswiadczenia_nda), przypisani_klienci=sorted(u.przypisani_klienci),
                zespoly_wspierane=sorted(u.zespoly_wspierane), jednostki_hrbp=sorted(u.jednostki_hrbp),
                dyzury=_okresy(u.dyzury), zmiany_wsparcia=_okresy(u.zmiany_wsparcia),
                nieobecnosci=_okresy(u.nieobecnosci), incydenty=_incydenty(u.incydenty),
                sprawy_iod=_incydenty(u.sprawy_iod),
                zastepstwa=[dict(zastepowany_id=z.zastepowany_id, od=_iso(z.okres.od), do=_iso(z.okres.do))
                            for z in u.zastepstwa],
                ostatnie_uzycie={k: _iso(t) for k, t in u.ostatnie_uzycie.items()}))

    @staticmethod
    def _wiersz_obiektu(o: Obiekt) -> dict:
        return dict(id=o.id, zasob_id=o.zasob, nazwa=o.nazwa, zespol=o.zespol, plemie=o.plemie, jednostka=o.jednostka,
                    klient=o.klient, typ_rekordu=o.typ_rekordu, autor_id=o.autor_id, proces=o.proces, kwota=o.kwota,
                    dotyczy_osoby_id=o.dotyczy_osoby_id, obslugujacy_id=o.obslugujacy_id,
                    aktywna_oferta=o.aktywna_oferta, termin_przechowywania=o.termin_przechowywania,
                    zrodlo_id=o.zrodlo_id,
                    atrybuty=dict(komisja=sorted(o.komisja), zatwierdzone_przez=list(o.zatwierdzone_przez)))

    # ------------------------------------------------------------------
    # Odczyt stanu
    # ------------------------------------------------------------------
    def wczytaj_stan(self) -> SystemDostepu:
        r = Rejestr()
        with self.silnik.connect() as p:
            uprz, wlasn, upow, przyd = {}, {}, {}, {}
            for w in p.execute(select(przypisania_uprzywilejowane)).mappings():
                uprz.setdefault(w["uzytkownik_id"], set()).add(w["rola_id"])
            for w in p.execute(select(wlasciciele_zasobow)).mappings():
                wlasn.setdefault(w["uzytkownik_id"], set()).add(w["zasob_id"])
            for w in p.execute(select(upowaznienia)).mappings():
                upow[w["uzytkownik_id"]] = Upowaznienie(frozenset(w["zakres"].split()), w["od"], w["do"], w["odwolane_o"])
            for w in p.execute(select(przydzialy).order_by(przydzialy.c.id)).mappings():
                przyd.setdefault(w["uzytkownik_id"], []).append(Przydzial(
                    w["zasob_id"], frozenset(Operacja(x) for x in w["operacje"]), w["typ_rekordu"],
                    Okres(w["od"], w["do"]) if w["od"] else None, w["wniosek_id"], w["awaryjny"],
                    w["ostatnia_recertyfikacja"]))
            for w in p.execute(select(uzytkownicy)).mappings():
                a = w["atrybuty"]
                u = Uzytkownik(
                    w["id"], w["imie_nazwisko"], w["rola_funkcyjna"], w["poziom"], w["jednostka"],
                    forma=FormaWspolpracy(w["forma"]), data_konca_umowy=w["data_konca_umowy"],
                    stanowisko=w["stanowisko"] or "", zespol=w["zespol"], plemie=w["plemie"], chapter=w["chapter"],
                    przelozony_id=w["przelozony_id"], aktywny=w["aktywny"],
                    oswiadczenia_nda=set(a["oswiadczenia_nda"]), dyzury=_z_okresow(a["dyzury"]),
                    zmiany_wsparcia=_z_okresow(a["zmiany_wsparcia"]), incydenty=_z_incydentow(a["incydenty"]),
                    sprawy_iod=_z_incydentow(a["sprawy_iod"]), przypisani_klienci=set(a["przypisani_klienci"]),
                    zespoly_wspierane=set(a["zespoly_wspierane"]), jednostki_hrbp=set(a["jednostki_hrbp"]),
                    zespol_tymczasowy=w["zespol_tymczasowy"], poprzedni_zespol=w["poprzedni_zespol"],
                    data_przeniesienia=w["data_przeniesienia"],
                    zastepstwa=[Zastepstwo(z["zastepowany_id"], Okres(_dt(z["od"]), _dt(z["do"])))
                                for z in a["zastepstwa"]],
                    wyznaczony_wynagrodzenia_zarzadu=w["wyznaczony_wynagrodzenia_zarzadu"],
                    przydzialy=przyd.get(w["id"], []), role_uprzywilejowane=uprz.get(w["id"], set()),
                    wlasciciel_zasobow=wlasn.get(w["id"], set()), upowaznienie=upow.get(w["id"]),
                    kierownik_umowy_id=w["kierownik_umowy_id"], nieobecnosci=_z_okresow(a["nieobecnosci"]),
                    ostatnia_aktywnosc=w["ostatnia_aktywnosc"],
                    ostatnie_uzycie={k: _dt(t) for k, t in a["ostatnie_uzycie"].items()},
                    data_zatrudnienia=w["data_zatrudnienia"])
                r.dodaj(u)
            for w in p.execute(select(konta)).mappings():
                r.dodaj(Konto(w["id"], w["uzytkownik_id"], TypKonta(w["typ"]), w["aktywne"], w["rola_id"],
                              w["zablokowane_o"], w["powod_blokady"] or ""))
            role_sesji = {}
            for w in p.execute(select(sesje_role)).mappings():
                role_sesji.setdefault(w["sesja_id"], {})[w["rola_id"]] = Okres(w["od"], w["do"])
            for w in p.execute(select(sesje)).mappings():
                r.dodaj(Sesja(w["id"], w["konto_id"], role_sesji.get(w["id"], {}), w["numer_zgloszenia"]))
            for w in p.execute(select(obiekty)).mappings():
                a = w["atrybuty"]
                r.dodaj(Obiekt(w["id"], w["zasob_id"], w["nazwa"], w["zespol"], w["plemie"], w["jednostka"], w["klient"],
                               w["typ_rekordu"], w["autor_id"], w["proces"], w["kwota"], w["dotyczy_osoby_id"],
                               set(a["komisja"]), w["obslugujacy_id"], w["aktywna_oferta"],
                               w["termin_przechowywania"], list(a["zatwierdzone_przez"]), w["zrodlo_id"]))
            r.katalog = [PozycjaKatalogu(w["rola_id"], w["zasob_id"], frozenset(Operacja(x) for x in w["operacje"]),
                                         w["sposob"], w["typ_rekordu"], w["opis"] or "")
                         for w in p.execute(select(katalog).order_by(katalog.c.id)).mappings()]

            dz = Dziennik()
            dz._wpisy = [WpisDziennika(w["nr"], w["czas"], w["zdarzenie"], tuple(sorted(w["dane"].items())),
                                       w["skrot_poprzedni"], w["skrot"])
                         for w in p.execute(select(dziennik).order_by(dziennik.c.nr)).mappings()]
            s = SystemDostepu(r, dz)
            s.sygnaly = [(w["czas"], w["tekst"]) for w in p.execute(select(sygnaly).order_by(sygnaly.c.nr)).mappings()]
            s.przeglady = [ZadaniePrzegladu(**w) for w in p.execute(select(zadania_przegladu)).mappings()]
            for w in p.execute(select(pozycje_recertyfikacji)).mappings():
                s.recertyfikacja.pozycje[w["id"]] = PozycjaPrzegladu(**w)
            wymagania = {}
            for w in p.execute(select(wymagania_wnioskow).order_by(wymagania_wnioskow.c.id)).mappings():
                wymagania.setdefault(w["wniosek_id"], []).append(
                    Wymaganie(w["rola"], list(w["kandydaci"]), w["udzielona_przez"], w["czas"]))
            for w in p.execute(select(wnioski)).mappings():
                s.wnioski.wnioski[w["id"]] = Wniosek(
                    w["id"], w["wnioskujacy_id"], w["beneficjent_id"], w["zasob_id"],
                    frozenset(Operacja(x) for x in w["operacje"]), w["typ_rekordu"], w["uzasadnienie"] or "",
                    w["okres_dni"], w["zlozony_o"], StatusWniosku(w["status"]), wymagania.get(w["id"], []),
                    w["powod"] or "", (w["reguly"] or "").split())
            for w in p.execute(select(prosby)).mappings():
                if w["rodzaj"] == "aktywacja":
                    s.sesje.prosby[w["id"]] = dict(w["dane"])
                else:
                    d = dict(w["dane"])
                    k = d["pozycja"]
                    d["pozycja"] = PozycjaKatalogu(k["rola"], k["zasob"], frozenset(Operacja(x) for x in k["operacje"]),
                                                   k["sposob"], k["typ_rekordu"], k["opis"])
                    s.wnioski.zmiany_katalogu[w["id"]] = d
        stan = self.ustawienie("stan_procesow", {})
        s.liczniki = dict(stan.get("liczniki", {}))
        s.recertyfikacja.ostatnia = {(u, k): _dt(t) for u, k, t in stan.get("recertyfikacja_ostatnia", [])}
        s.kadry.zgloszone_nieuzywane = {tuple(x) for x in stan.get("zgloszone_nieuzywane", [])}
        return s
