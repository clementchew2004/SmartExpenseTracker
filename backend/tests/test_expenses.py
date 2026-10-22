import pytest

# --- POST /expenses ---


def test_create_expense_saves_it(client):
    body = {
        "amount": "4.50",
        "currency": "GBP",
        "date": "2026-10-15",
        "merchant": "Chatime",
        "category": "Food",
    }

    response = client.post("/expenses", json=body)

    assert response.status_code == 201
    created = response.json()
    assert created["id"] == 1
    assert created["amount"] == "4.50"
    assert created["merchant"] == "Chatime"
    # It's really in the database, not just echoed back.
    assert client.get("/expenses/1").json() == created


@pytest.mark.parametrize(
    "bad_field",
    [
        {"amount": "-3.00"},
        {"amount": "0"},
        {"currency": "USD"},
        {"category": "Pizza"},
        {"surprise": "extra field"},
    ],
)
def test_create_expense_rejects_invalid_input(client, bad_field):
    body = {
        "amount": "4.50",
        "currency": "GBP",
        "date": "2026-10-15",
        "merchant": "Chatime",
        "category": "Food",
    } | bad_field

    response = client.post("/expenses", json=body)

    assert response.status_code == 422
    assert client.get("/expenses").json() == []


# --- GET /expenses ---


def test_list_expenses_newest_first(client, make_expense):
    make_expense(merchant="Old", date="2026-09-01")
    make_expense(merchant="New", date="2026-10-20")

    response = client.get("/expenses")

    assert response.status_code == 200
    assert [e["merchant"] for e in response.json()] == ["New", "Old"]


def test_list_expenses_filter_by_category(client, make_expense):
    make_expense(merchant="Chatime", category="Food")
    make_expense(merchant="TfL", category="Transport")

    response = client.get("/expenses", params={"category": "Food"})

    assert [e["merchant"] for e in response.json()] == ["Chatime"]


def test_list_expenses_filter_by_date_range(client, make_expense):
    make_expense(merchant="September", date="2026-09-30")
    make_expense(merchant="October 1st", date="2026-10-01")
    make_expense(merchant="October 31st", date="2026-10-31")
    make_expense(merchant="November", date="2026-11-01")

    response = client.get(
        "/expenses", params={"from": "2026-10-01", "to": "2026-10-31"}
    )

    assert [e["merchant"] for e in response.json()] == ["October 31st", "October 1st"]


def test_list_expenses_limit_and_offset(client, make_expense):
    make_expense(merchant="Third", date="2026-10-01")
    make_expense(merchant="Second", date="2026-10-02")
    make_expense(merchant="First", date="2026-10-03")

    response = client.get("/expenses", params={"limit": 1, "offset": 1})

    assert [e["merchant"] for e in response.json()] == ["Second"]


def test_list_expenses_rejects_from_after_to(client):
    response = client.get(
        "/expenses", params={"from": "2026-10-31", "to": "2026-10-01"}
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "'from' must be on or before 'to'"


# --- GET /expenses/{id} ---


def test_get_expense(client, make_expense):
    created = make_expense(merchant="Chatime")

    response = client.get(f"/expenses/{created['id']}")

    assert response.status_code == 200
    assert response.json() == created


def test_get_missing_expense_returns_404(client):
    response = client.get("/expenses/999")

    assert response.status_code == 404


# --- PATCH /expenses/{id} ---


def test_patch_changes_only_sent_fields(client, make_expense):
    created = make_expense(amount="4.50", merchant="Chatime", note=None)

    response = client.patch(
        f"/expenses/{created['id']}", json={"amount": "5.00", "note": "large"}
    )

    assert response.status_code == 200
    updated = response.json()
    assert updated["amount"] == "5.00"
    assert updated["note"] == "large"
    assert updated["merchant"] == "Chatime"
    assert updated["date"] == created["date"]


def test_patch_null_amount_returns_422_and_keeps_expense(client, make_expense):
    created = make_expense(amount="4.50")

    response = client.patch(f"/expenses/{created['id']}", json={"amount": None})

    assert response.status_code == 422
    assert client.get(f"/expenses/{created['id']}").json()["amount"] == "4.50"


def test_patch_missing_expense_returns_404(client):
    response = client.patch("/expenses/999", json={"note": "hello"})

    assert response.status_code == 404


# --- DELETE /expenses/{id} ---


def test_delete_expense_removes_it(client, make_expense):
    created = make_expense()

    response = client.delete(f"/expenses/{created['id']}")

    assert response.status_code == 204
    assert client.get(f"/expenses/{created['id']}").status_code == 404


def test_delete_missing_expense_returns_404(client):
    response = client.delete("/expenses/999")

    assert response.status_code == 404
