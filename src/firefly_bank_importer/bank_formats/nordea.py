from firefly_bank_importer.bank_formats.base import HeaderBankFormat

NORDEA_FORMAT = HeaderBankFormat(
    name="nordea",
    required_headers=frozenset({"Bokföringsdag", "Belopp", "Rubrik"}),
    date_header="Bokföringsdag",
    description_header="Rubrik",
    amount_header="Belopp",
    balance_header="Saldo",
    date_format="%Y/%m/%d",
)
