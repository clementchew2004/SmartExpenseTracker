import datetime

import pytest

from app.main import app
from app.services.trend import months_ending
from app.today import get_today

TODAY = datetime.date(2026, 11, 20)


@pytest.fixture(autouse=True)
def fixed_today():
    app.dependency_overrides[get_today] = lambda: TODAY
    yield
    app.dependency_overrides.pop(get_today, None)


def trend(client, month="2026-11", currency="GBP"):
    response = client.get("/stats/trend", params={"month": month})
    assert response.status_code == 200, response.text
    [chosen] = [c for c in response.json()["currencies"] if c["currency"] == currency]
    return chosen["months"]


def test_six_months_ending_at_the_month_across_new_year():
    months = months_ending(datetime.date(2026, 3, 1))

    assert [m.isoformat() for m in months] == [
        "2025-10-01",
        "2025-11-01",
        "2025-12-01",
        "2026-01-01",
        "2026-02-01",
        "2026-03-01",
    ]


def test_totals_per_month_and_category(client, make_expense):
    make_expense(amount="142.30", date="2026-10-08", category="Food")
    make_expense(amount="40.00", date="2026-10-31", category="Groceries")
    make_expense(amount="12.50", date="2026-11-01", category="Food")
    make_expense(amount="99.00", date="2026-05-31")  # just before the 6 months

    months = trend(client)

    assert [m["month"] for m in months] == [
        "2026-06",
        "2026-07",
        "2026-08",
        "2026-09",
        "2026-10",
        "2026-11",
    ]
    october, november = months[4], months[5]
    assert october["total"] == "182.30"
    assert october["by_category"] == {"Food": "142.30", "Groceries": "40.00"}
    assert november["total"] == "12.50"


def test_a_quiet_month_is_zero_not_missing(client, make_expense):
    make_expense(amount="10.00", date="2026-10-08")

    june = trend(client)[0]

    assert june == {
        "month": "2026-06",
        "total": "0.00",
        "by_category": {},
        "budget": None,
    }


def test_future_months_have_no_total(client, make_expense):
    months = trend(client, month="2027-01")

    assert [m["total"] for m in months[-2:]] == [None, None]  # Dec 2026, Jan 2027
    assert months[-3]["total"] == "0.00"  # November: this month


def test_each_month_has_its_own_budget(client, make_expense):
    client.put("/budgets/default/GBP", json={"amount": "750"})
    client.put("/budgets/2026-09/GBP", json={"amount": "600"})

    budgets = [m["budget"] for m in trend(client)]

    assert budgets == ["750.00", "750.00", "750.00", "600.00", "750.00", "750.00"]
    assert all(m["budget"] is None for m in trend(client, currency="MYR"))


def test_currencies_are_never_mixed(client, make_expense):
    make_expense(amount="10.00", date="2026-10-08")
    make_expense(amount="40.00", currency="MYR", date="2026-10-09")

    assert trend(client, currency="GBP")[4]["total"] == "10.00"
    assert trend(client, currency="MYR")[4]["total"] == "40.00"


def test_another_users_spending_is_never_included(
    client, make_user, client_for, make_expense
):
    make_expense(amount="10.00", date="2026-10-08")
    other = client_for(make_user("other@example.com"))

    assert trend(other)[4]["total"] == "0.00"


@pytest.mark.parametrize("month", ["2026-13", "October", ""])
def test_bad_month_is_422(client, month):
    assert client.get("/stats/trend", params={"month": month}).status_code == 422


def test_needs_login(anon_client):
    assert (
        anon_client.get("/stats/trend", params={"month": "2026-11"}).status_code == 401
    )
