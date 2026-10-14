"""Konfiguracja pytest – każdy test dostaje świeżą przykładową organizację."""
import pytest

from dostep.przyklad import TERAZ, X, Y, Przyklad

Swiat = Przyklad  # nazwa używana w testach

__all__ = ["TERAZ", "X", "Y", "Swiat"]


@pytest.fixture
def swiat() -> Przyklad:
    return Przyklad()
