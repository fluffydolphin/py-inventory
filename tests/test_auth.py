BOLT = {
    "sku": "ABC",
    "name": "Test bolt",
    "unit": "ea",
    "cost_cents": 25,
}


def test_login_returns_token(client, admin_user):
    response = client.post(
        "/auth/login",
        json={"email": "admin@test.com", "password": "secret"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]


def test_login_wrong_password(client, admin_user):
    response = client.post(
        "/auth/login",
        json={"email": "admin@test.com", "password": "nope"},
    )
    assert response.status_code == 401


def test_create_product_without_token(client):
    response = client.post("/products", json=BOLT)
    assert response.status_code == 401


def test_purchaser_cannot_create_product(purchaser_client):
    response = purchaser_client.post("/products", json=BOLT)
    assert response.status_code == 403
    assert response.json()["detail"] == "Admin only"
