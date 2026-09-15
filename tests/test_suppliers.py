ACME = {"name": "Acme Fasteners", "email": "sales@example.com"}


def test_purchaser_can_create_supplier(purchaser_client):
    response = purchaser_client.post("/suppliers", json=ACME)
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Acme Fasteners"
    assert body["email"] == "sales@example.com"
    assert body["active"] is True


def test_duplicate_supplier_email_returns_409(purchaser_client):
    assert purchaser_client.post("/suppliers", json=ACME).status_code == 201
    second = purchaser_client.post("/suppliers", json=ACME)
    assert second.status_code == 409


def test_warehouse_cannot_create_supplier(warehouse_client):
    response = warehouse_client.post("/suppliers", json=ACME)
    assert response.status_code == 403


def test_list_suppliers_requires_login(client):
    response = client.get("/suppliers")
    assert response.status_code == 401
