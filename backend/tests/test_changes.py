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


def changes(client, month="2026-11"):
    response = client.get("/stats/changes", params={"month": month})
    assert response.status_code == 200, response.text
    return response.json()


def by_category(body, currency="GBP"):
    [chosen] = [c for c in body["currencies"] if c["currency"] == currency]
    return {c["category"]: c for c in chosen["changes"]}


def test_compared_with_the_same_days_of_previous_months(client, make_expense):
    make_expense(amount="30.00", date="2026-10-05", category="Food")
    make_expense(amount="500.00", date="2026-10-25", category="Food")  # after the 20th
    make_expense(amount="50.00", date="2026-11-10", category="Food")

    body = changes(client)
    food = by_category(body)["Food"]

    assert body["up_to_day"] == 20
    assert body["compared_months"] == ["2026-10"]  # you started in October
    assert food["now"] == "50.00"
    assert food["usual"] == "30.00"  # 25 Oct is past day 20, so it's left out
    assert food["change"] == "20.00"


def test_usual_is_the_average_of_up_to_three_months(client, make_expense):
    make_expense(amount="99.00", date="2026-07-02", category="Food")  # 4 months back
    make_expense(amount="10.00", date="2026-08-02", category="Food")
    make_expense(amount="20.00", date="2026-09-02", category="Food")
    make_expense(amount="0.01", date="2026-10-02", category="Bills")  # Oct: no food

    body = changes(client)
    food = by_category(body)["Food"]

    assert body["compared_months"] == ["2026-08", "2026-09", "2026-10"]
    assert food["usual"] == "10.00"  # (10 + 20 + 0) / 3
    assert food["now"] == "0.00"
    assert food["change"] == "-10.00"


def test_usual_rounds_to_the_penny(client, make_expense):
    make_expense(amount="10.00", date="2026-08-02", category="Food")
    make_expense(amount="0.01", date="2026-09-02", category="Bills")
    make_expense(amount="0.01", date="2026-10-02", category="Bills")

    assert by_category(changes(client))["Food"]["usual"] == "3.33"


def test_biggest_change_first_either_way(client, make_expense):
    make_expense(amount="100.00", date="2026-10-02", category="Food")
    make_expense(amount="5.00", date="2026-10-02", category="Transport")
    make_expense(amount="60.00", date="2026-11-02", category="Food")  # -40
    make_expense(amount="15.00", date="2026-11-02", category="Transport")  # +10

    [chosen] = [c for c in changes(client)["currencies"] if c["currency"] == "GBP"]

    assert [c["category"] for c in chosen["changes"]] == ["Food", "Transport"]


def test_no_history_yet_means_nothing_to_compare(client, make_expense):
    make_expense(amount="12.00", date="2026-11-04")

    body = changes(client)

    assert body["compared_months"] == []
    assert by_category(body) == {}


def test_a_past_month_compares_whole_months(client, make_expense):
    make_expense(amount="10.00", date="2026-09-28", category="Food")
    make_expense(amount="25.00", date="2026-10-30", category="Food")

    body = changes(client, month="2026-10")

    assert body["up_to_day"] is None
    assert by_category(body)["Food"]["change"] == "15.00"


def test_currencies_are_never_mixed(client, make_expense):
    make_expense(amount="10.00", date="2026-10-02", category="Food")
    make_expense(amount="40.00", currency="MYR", date="2026-11-02", category="Food")

    body = changes(client)

    assert by_category(body)["Food"]["now"] == "0.00"
    assert by_category(body, "MYR")["Food"]["now"] == "40.00"
    assert by_category(body, "MYR")["Food"]["usual"] == "0.00"


def test_only_my_expenses(client, make_user, client_for, make_expense):
    make_expense(amount="10.00", date="2026-10-02")
    make_expense(amount="10.00", date="2026-11-02")
    other = client_for(make_user("other@example.com"))

    assert changes(other)["compared_months"] == []


def test_needs_login(anon_client):
    response = anon_client.get("/stats/changes", params={"month": "2026-11"})
    assert response.status_code == 401
