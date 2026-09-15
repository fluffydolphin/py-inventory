def test_receive_partial_then_complete(warehouse_client, submitted_po):
    po, line = submitted_po
    first = warehouse_client.post(
        f"/purchase-orders/{po.id}/receive",
        json={
            "idempotency_key": "recv-partial",
            "lines": [{"po_line_id": line.id, "qty": 4}],
        },
    )
    assert first.status_code == 200
    assert first.json()["status"] == "partial"
    assert first.json()["lines"][0]["qty_received"] == 4
    assert warehouse_client.get("/products").json()[0]["qty_on_hand"] == 4

    second = warehouse_client.post(
        f"/purchase-orders/{po.id}/receive",
        json={
            "idempotency_key": "recv-rest",
            "lines": [{"po_line_id": line.id, "qty": 6}],
        },
    )
    assert second.status_code == 200
    assert second.json()["status"] == "received"
    assert second.json()["lines"][0]["qty_received"] == 10
    assert warehouse_client.get("/products").json()[0]["qty_on_hand"] == 10


def test_receive_more_than_remaining(warehouse_client, submitted_po):
    po, line = submitted_po
    warehouse_client.post(
        f"/purchase-orders/{po.id}/receive",
        json={
            "idempotency_key": "recv-4",
            "lines": [{"po_line_id": line.id, "qty": 4}],
        },
    )
    response = warehouse_client.post(
        f"/purchase-orders/{po.id}/receive",
        json={
            "idempotency_key": "recv-too-many",
            "lines": [{"po_line_id": line.id, "qty": 7}],
        },
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Cannot receive more than ordered"


def test_idempotent_receive_does_not_double_stock(warehouse_client, submitted_po):
    po, line = submitted_po
    payload = {
        "idempotency_key": "recv-same",
        "lines": [{"po_line_id": line.id, "qty": 4}],
    }
    first = warehouse_client.post(f"/purchase-orders/{po.id}/receive", json=payload)
    second = warehouse_client.post(f"/purchase-orders/{po.id}/receive", json=payload)
    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["lines"][0]["qty_received"] == 4
    assert warehouse_client.get("/products").json()[0]["qty_on_hand"] == 4
    movements = warehouse_client.get(f"/products/{line.product_id}/movements")
    assert movements.status_code == 200
    assert len(movements.json()) == 1
    assert movements.json()[0]["qty_delta"] == 4


def test_purchaser_cannot_receive(purchaser_client, submitted_po):
    po, line = submitted_po
    response = purchaser_client.post(
        f"/purchase-orders/{po.id}/receive",
        json={
            "idempotency_key": "recv-nope",
            "lines": [{"po_line_id": line.id, "qty": 1}],
        },
    )
    assert response.status_code == 403


def test_cannot_receive_draft(purchaser_client, warehouse_user, supplier, product):
    created = purchaser_client.post(
        "/purchase-orders",
        json={
            "supplier_id": supplier.id,
            "lines": [
                {"product_id": product.id, "qty_ordered": 10, "unit_cost_cents": 25}
            ],
        },
    )
    assert created.status_code == 201
    po_id = created.json()["id"]
    line_id = created.json()["lines"][0]["id"]
    login = purchaser_client.post(
        "/auth/login",
        json={"email": "warehouse@test.com", "password": "secret"},
    )
    purchaser_client.headers["Authorization"] = f"Bearer {login.json()['access_token']}"
    response = purchaser_client.post(
        f"/purchase-orders/{po_id}/receive",
        json={
            "idempotency_key": "recv-draft",
            "lines": [{"po_line_id": line_id, "qty": 1}],
        },
    )
    assert response.status_code == 400
