import json

from fastapi.testclient import TestClient

CSV_STATEMENT = """Data;Descrição;Valor;Tipo;ID
03/10/2026;Salário;1.000,00;receita;salary-1
04/10/2026;Mercado;125,50;despesa;market-1
""".encode()

OFX_V1_STATEMENT = b"""OFXHEADER:100
DATA:OFXSGML
VERSION:102
SECURITY:NONE
ENCODING:USASCII
CHARSET:1252
COMPRESSION:NONE
OLDFILEUID:NONE
NEWFILEUID:NONE

<OFX><SIGNONMSGSRSV1><SONRS><STATUS><CODE>0<SEVERITY>INFO</STATUS><DTSERVER>20261004120000[-3:BRT]<LANGUAGE>POR</SONRS></SIGNONMSGSRSV1><BANKMSGSRSV1><STMTTRNRS><TRNUID>1<STATUS><CODE>0<SEVERITY>INFO</STATUS><STMTRS><CURDEF>BRL<BANKACCTFROM><BANKID>001<ACCTID>123<ACCTTYPE>CHECKING</BANKACCTFROM><BANKTRANLIST><DTSTART>20261001000000[-3:BRT]<DTEND>20261004235959[-3:BRT]<STMTTRN><TRNTYPE>DEBIT<DTPOSTED>20261003120000[-3:BRT]<TRNAMT>-25.50<FITID>bank-1<MEMO>Mercado</STMTTRN></BANKTRANLIST><LEDGERBAL><BALAMT>974.50<DTASOF>20261004120000[-3:BRT]</LEDGERBAL></STMTRS></STMTTRNRS></BANKMSGSRSV1></OFX>"""

OFX_V2_STATEMENT = b"""<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<?OFX OFXHEADER="200" VERSION="203" SECURITY="NONE" OLDFILEUID="NONE" NEWFILEUID="NONE"?>
<OFX><SIGNONMSGSRSV1><SONRS><STATUS><CODE>0</CODE><SEVERITY>INFO</SEVERITY></STATUS><DTSERVER>20261004120000[-3:BRT]</DTSERVER><LANGUAGE>POR</LANGUAGE></SONRS></SIGNONMSGSRSV1><CREDITCARDMSGSRSV1><CCSTMTTRNRS><TRNUID>1</TRNUID><STATUS><CODE>0</CODE><SEVERITY>INFO</SEVERITY></STATUS><CCSTMTRS><CURDEF>BRL</CURDEF><CCACCTFROM><ACCTID>999</ACCTID></CCACCTFROM><BANKTRANLIST><DTSTART>20261001000000[-3:BRT]</DTSTART><DTEND>20261004235959[-3:BRT]</DTEND><STMTTRN><TRNTYPE>DEBIT</TRNTYPE><DTPOSTED>20261003120000[-3:BRT]</DTPOSTED><TRNAMT>-50.00</TRNAMT><FITID>card-1</FITID><NAME>Cafe</NAME><MEMO>Almoco</MEMO></STMTTRN></BANKTRANLIST><LEDGERBAL><BALAMT>-50.00</BALAMT><DTASOF>20261004120000[-3:BRT]</DTASOF></LEDGERBAL></CCSTMTRS></CCSTMTTRNRS></CREDITCARDMSGSRSV1></OFX>"""


def _upload(
    client: TestClient,
    headers: dict,
    wallet_id: int,
    content: bytes = CSV_STATEMENT,
    filename: str = "statement.csv",
    options: dict[str, str] | None = None,
):
    data = {"wallet_id": str(wallet_id)}
    if options is not None:
        data["options"] = json.dumps(options)
    return client.post(
        "/api/v1/imports/",
        data=data,
        files={"file": (filename, content, "application/octet-stream")},
        headers=headers,
    )


def test_csv_preview_and_confirm_are_atomic(
    client: TestClient, auth_headers: dict, wallet: dict, category: dict
) -> None:
    preview = _upload(client, auth_headers, wallet["id"])
    assert preview.status_code == 201
    data = preview.json()
    assert data["batch"]["status"] == "PREVIEW"
    assert data["batch"]["total_rows"] == 2
    assert data["batch"]["valid_rows"] == 2
    assert [item["status"] for item in data["items"]] == ["READY", "READY"]

    batch_id = data["batch"]["id"]
    confirmed = client.post(
        f"/api/v1/imports/{batch_id}/confirm",
        json={"default_category_id": category["id"]},
        headers=auth_headers,
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["batch"]["status"] == "COMPLETED"
    assert confirmed.json()["batch"]["imported_rows"] == 2
    assert all(item["status"] == "IMPORTED" for item in confirmed.json()["items"])

    wallet_detail = client.get(f"/api/v1/wallets/{wallet['id']}", headers=auth_headers)
    assert wallet_detail.json()["balance"] == "1874.50"
    transactions = client.get(
        f"/api/v1/transactions/?wallet_id={wallet['id']}", headers=auth_headers
    ).json()
    assert {transaction["source"] for transaction in transactions} == {"CSV"}
    assert {transaction["category_id"] for transaction in transactions} == {category["id"]}
    assert all(transaction["external_id"].startswith("csv:") for transaction in transactions)


def test_reimport_marks_existing_rows_as_duplicates(
    client: TestClient, auth_headers: dict, wallet: dict
) -> None:
    first = _upload(client, auth_headers, wallet["id"]).json()
    client.post(
        f"/api/v1/imports/{first['batch']['id']}/confirm",
        json={},
        headers=auth_headers,
    )

    second = _upload(client, auth_headers, wallet["id"])
    assert second.status_code == 201
    assert second.json()["batch"]["duplicate_rows"] == 2
    assert all(item["status"] == "DUPLICATE" for item in second.json()["items"])

    confirmed = client.post(
        f"/api/v1/imports/{second.json()['batch']['id']}/confirm",
        json={},
        headers=auth_headers,
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["batch"]["imported_rows"] == 0
    transactions = client.get(
        f"/api/v1/transactions/?wallet_id={wallet['id']}", headers=auth_headers
    )
    assert len(transactions.json()) == 2


def test_csv_custom_mapping_and_row_exclusion(
    client: TestClient, auth_headers: dict, wallet: dict
) -> None:
    content = (
        b"Quando|Texto|Debito|Credito|Ref\n03-10-2026|Cafe|10,00||a\n04-10-2026|Pix||25,00|b\n"
    )
    preview = _upload(
        client,
        auth_headers,
        wallet["id"],
        content,
        options={
            "delimiter": "|",
            "date": "Quando",
            "description": "Texto",
            "debit": "Debito",
            "credit": "Credito",
            "id": "Ref",
        },
    ).json()
    confirmed = client.post(
        f"/api/v1/imports/{preview['batch']['id']}/confirm",
        json={"rows": [{"row_number": 2, "include": False}]},
        headers=auth_headers,
    )
    assert confirmed.status_code == 200
    assert [item["status"] for item in confirmed.json()["items"]] == [
        "IGNORED",
        "IMPORTED",
    ]
    assert confirmed.json()["batch"]["imported_rows"] == 1


def test_invalid_csv_rows_remain_visible_in_preview(
    client: TestClient, auth_headers: dict, wallet: dict
) -> None:
    content = b"Data;Descricao;Valor\n99/99/2026;Bad date;-10,00\n04/10/2026;Zero;0\n"
    response = _upload(client, auth_headers, wallet["id"], content)
    assert response.status_code == 201
    assert response.json()["batch"]["invalid_rows"] == 2
    assert all(item["status"] == "INVALID" for item in response.json()["items"])


def test_ofx_v1_and_v2_are_parsed(client: TestClient, auth_headers: dict, wallet: dict) -> None:
    bank = _upload(client, auth_headers, wallet["id"], OFX_V1_STATEMENT, "bank.ofx")
    card = _upload(client, auth_headers, wallet["id"], OFX_V2_STATEMENT, "card.qfx")
    assert bank.status_code == 201
    assert card.status_code == 201
    assert bank.json()["items"][0]["external_id"] == "ofx:bank-1"
    assert card.json()["items"][0]["external_id"] == "ofx:card-1"
    assert card.json()["items"][0]["description"] == "Cafe - Almoco"


def test_import_confirmation_rolls_back_when_balance_is_insufficient(
    client: TestClient, auth_headers: dict, wallet: dict
) -> None:
    content = b"Data;Descricao;Valor\n04/10/2026;Large expense;-2000,00\n"
    preview = _upload(client, auth_headers, wallet["id"], content).json()
    batch_id = preview["batch"]["id"]
    confirmed = client.post(f"/api/v1/imports/{batch_id}/confirm", json={}, headers=auth_headers)
    assert confirmed.status_code == 400

    after = client.get(f"/api/v1/imports/{batch_id}/preview", headers=auth_headers)
    assert after.json()["batch"]["status"] == "PREVIEW"
    assert after.json()["items"][0]["status"] == "READY"
    wallet_detail = client.get(f"/api/v1/wallets/{wallet['id']}", headers=auth_headers)
    assert wallet_detail.json()["balance"] == "1000.00"


def test_import_history_lifecycle_and_ownership(
    client: TestClient, auth_headers: dict, wallet: dict
) -> None:
    preview = _upload(client, auth_headers, wallet["id"]).json()
    batch_id = preview["batch"]["id"]
    assert client.get("/api/v1/imports/", headers=auth_headers).json()[0]["id"] == batch_id
    assert client.get(f"/api/v1/imports/{batch_id}", headers=auth_headers).status_code == 200

    client.post(
        "/api/v1/auth/register",
        json={"email": "imports-other@example.com", "password": "password123"},
    )
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "imports-other@example.com", "password": "password123"},
    )
    other_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    assert client.get(f"/api/v1/imports/{batch_id}", headers=other_headers).status_code == 404

    deleted = client.delete(f"/api/v1/imports/{batch_id}", headers=auth_headers)
    assert deleted.status_code == 204
    assert client.get(f"/api/v1/imports/{batch_id}", headers=auth_headers).status_code == 404


def test_completed_import_cannot_be_confirmed_or_deleted(
    client: TestClient, auth_headers: dict, wallet: dict
) -> None:
    preview = _upload(client, auth_headers, wallet["id"]).json()
    batch_id = preview["batch"]["id"]
    assert (
        client.post(
            f"/api/v1/imports/{batch_id}/confirm", json={}, headers=auth_headers
        ).status_code
        == 200
    )
    assert (
        client.post(
            f"/api/v1/imports/{batch_id}/confirm", json={}, headers=auth_headers
        ).status_code
        == 409
    )
    assert client.delete(f"/api/v1/imports/{batch_id}", headers=auth_headers).status_code == 409


def test_import_rejects_unsupported_file_and_bad_options(
    client: TestClient, auth_headers: dict, wallet: dict
) -> None:
    unsupported = _upload(client, auth_headers, wallet["id"], b"hello", "statement.txt")
    assert unsupported.status_code == 422
    bad_options = client.post(
        "/api/v1/imports/",
        data={"wallet_id": str(wallet["id"]), "options": "not-json"},
        files={"file": ("statement.csv", CSV_STATEMENT, "text/csv")},
        headers=auth_headers,
    )
    assert bad_options.status_code == 422


def test_csv_parser_handles_us_numbers_parentheses_and_generated_fingerprint(
    client: TestClient, auth_headers: dict, wallet: dict
) -> None:
    content = b'Date,Amount\n2026-10-03,"(1,234.56)"\n'
    response = _upload(client, auth_headers, wallet["id"], content)
    assert response.status_code == 201
    item = response.json()["items"][0]
    assert item["amount"] == "1234.56"
    assert item["transaction_type"] == "EXPENSE"
    assert item["description"] == "Imported transaction"
    assert item["external_id"].startswith("csv:")


def test_csv_date_format_and_invalid_layout_errors(
    client: TestClient, auth_headers: dict, wallet: dict
) -> None:
    custom_date = _upload(
        client,
        auth_headers,
        wallet["id"],
        b"When;Amount\n20261003;10.00\n",
        options={"date": "When", "amount": "Amount", "date_format": "%Y%m%d"},
    )
    assert custom_date.status_code == 201

    invalid_delimiter = _upload(
        client,
        auth_headers,
        wallet["id"],
        CSV_STATEMENT,
        options={"delimiter": ":"},
    )
    assert invalid_delimiter.status_code == 422
    missing_date = _upload(client, auth_headers, wallet["id"], b"Description;Amount\nCafe;10\n")
    assert missing_date.status_code == 422
    missing_amount = _upload(
        client, auth_headers, wallet["id"], b"Date;Description\n03/10/2026;Cafe\n"
    )
    assert missing_amount.status_code == 422
    missing_configured_column = _upload(
        client,
        auth_headers,
        wallet["id"],
        CSV_STATEMENT,
        options={"date": "NotThere"},
    )
    assert missing_configured_column.status_code == 422


def test_import_rejects_empty_malformed_and_currency_mismatch(
    client: TestClient, auth_headers: dict, wallet: dict
) -> None:
    assert _upload(client, auth_headers, wallet["id"], b"").status_code == 422
    assert _upload(client, auth_headers, wallet["id"], b"not an ofx", "bad.ofx").status_code == 422
    usd_wallet = client.post(
        "/api/v1/wallets/",
        json={"name": "USD", "currency": "USD", "initial_balance": "100.00"},
        headers=auth_headers,
    ).json()
    mismatch = _upload(client, auth_headers, usd_wallet["id"], OFX_V1_STATEMENT, "bank.ofx")
    assert mismatch.status_code == 422


def test_confirmation_validates_rows_and_categories(
    client: TestClient, auth_headers: dict, wallet: dict
) -> None:
    preview = _upload(client, auth_headers, wallet["id"]).json()
    batch_id = preview["batch"]["id"]
    unknown_row = client.post(
        f"/api/v1/imports/{batch_id}/confirm",
        json={"rows": [{"row_number": 999, "include": False}]},
        headers=auth_headers,
    )
    assert unknown_row.status_code == 422
    unknown_category = client.post(
        f"/api/v1/imports/{batch_id}/confirm",
        json={"default_category_id": 99999},
        headers=auth_headers,
    )
    assert unknown_category.status_code == 422
    repeated_rows = client.post(
        f"/api/v1/imports/{batch_id}/confirm",
        json={
            "rows": [
                {"row_number": 2, "include": True},
                {"row_number": 2, "include": False},
            ]
        },
        headers=auth_headers,
    )
    assert repeated_rows.status_code == 422


def test_missing_import_routes_return_not_found(client: TestClient, auth_headers: dict) -> None:
    assert client.get("/api/v1/imports/99999", headers=auth_headers).status_code == 404
    assert client.get("/api/v1/imports/99999/preview", headers=auth_headers).status_code == 404
    assert (
        client.post("/api/v1/imports/99999/confirm", json={}, headers=auth_headers).status_code
        == 404
    )
    assert client.delete("/api/v1/imports/99999", headers=auth_headers).status_code == 404


def test_options_must_be_string_mapping(
    client: TestClient, auth_headers: dict, wallet: dict
) -> None:
    response = client.post(
        "/api/v1/imports/",
        data={"wallet_id": str(wallet["id"]), "options": '["date"]'},
        files={"file": ("statement.csv", CSV_STATEMENT, "text/csv")},
        headers=auth_headers,
    )
    assert response.status_code == 422
