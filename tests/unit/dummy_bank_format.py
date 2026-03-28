from firefly_bank_importer.bank_formats.base import HeaderBankFormat

DUMMY_HEADERS = ["Booked", "Narrative", "Category", "Amount", "RunningBalance"]

DUMMY_FORMAT = HeaderBankFormat(
    name="dummybank",
    required_headers=frozenset({"Booked", "Narrative", "Amount"}),
    date_header="Booked",
    description_header="Narrative",
    amount_header="Amount",
    transaction_type_header="Category",
    balance_header="RunningBalance",
)
