import datetime

import pytest

from app.main import app
from app.today import get_today

TODAY = datetime.date(2026, 11, 20)


@pytest.fixture(autouse=True)
def fixed_today():
    app.dependency_overrides[get_today] = lambda: TODAY
    yield
    app.dependency_overrides.pop(get_today, None)


def pace(client, month="2026-11", currency="GBP"):
    response = client.get("/stats/pace", params={"month": month})
    assert response.status_code == 200, response.text
    [chosen] = [c for c in response.json()["currencies"] if c["currency"] == currency]
    return chosen


def day(chosen, n):
    return chosen["days"][n - 1]


def test_running_total_day_by_day(client, make_expense):
    make_expense(amount="10.00", date="2026-11-01")
    make_expense(amount="2.50", date="2026-11-01")
    make_expense(amount="7.50", date="2026-11-03")

    chosen = pace(client)

    assert len(chosen["days"]) == 30  # every day of November
    assert day(chosen, 1)["spent"] == "12.50"
    assert day(chosen, 2)["spent"] == "12.50"  # a quiet day keeps the total
    assert day(chosen, 3)["spent"] == "20.00"
    assert day(chosen, 20)["spent"] == "20.00"


def test_days_still_to_come_have_no_point(client, make_expense):
    make_expense(amount="99.00", date="2026-11-25")  # dated ahead of today

    chosen = pace(client)

    assert day(chosen, 20)["spent"] == "0.00"  # not counted yet
    assert day(chosen, 21)["spent"] is None
    assert day(chosen, 30)["spent"] is None


def test_even_pace_lands_on_the_budget(client):
    client.put("/budgets/default/GBP", json={"amount": "900"})

    chosen = pace(client)

    assert chosen["budget"] == "900.00"
    assert day(chosen, 1)["on_pace"] == "30.00"  # 900 / 30 days
    assert day(chosen, 15)["on_pace"] == "450.00"
    assert day(chosen, 30)["on_pace"] == "900.00"


def test_even_pace_rounds_to_the_penny(client):
    client.put("/budgets/default/GBP", json={"amount": "100"})

    chosen = pace(client, month="2026-10")  # 31 days

    assert day(chosen, 1)["on_pace"] == "3.23"  # 3.2258...
    assert day(chosen, 31)["on_pace"] == "100.00"


def test_no_budget_means_no_pace_line(client, make_expense):
    make_expense(amount="5.00", date="2026-11-02")

    chosen = pace(client)

    assert chosen["budget"] is None
    assert all(d["on_pace"] is None for d in chosen["days"])


def test_a_past_month_is_complete(client, make_expense):
    make_expense(amount="40.00", date="2026-10-31")

    chosen = pace(client, month="2026-10")

    assert day(chosen, 31)["spent"] == "40.00"


def test_currencies_are_never_mixed(client, make_expense):
    make_expense(amount="10.00", date="2026-11-02")
    make_expense(amount="40.00", currency="MYR", date="2026-11-02", merchant="Grab")

    assert day(pace(client), 2)["spent"] == "10.00"
    assert day(pace(client, currency="MYR"), 2)["spent"] == "40.00"


def test_only_my_expenses(client, make_user, client_for, make_expense):
    make_expense(amount="10.00", date="2026-11-02")
    other = client_for(make_user("other@example.com"))

    assert day(pace(other), 2)["spent"] == "0.00"


def test_bad_month_is_rejected(client):
    assert client.get("/stats/pace", params={"month": "Nov"}).status_code == 422


def test_needs_login(anon_client):
    assert (
        anon_client.get("/stats/pace", params={"month": "2026-11"}).status_code == 401
    )
