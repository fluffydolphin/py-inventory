def _po_body(supplier, product, qty=10, cost=25):
    return {
        "supplier_id": supplier.id,
        "lines": [
            {
                "product_id": product.id,
                "qty_ordered": qty,
                "unit_cost_cents": cost,
            }
        ],
    }


def test_create_po_is_draft(purchaser_client, supplier, product):
    response = purchaser_client.post("/purchase-orders", json=_po_body(supplier, product))
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "draft"
    assert body["po_number"].startswith("PO-")
    assert body["submitted_at"] is None
    assert len(body["lines"]) == 1
    assert body["lines"][0]["qty_ordered"] == 10
    assert body["lines"][0]["qty_received"] == 0


def test_duplicate_product_on_po_rejected(purchaser_client, supplier, product):
    payload = {
        "supplier_id": supplier.id,
        "lines": [
            {"product_id": product.id, "qty_ordered": 4, "unit_cost_cents": 25},
            {"product_id": product.id, "qty_ordered": 6, "unit_cost_cents": 25},
        ],
    }
    response = purchaser_client.post("/purchase-orders", json=payload)
    assert response.status_code == 400
    assert response.json()["detail"] == "Duplicate product on one PO"


def test_submit_draft(purchaser_client, supplier, product):
    created = purchaser_client.post("/purchase-orders", json=_po_body(supplier, product))
    po_id = created.json()["id"]
    response = purchaser_client.post(f"/purchase-orders/{po_id}/submit")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "submitted"
    assert body["submitted_at"] is not None


def test_submit_twice_rejected(purchaser_client, supplier, product):
    created = purchaser_client.post("/purchase-orders", json=_po_body(supplier, product))
    po_id = created.json()["id"]
    assert purchaser_client.post(f"/purchase-orders/{po_id}/submit").status_code == 200
    second = purchaser_client.post(f"/purchase-orders/{po_id}/submit")
    assert second.status_code == 400


def test_cancel_draft(purchaser_client, supplier, product):
    created = purchaser_client.post("/purchase-orders", json=_po_body(supplier, product))
    po_id = created.json()["id"]
    response = purchaser_client.post(f"/purchase-orders/{po_id}/cancel")
    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"


def test_warehouse_cannot_create_po(warehouse_client, supplier, product):
    response = warehouse_client.post("/purchase-orders", json=_po_body(supplier, product))
    assert response.status_code == 403


def test_missing_supplier(purchaser_client, product):
    payload = {
        "supplier_id": 999,
        "lines": [
            {"product_id": product.id, "qty_ordered": 10, "unit_cost_cents": 25},
        ],
    }
    response = purchaser_client.post("/purchase-orders", json=payload)
    assert response.status_code == 404


def test_list_filter_by_status(purchaser_client, supplier, product):
    purchaser_client.post("/purchase-orders", json=_po_body(supplier, product, qty=1))
    submitted = purchaser_client.post("/purchase-orders", json=_po_body(supplier, product, qty=2))
    po_id = submitted.json()["id"]
    purchaser_client.post(f"/purchase-orders/{po_id}/submit")
    drafts = purchaser_client.get("/purchase-orders", params={"status": "draft"})
    assert drafts.status_code == 200
    assert all(row["status"] == "draft" for row in drafts.json())
    assert len(drafts.json()) == 1
