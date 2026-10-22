import pytest


def test_monthly_totals_sum_per_category(client, make_expense):
    make_expense(amount="4.50", category="Food", date="2026-10-15")
    make_expense(amount="3.20", category="Food", date="2026-10-20")
    make_expense(amount="2.80", category="Transport", date="2026-10-03")

    response = client.get("/stats/monthly", params={"month": "2026-10"})

    assert response.status_code == 200
    assert response.json() == {
        "month": "2026-10",
        "totals": {"GBP": {"Food": "7.70", "Transport": "2.80"}},
    }


def test_monthly_totals_keep_currencies_separate(client, make_expense):
    make_expense(amount="4.50", currency="GBP", category="Food")
    make_expense(amount="12.00", currency="MYR", category="Food")

    response = client.get("/stats/monthly", params={"month": "2026-10"})

    assert response.json()["totals"] == {
        "GBP": {"Food": "4.50"},
        "MYR": {"Food": "12.00"},
    }


def test_monthly_totals_only_include_that_month(client, make_expense):
    make_expense(amount="1.00", date="2026-09-30")
    make_expense(amount="2.00", date="2026-10-01")
    make_expense(amount="3.00", date="2026-10-31")
    make_expense(amount="4.00", date="2026-11-01")

    response = client.get("/stats/monthly", params={"month": "2026-10"})

    assert response.json()["totals"] == {"GBP": {"Food": "5.00"}}


def test_monthly_totals_december_rolls_over_to_january(client, make_expense):
    make_expense(amount="1.00", date="2026-12-31")
    make_expense(amount="2.00", date="2027-01-01")

    response = client.get("/stats/monthly", params={"month": "2026-12"})

    assert response.json()["totals"] == {"GBP": {"Food": "1.00"}}


def test_monthly_totals_empty_month(client):
    response = client.get("/stats/monthly", params={"month": "2026-08"})

    assert response.status_code == 200
    assert response.json() == {"month": "2026-08", "totals": {}}


@pytest.mark.parametrize("bad_month", ["2026-13", "october", "2026/10"])
def test_monthly_totals_reject_bad_month(client, bad_month):
    response = client.get("/stats/monthly", params={"month": bad_month})

    assert response.status_code == 422
    assert response.json()["detail"] == "month must be in YYYY-MM format, e.g. 2026-10"


def test_monthly_totals_require_month(client):
    response = client.get("/stats/monthly")

    assert response.status_code == 422
