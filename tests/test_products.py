# pytest collects functions named test_*.
# assert X is the spec: if X is false, the test fails.

BOLT = {
    "sku": "ABC",
    "name": "Test bolt",
    "unit": "ea",
    "cost_cents": 25,
}


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_create_product(admin_client):
    response = admin_client.post("/products", json=BOLT)
    assert response.status_code == 201
    body = response.json()
    assert body["sku"] == "ABC"
    assert body["cost_cents"] == 25
    assert body["reorder_point"] is None


def test_duplicate_sku_returns_409(admin_client):
    first = admin_client.post("/products", json=BOLT)
    assert first.status_code == 201

    second = admin_client.post("/products", json=BOLT)
    assert second.status_code == 409
    assert second.json()["detail"] == "SKU already exists"


def test_list_products_includes_created(admin_client):
    admin_client.post("/products", json=BOLT)
    response = admin_client.get("/products")
    assert response.status_code == 200
    skus = [row["sku"] for row in response.json()]
    assert skus == ["ABC"]
