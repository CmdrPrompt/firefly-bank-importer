from firefly_bank_importer.bank_formats.base import HeaderBankFormat

ICA_FORMAT = HeaderBankFormat(
    name="ica",
    required_headers=frozenset({"Datum", "Text", "Typ", "Belopp"}),
    date_header="Datum",
    description_header="Text",
    amount_header="Belopp",
    transaction_type_header="Typ",
    balance_header="Saldo",
)
