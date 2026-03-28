import pytest

SEB_HEADERS = ["Bokföringsdatum", "Valutadatum", "Text", "Belopp", "Saldo"]
ICA_HEADERS = ["Datum", "Text", "Typ", "Belopp", "Saldo"]


@pytest.fixture()
def seb_headers() -> list[str]:
    return list(SEB_HEADERS)


@pytest.fixture()
def ica_headers() -> list[str]:
    return list(ICA_HEADERS)


def make_seb_row(
    datum: str = "2025-01-15",
    text: str = "ICA Maxi",
    belopp: str = "-250,00",
    saldo: str = "10000,00",
) -> list[str]:
    return [datum, datum, text, belopp, saldo]


def make_ica_row(
    datum: str = "2025-01-15",
    text: str = "ICA Kortköp",
    typ: str = "Kortköp",
    belopp: str = "-250,00",
    saldo: str = "10000,00",
) -> list[str]:
    return [datum, text, typ, belopp, saldo]
