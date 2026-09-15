def test_adjust_damaged_reduces_qty(warehouse_client, stocked_product):
    response = warehouse_client.post(
        "/stock/adjustments",
        json={
            "product_id": stocked_product.id,
            "qty_delta": -2,
            "reason": "damaged",
        },
    )
    assert response.status_code == 200
    assert response.json()["qty_on_hand"] == 8
    movements = warehouse_client.get(f"/products/{stocked_product.id}/movements")
    assert movements.status_code == 200
    assert len(movements.json()) == 1
    assert movements.json()[0]["qty_delta"] == -2
    assert movements.json()[0]["reason"] == "adjustment"
    assert movements.json()[0]["ref_type"] == "damaged"


def test_adjust_cannot_go_below_zero(warehouse_client, stocked_product):
    response = warehouse_client.post(
        "/stock/adjustments",
        json={
            "product_id": stocked_product.id,
            "qty_delta": -11,
            "reason": "damaged",
        },
    )
    assert response.status_code == 400
    assert warehouse_client.get("/products").json()[0]["qty_on_hand"] == 10


def test_cycle_count_can_increase_qty(warehouse_client, stocked_product):
    response = warehouse_client.post(
        "/stock/adjustments",
        json={
            "product_id": stocked_product.id,
            "qty_delta": 3,
            "reason": "cycle_count",
        },
    )
    assert response.status_code == 200
    assert response.json()["qty_on_hand"] == 13


def test_purchaser_cannot_adjust(purchaser_client, stocked_product):
    response = purchaser_client.post(
        "/stock/adjustments",
        json={
            "product_id": stocked_product.id,
            "qty_delta": -1,
            "reason": "damaged",
        },
    )
    assert response.status_code == 403


def test_low_stock_filter(warehouse_client, db, stocked_product):
    stocked_product.reorder_point = 12
    db.commit()
    low = warehouse_client.get("/stock", params={"low_stock": True})
    assert low.status_code == 200
    assert [row["id"] for row in low.json()] == [stocked_product.id]
    stocked_product.reorder_point = 5
    db.commit()
    none = warehouse_client.get("/stock", params={"low_stock": True})
    assert none.json() == []
