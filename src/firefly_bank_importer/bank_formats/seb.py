from firefly_bank_importer.bank_formats.base import HeaderBankFormat

SEB_FORMAT = HeaderBankFormat(
    name="seb",
    required_headers=frozenset({"Bokföringsdatum", "Text", "Belopp"}),
    date_header="Bokföringsdatum",
    description_header="Text",
    amount_header="Belopp",
    balance_header="Saldo",
)
