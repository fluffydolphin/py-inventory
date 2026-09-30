"""Simulated warehouse traffic against a running API.

Login once per user (bcrypt is slow). The mix is mostly reads, plus
purchasers who create and submit a PO, and warehouse users who adjust stock.

From the project folder, with the API already up:

    uv run locust -f loadtest/locustfile.py --host http://127.0.0.1:8000

Open http://localhost:8089. StepLoad below ramps 10, 25, 50, then 100 users.
While that class is in this file, --users and --run-time are ignored.
"""

import random
import uuid

from locust import HttpUser, LoadTestShape, between, task


def _login(user: HttpUser, email: str, password: str) -> None:
    response = user.client.post(
        "/auth/login",
        json={"email": email, "password": password},
        name="/auth/login",
    )
    response.raise_for_status()
    token = response.json()["access_token"]
    user.client.headers["Authorization"] = f"Bearer {token}"


class BrowserUser(HttpUser):
    weight = 7
    wait_time = between(1, 3)

    def on_start(self) -> None:
        _login(self, "admin@example.com", "admin")

    @task(10)
    def list_products(self) -> None:
        self.client.get("/products?limit=50", name="/products")

    @task(6)
    def list_stock(self) -> None:
        self.client.get("/stock?limit=50", name="/stock")

    @task(2)
    def list_low_stock(self) -> None:
        self.client.get("/stock?low_stock=true&limit=50", name="/stock?low_stock")

    @task(3)
    def list_purchase_orders(self) -> None:
        self.client.get("/purchase-orders?limit=50", name="/purchase-orders")


class PurchaserUser(HttpUser):
    weight = 2
    wait_time = between(1, 3)

    def on_start(self) -> None:
        _login(self, "admin@example.com", "admin")

    @task
    def create_and_submit_po(self) -> None:
        suffix = uuid.uuid4().hex[:12]
        supplier = self.client.post(
            "/suppliers",
            json={"name": f"Supplier {suffix}", "email": f"{suffix}@example.com"},
            name="/suppliers",
        )
        if not supplier.ok:
            return
        product = self.client.post(
            "/products",
            json={
                "sku": f"SKU-{suffix}",
                "name": f"Item {suffix}",
                "unit": "ea",
                "cost_cents": 100,
            },
            name="/products [create]",
        )
        if not product.ok:
            return
        po = self.client.post(
            "/purchase-orders",
            json={
                "supplier_id": supplier.json()["id"],
                "lines": [
                    {
                        "product_id": product.json()["id"],
                        "qty_ordered": 10,
                        "unit_cost_cents": 100,
                    }
                ],
            },
            name="/purchase-orders [create]",
        )
        if not po.ok:
            return
        self.client.post(
            f"/purchase-orders/{po.json()['id']}/submit",
            name="/purchase-orders/:id/submit",
        )


class WarehouseUser(HttpUser):
    weight = 1
    wait_time = between(1, 3)

    def on_start(self) -> None:
        _login(self, "admin@example.com", "admin")
        listed = self.client.get("/products?limit=100", name="/products")
        if listed.ok:
            self.product_ids = [row["id"] for row in listed.json()]
        else:
            self.product_ids = []

    @task
    def adjust_stock(self) -> None:
        if not self.product_ids:
            return
        # Positive delta: a random negative can 400 once qty hits zero.
        self.client.post(
            "/stock/adjustments",
            json={
                "product_id": random.choice(self.product_ids),
                "qty_delta": 1,
                "reason": "cycle_count",
            },
            name="/stock/adjustments",
        )


class StepLoad(LoadTestShape):
    """Hold each level. Durations are elapsed seconds from the start."""

    stages = [
        (60, 10),
        (180, 25),
        (300, 50),
        (420, 100),
    ]

    def tick(self) -> tuple[int, float] | None:
        run_time = self.get_run_time()
        for duration, users in self.stages:
            if run_time < duration:
                return (users, 5.0)
        return None
