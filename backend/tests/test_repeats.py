import datetime
from types import SimpleNamespace

import pytest

from app.main import app
from app.routers.repeats import get_today
from app.services.repeats import MAX_DUE, due_dates, following


def d(text: str) -> datetime.date:
    return datetime.date.fromisoformat(text)


# --- Date arithmetic --------------------------------------------------------------


def test_monthly_uses_the_last_day_then_goes_back_to_the_31st():
    jan_31 = d("2026-01-31")
    feb = following(jan_31, "monthly", 31)
    mar = following(feb, "monthly", 31)
    apr = following(mar, "monthly", 31)

    assert (feb, mar, apr) == (d("2026-02-28"), d("2026-03-31"), d("2026-04-30"))


def test_leap_years_get_the_29th():
    assert following(d("2028-01-31"), "monthly", 31) == d("2028-02-29")


def test_monthly_rolls_over_the_year():
    assert following(d("2026-12-15"), "monthly", 15) == d("2027-01-15")


def test_weekly_and_daily():
    assert following(d("2026-10-29"), "weekly", 29) == d("2026-11-05")
    assert following(d("2026-10-31"), "daily", 31) == d("2026-11-01")


def repeat(next_due, frequency="monthly", day=1, end_date=None):
    return SimpleNamespace(
        next_due=d(next_due),
        frequency=frequency,
        day_of_month=day,
        end_date=d(end_date) if end_date else None,
    )


def test_nothing_due_before_the_date():
    assert due_dates(repeat("2026-11-01"), d("2026-10-31")) == []


def test_due_on_the_day_itself():
    assert due_dates(repeat("2026-11-01"), d("2026-11-01")) == [d("2026-11-01")]


def test_three_missed_months_are_three_dates_oldest_first():
    dates = due_dates(repeat("2026-11-01"), d("2027-01-20"))

    assert dates == [d("2026-11-01"), d("2026-12-01"), d("2027-01-01")]


def test_the_end_date_stops_reminders():
    dates = due_dates(repeat("2026-11-01", end_date="2026-12-15"), d("2027-03-01"))

    assert dates == [d("2026-11-01"), d("2026-12-01")]


def test_a_long_absence_is_capped():
    dates = due_dates(repeat("2026-01-01", frequency="daily"), d("2026-12-31"))

    assert len(dates) == MAX_DUE
    assert dates[0] == d("2026-01-01")


# --- Routes (today is fixed at 5 Nov 2026) -----------------------------------------

TODAY = d("2026-11-05")
RENT = {
    "amount": "950.00",
    "currency": "GBP",
    "date": "2026-10-01",  # the first rent, already saved
    "merchant": "Rent",
    "category": "Bills",
    "frequency": "monthly",
}


@pytest.fixture(autouse=True)
def fixed_today():
    app.dependency_overrides[get_today] = lambda: TODAY
    yield
    app.dependency_overrides.pop(get_today, None)


def make_repeat(client, **changes):
    response = client.post("/repeats", json=RENT | changes)
    assert response.status_code == 201, response.text
    return response.json()


def save(client, reminder, **changes):
    body = {
        "amount": reminder["amount"],
        "currency": reminder["currency"],
        "date": reminder["due_date"],
        "merchant": reminder["merchant"],
        "category": reminder["category"],
        "note": reminder["note"],
        "due_date": reminder["due_date"],
    } | changes
    return client.post(f"/repeats/{reminder['repeat_id']}/save", json=body)


def test_creating_a_repeat_starts_from_the_next_date(client):
    rent = make_repeat(client)

    assert rent["next_due"] == "2026-11-01"
    assert rent["day_of_month"] == 1
    assert rent["finished"] is False
    assert client.get("/repeats").json() == [rent]


def test_due_reminders_are_cards_for_dates_up_to_today(client):
    rent = make_repeat(client)

    assert client.get("/repeats/due").json() == [
        {
            "repeat_id": rent["id"],
            "due_date": "2026-11-01",
            "amount": "950.00",
            "currency": "GBP",
            "merchant": "Rent",
            "category": "Bills",
            "note": None,
        }
    ]


def test_missed_months_give_one_card_each_oldest_first(client):
    make_repeat(client, date="2026-07-01")

    due = [r["due_date"] for r in client.get("/repeats/due").json()]

    assert due == ["2026-08-01", "2026-09-01", "2026-10-01", "2026-11-01"]


def test_saving_creates_one_expense_and_moves_on(client):
    make_repeat(client)
    [card] = client.get("/repeats/due").json()

    response = save(client, card)

    assert response.status_code == 201
    assert response.json()["date"] == "2026-11-01"
    assert [e["merchant"] for e in client.get("/expenses").json()] == ["Rent"]
    assert client.get("/repeats/due").json() == []  # December isn't due yet
    assert client.get("/repeats").json()[0]["next_due"] == "2026-12-01"


def test_the_card_can_be_edited_before_saving(client):
    make_repeat(client, merchant="Electricity", amount="60.00")
    [card] = client.get("/repeats/due").json()

    save(client, card, amount="72.40", date="2026-11-03")

    [expense] = client.get("/expenses").json()
    assert (expense["amount"], expense["date"]) == ("72.40", "2026-11-03")
    # The repeat itself keeps its usual amount for next month.
    assert client.get("/repeats").json()[0]["amount"] == "60.00"


def test_a_card_can_only_be_saved_once(client):
    make_repeat(client)
    [card] = client.get("/repeats/due").json()
    assert save(client, card).status_code == 201

    second = save(client, card)  # e.g. a double tap

    assert second.status_code == 409
    assert len(client.get("/expenses").json()) == 1


def test_cards_must_be_handled_oldest_first(client):
    make_repeat(client, date="2026-09-01")
    older, newer = client.get("/repeats/due").json()

    assert save(client, newer).status_code == 409
    assert save(client, older).status_code == 201


def test_a_date_not_yet_due_cant_be_saved(client):
    rent = make_repeat(client, date="2026-11-01")  # next due 1 Dec

    response = client.post(
        f"/repeats/{rent['id']}/skip", json={"due_date": "2026-12-01"}
    )

    assert response.status_code == 409


def test_skipping_moves_on_without_saving(client):
    make_repeat(client)
    [card] = client.get("/repeats/due").json()

    response = client.post(
        f"/repeats/{card['repeat_id']}/skip", json={"due_date": card["due_date"]}
    )

    assert response.status_code == 204
    assert client.get("/expenses").json() == []
    assert client.get("/repeats/due").json() == []


def test_editing_changes_future_reminders_not_saved_expenses(client):
    make_repeat(client, date="2026-09-01")
    first, _ = client.get("/repeats/due").json()
    save(client, first)  # October's rent, saved at £950

    rent_id = first["repeat_id"]
    response = client.patch(f"/repeats/{rent_id}", json={"amount": "1000.00"})

    assert response.json()["amount"] == "1000.00"
    [next_card] = client.get("/repeats/due").json()
    assert next_card["amount"] == "1000.00"
    assert client.get("/expenses").json()[0]["amount"] == "950.00"


def test_an_edit_cant_blank_a_required_field(client):
    rent = make_repeat(client)

    response = client.patch(f"/repeats/{rent['id']}", json={"amount": None})

    assert response.status_code == 422


def test_stopping_keeps_saved_expenses(client):
    make_repeat(client)
    [card] = client.get("/repeats/due").json()
    save(client, card)

    response = client.delete(f"/repeats/{card['repeat_id']}")

    assert response.status_code == 204
    assert client.get("/repeats").json() == []
    assert client.get("/repeats/due").json() == []
    assert len(client.get("/expenses").json()) == 1


def test_a_finished_repeat_says_so(client):
    make_repeat(client, end_date="2026-11-01")
    [card] = client.get("/repeats/due").json()
    save(client, card)

    [rent] = client.get("/repeats").json()

    assert rent["finished"] is True
    assert client.get("/repeats/due").json() == []


@pytest.mark.parametrize(
    "changes",
    [
        {"frequency": "yearly"},
        {"end_date": "2026-09-30"},  # before the first date
        {"amount": "0"},
        {"currency": "USD"},
    ],
)
def test_bad_repeats_are_rejected(client, changes):
    assert client.post("/repeats", json=RENT | changes).status_code == 422


def test_repeats_need_login(anon_client):
    assert anon_client.get("/repeats").status_code == 401
    assert anon_client.get("/repeats/due").status_code == 401


def test_a_cannot_see_or_act_on_bs_repeats(make_user, client_for):
    a = client_for(make_user("a@example.com"))
    b = client_for(make_user("b@example.com"))
    rent = make_repeat(b)
    [card] = b.get("/repeats/due").json()

    assert a.get("/repeats").json() == []
    assert a.get("/repeats/due").json() == []
    assert save(a, card).status_code == 404
    assert (
        a.post(
            f"/repeats/{rent['id']}/skip", json={"due_date": "2026-11-01"}
        ).status_code
        == 404
    )
    assert a.patch(f"/repeats/{rent['id']}", json={"amount": "1.00"}).status_code == 404
    assert a.delete(f"/repeats/{rent['id']}").status_code == 404
    assert b.get("/repeats/due").json() == [card]  # B's reminder untouched
