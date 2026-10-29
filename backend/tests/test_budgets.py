import datetime
from decimal import Decimal

import pytest

from app.services.budgets import next_month, outlook

OCT = datetime.date(2026, 10, 1)  # 31 days
FEB = datetime.date(2027, 2, 1)  # 28 days


def day(n: int, month: datetime.date = OCT) -> datetime.date:
    return month.replace(day=n)


# --- The outlook: pure arithmetic, tested with fixed dates ---------------------


def test_next_month_rolls_over_the_year():
    assert next_month(datetime.date(2026, 12, 1)) == datetime.date(2027, 1, 1)
    assert next_month(OCT) == datetime.date(2026, 11, 1)


def test_nothing_is_predicted_before_day_14():
    # £700 by the 13th is £1,669 at this pace - but it's too early to say.
    assert outlook(Decimal(700), Decimal(800), OCT, day(13)) == "too_early"


def test_from_day_14_the_pace_decides():
    # £300 by the 14th: £300 / 14 * 31 = £664 -> stays under £800.
    assert outlook(Decimal(300), Decimal(800), OCT, day(14)) == "on_track"
    # £400 by the 14th: £400 / 14 * 31 = £886 -> over £800.
    assert outlook(Decimal(400), Decimal(800), OCT, day(14)) == "likely_over"


def test_the_length_of_the_month_counts():
    # £400 by the 14th of February: £400 / 14 * 28 = exactly £800 -> not over.
    assert outlook(Decimal(400), Decimal(800), FEB, day(14, FEB)) == "on_track"


def test_already_over_is_said_on_any_day():
    assert outlook(Decimal("800.01"), Decimal(800), OCT, day(3)) == "over"


def test_finished_months_get_a_verdict():
    nov_1 = datetime.date(2026, 11, 1)
    assert outlook(Decimal("800.00"), Decimal(800), OCT, nov_1) == "under"
    assert outlook(Decimal("800.01"), Decimal(800), OCT, nov_1) == "over"


def test_future_months_are_upcoming():
    sep_30 = datetime.date(2026, 9, 30)
    assert outlook(Decimal(0), Decimal(800), OCT, sep_30) == "upcoming"


# --- The routes --------------------------------------------------------------------

# Past months only, so the results never depend on today's real date.
MONTH = "2025-03"


def budgets(client, month=MONTH):
    response = client.get("/budgets", params={"month": month})
    assert response.status_code == 200, response.text
    return response.json()


def test_nothing_set_up_yet(client):
    assert budgets(client) == {"month": MONTH, "budgets": [], "defaults": {}}


def test_the_default_applies_to_every_month(client, make_expense):
    client.put("/budgets/default/GBP", json={"amount": "800"})
    make_expense(amount="620.00", currency="GBP", date="2025-03-10")

    body = budgets(client)

    assert body["defaults"] == {"GBP": "800.00"}
    assert body["budgets"] == [
        {
            "currency": "GBP",
            "amount": "800.00",
            "source": "default",
            "spent": "620.00",
            "outlook": "under",
        }
    ]
    assert budgets(client, "2025-04")["budgets"][0]["amount"] == "800.00"


def test_a_months_own_amount_replaces_the_default(client):
    client.put("/budgets/default/GBP", json={"amount": "800"})

    response = client.put(f"/budgets/{MONTH}/GBP", json={"amount": "1000.50"})

    assert response.json() == {"amount": "1000.50"}
    [gbp] = budgets(client)["budgets"]
    assert (gbp["amount"], gbp["source"]) == ("1000.50", "month")
    # Only that month: the next one still uses the default.
    assert budgets(client, "2025-04")["budgets"][0]["source"] == "default"


def test_deleting_a_months_amount_goes_back_to_the_default(client):
    client.put("/budgets/default/GBP", json={"amount": "800"})
    client.put(f"/budgets/{MONTH}/GBP", json={"amount": "1000"})

    response = client.delete(f"/budgets/{MONTH}/GBP")

    assert response.status_code == 204
    assert budgets(client)["budgets"][0]["source"] == "default"


def test_setting_again_changes_the_amount_not_adds_a_row(client, db_session):
    client.put("/budgets/default/GBP", json={"amount": "800"})
    client.put("/budgets/default/GBP", json={"amount": "750"})

    assert budgets(client)["defaults"] == {"GBP": "750.00"}


def test_a_month_without_any_budget_in_a_currency_leaves_it_out(client):
    client.put(f"/budgets/{MONTH}/MYR", json={"amount": "500"})

    assert [b["currency"] for b in budgets(client)["budgets"]] == ["MYR"]
    assert budgets(client, "2025-04")["budgets"] == []


def test_currencies_are_never_mixed(client, make_expense):
    client.put("/budgets/default/GBP", json={"amount": "100"})
    client.put("/budgets/default/MYR", json={"amount": "100"})
    make_expense(amount="90.00", currency="GBP", date="2025-03-05")
    make_expense(amount="90.00", currency="MYR", date="2025-03-06")

    gbp, myr = budgets(client)["budgets"]

    # Together they'd be 180 and "over"; separately each is under its own 100.
    assert (gbp["currency"], gbp["spent"], gbp["outlook"]) == ("GBP", "90.00", "under")
    assert (myr["currency"], myr["spent"], myr["outlook"]) == ("MYR", "90.00", "under")


def test_only_that_months_spending_counts(client, make_expense):
    client.put("/budgets/default/GBP", json={"amount": "100"})
    make_expense(amount="500.00", date="2025-02-28")
    make_expense(amount="10.00", date="2025-03-31")
    make_expense(amount="500.00", date="2025-04-01")

    assert budgets(client)["budgets"][0]["spent"] == "10.00"


def test_removing_a_default_stops_that_budget(client):
    client.put("/budgets/default/MYR", json={"amount": "500"})

    assert client.delete("/budgets/default/MYR").status_code == 204
    assert budgets(client) == {"month": MONTH, "budgets": [], "defaults": {}}


@pytest.mark.parametrize("amount", ["0", "-5", "12.345", "abc"])
def test_budget_amounts_must_be_positive_money(client, amount):
    response = client.put("/budgets/default/GBP", json={"amount": amount})

    assert response.status_code == 422


@pytest.mark.parametrize(
    "path", ["/budgets/default/USD", "/budgets/2025-13/GBP", "/budgets/March/GBP"]
)
def test_bad_currency_or_month_is_rejected(client, path):
    assert client.put(path, json={"amount": "10"}).status_code == 422


def test_budgets_need_login(anon_client):
    assert anon_client.get("/budgets", params={"month": MONTH}).status_code == 401
    assert (
        anon_client.put("/budgets/default/GBP", json={"amount": "1"}).status_code == 401
    )


def test_a_cannot_see_or_change_bs_budgets(make_user, client_for):
    a = client_for(make_user("a@example.com"))
    b = client_for(make_user("b@example.com"))
    b.put("/budgets/default/GBP", json={"amount": "800"})
    b.put(f"/budgets/{MONTH}/GBP", json={"amount": "900"})

    assert budgets(a) == {"month": MONTH, "budgets": [], "defaults": {}}
    # A deleting "their" March budget must not touch B's.
    a.delete(f"/budgets/{MONTH}/GBP")
    assert budgets(b)["budgets"][0]["amount"] == "900.00"
