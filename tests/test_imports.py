import io


def _csv(rows: list[list[str]]) -> bytes:
    buffer = io.StringIO()
    buffer.write("sku,name,unit,cost_cents,opening_qty\n")
    for row in rows:
        buffer.write(",".join(row) + "\n")
    return buffer.getvalue().encode()


def test_import_partial_success(admin_client):
    rows = []
    for i in range(1, 101):
        if i in (10, 20, 47):
            rows.append(["", f"Bad {i}", "ea", "10", "0"])
        else:
            rows.append([f"SKU-{i:03d}", f"Part {i}", "ea", "25", "0"])
    response = admin_client.post(
        "/imports/products",
        files={"file": ("parts.csv", _csv(rows), "text/csv")},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "completed_with_errors"
    assert body["imported_count"] == 97
    assert body["error_count"] == 3

    products = admin_client.get("/products").json()
    assert len(products) == 97

    errors = admin_client.get(f"/imports/{body['id']}/errors").json()
    assert len(errors) == 3
    assert {row["row_number"] for row in errors} == {11, 21, 48}
    assert all(row["message"] == "sku is required" for row in errors)


def test_duplicate_sku_in_file(admin_client):
    rows = [
        ["BOLT-M8", "Bolt", "ea", "25", "0"],
        ["BOLT-M8", "Bolt copy", "ea", "25", "0"],
        ["NUT-M8", "Nut", "ea", "15", "0"],
    ]
    response = admin_client.post(
        "/imports/products",
        files={"file": ("dups.csv", _csv(rows), "text/csv")},
    )
    assert response.json()["imported_count"] == 2
    assert response.json()["error_count"] == 1
    errors = admin_client.get(f"/imports/{response.json()['id']}/errors").json()
    assert errors[0]["message"] == "Duplicate SKU in this file"
    assert errors[0]["row_number"] == 3


def test_duplicate_sku_in_db(admin_client, product):
    rows = [
        [product.sku, "Should fail", "ea", "25", "0"],
        ["WASHER-M8", "Washer", "ea", "5", "0"],
    ]
    response = admin_client.post(
        "/imports/products",
        files={"file": ("dbdup.csv", _csv(rows), "text/csv")},
    )
    assert response.json()["imported_count"] == 1
    assert response.json()["error_count"] == 1
    errors = admin_client.get(f"/imports/{response.json()['id']}/errors").json()
    assert errors[0]["message"] == "SKU already exists"


def test_opening_qty_writes_movement(admin_client):
    rows = [["PAINT-1", "Paint", "l", "400", "12"]]
    response = admin_client.post(
        "/imports/products",
        files={"file": ("open.csv", _csv(rows), "text/csv")},
    )
    assert response.json()["status"] == "completed"
    products = admin_client.get("/products").json()
    assert products[0]["qty_on_hand"] == 12
    movements = admin_client.get(f"/products/{products[0]['id']}/movements").json()
    assert len(movements) == 1
    assert movements[0]["reason"] == "import"
    assert movements[0]["qty_delta"] == 12


def test_purchaser_cannot_import(purchaser_client):
    response = purchaser_client.post(
        "/imports/products",
        files={"file": ("nope.csv", _csv([["A", "A", "ea", "1", "0"]]), "text/csv")},
    )
    assert response.status_code == 403
