import datetime
import json

import pytest

from app.llm.client import LLMError, get_llm_client
from app.main import app
from app.routers import insights
from app.services.weekly import monday_of, percent, weeks_in_month
from app.today import get_today

# These tests never call the real OpenAI API: get_llm_client is overridden.


def d(text: str) -> datetime.date:
    return datetime.date.fromisoformat(text)


# --- Week arithmetic ---------------------------------------------------------------


def test_monday_of():
    assert monday_of(d("2026-11-11")) == d("2026-11-09")  # Wednesday
    assert monday_of(d("2026-11-09")) == d("2026-11-09")  # already Monday
    assert monday_of(d("2026-11-15")) == d("2026-11-09")  # Sunday


def test_weeks_in_month_include_weeks_crossing_into_it_and_stop_at_this_week():
    # November 2026 starts on a Sunday, so 26 Oct - 1 Nov touches it.
    weeks = weeks_in_month(d("2026-11-01"), today=d("2026-11-11"))

    assert weeks == [d("2026-11-09"), d("2026-11-02"), d("2026-10-26")]


def test_a_finished_month_lists_every_week_touching_it():
    weeks = weeks_in_month(d("2026-10-01"), today=d("2026-11-11"))

    assert weeks[0] == d("2026-10-26")  # ends in November, still in October's list
    assert weeks[-1] == d("2026-09-28")  # starts in September
    assert len(weeks) == 5


def test_a_future_month_has_no_weeks():
    assert weeks_in_month(d("2026-12-01"), today=d("2026-11-11")) == []


@pytest.mark.parametrize(
    ("part", "whole", "expected"),
    [("29", "200", 15), ("28.9", "200", 14), ("-10", "40", -25), ("120", "100", 120)],
)
def test_percent_rounds_halves_up(part, whole, expected):
    from decimal import Decimal

    assert percent(Decimal(part), Decimal(whole)) == expected


# --- GET /insights/weekly (today is fixed at Wed 11 Nov 2026) --------------------

TODAY = d("2026-11-11")


class FakeLLM:
    """Pretends to be LLMClient.stream: records what it was sent, then yields
    the scripted pieces. A scripted LLMError is raised at that point."""

    def __init__(self):
        self.calls = []
        self.script = None  # None -> "Summary number N." in two pieces

    def stream(self, system_prompt, user_message):
        self.calls.append(json.loads(user_message))
        pieces = self.script or ["Summary number ", f"{len(self.calls)}."]
        for piece in pieces:
            if isinstance(piece, Exception):
                raise piece
            yield piece


@pytest.fixture
def llm():
    fake = FakeLLM()
    app.dependency_overrides[get_llm_client] = lambda: fake
    app.dependency_overrides[get_today] = lambda: TODAY
    yield fake
    app.dependency_overrides.pop(get_llm_client, None)
    app.dependency_overrides.pop(get_today, None)


def weeks(client, month="2026-11"):
    response = client.get("/insights/weekly", params={"month": month})
    assert response.status_code == 200, response.text
    return {w["week_start"]: w for w in response.json()["weeks"]}


def gbp(week):
    [currency] = [c for c in week["currencies"] if c["currency"] == "GBP"]
    return currency


def test_finished_week_is_compared_with_the_whole_week_before(
    client, make_expense, llm
):
    make_expense(amount="30.00", date="2026-10-28")  # week of 26 Oct
    make_expense(amount="10.00", date="2026-11-01")  # Sunday, same week
    make_expense(amount="50.00", date="2026-11-04", merchant="Tesco")  # week of 2 Nov
    make_expense(amount="10.00", date="2026-11-08", merchant="Pret")

    week = weeks(client)["2026-11-02"]

    assert week["in_progress"] is False
    assert week["days_counted"] == 7
    assert gbp(week)["spent"] == "60.00"
    assert gbp(week)["previous"] == "40.00"
    assert gbp(week)["change"] == "20.00"
    assert gbp(week)["change_pct"] == 50
    assert [m["merchant"] for m in gbp(week)["top_merchants"]] == ["Tesco", "Pret"]
    assert week["summary"] is None  # nothing written until you tap


def test_this_week_is_compared_with_the_same_days_of_last_week(
    client, make_expense, llm
):
    make_expense(amount="20.00", date="2026-11-03")  # last Tue: counts
    make_expense(amount="99.00", date="2026-11-06")  # last Fri: after "Wednesday"
    make_expense(amount="5.00", date="2026-11-10")  # this Tue

    week = weeks(client)["2026-11-09"]

    assert week["in_progress"] is True
    assert week["days_counted"] == 3  # Mon, Tue, Wed
    assert gbp(week)["spent"] == "5.00"
    assert gbp(week)["previous"] == "20.00"  # not 119.00


def test_expenses_later_this_week_are_not_counted_yet(client, make_expense, llm):
    make_expense(amount="5.00", date="2026-11-10")
    make_expense(amount="900.00", date="2026-11-14")  # dated Saturday

    assert gbp(weeks(client)["2026-11-09"])["spent"] == "5.00"


def test_first_week_has_no_comparison(client, make_expense, llm):
    make_expense(amount="12.00", date="2026-11-04")

    week = weeks(client)["2026-11-02"]

    assert gbp(week)["previous"] is None
    assert gbp(week)["change"] is None
    assert gbp(week)["change_pct"] is None


def test_currencies_are_never_mixed(client, make_expense, llm):
    make_expense(amount="10.00", date="2026-11-04")
    make_expense(amount="40.00", currency="MYR", date="2026-11-05", merchant="Grab")

    by_currency = {c["currency"]: c for c in weeks(client)["2026-11-02"]["currencies"]}

    assert by_currency["GBP"]["spent"] == "10.00"
    assert by_currency["MYR"]["spent"] == "40.00"
    assert [m["merchant"] for m in by_currency["GBP"]["top_merchants"]] == ["Chatime"]


def test_budget_share_uses_the_lists_own_month(client, make_expense, llm):
    client.put("/budgets/default/GBP", json={"amount": "200"})
    client.put("/budgets/2026-11/GBP", json={"amount": "100"})
    make_expense(amount="20.00", date="2026-10-28")  # week of 26 Oct - 1 Nov

    october = weeks(client, "2026-10")["2026-10-26"]
    november = weeks(client, "2026-11")["2026-10-26"]

    assert gbp(october)["budget_share_pct"] == 10  # of October's £200 (the default)
    assert gbp(november)["budget_share_pct"] == 20  # of November's own £100


def test_no_budget_means_no_share(client, make_expense, llm):
    make_expense(amount="20.00", date="2026-11-04")

    assert gbp(weeks(client)["2026-11-02"])["budget_share_pct"] is None


def sentence(client, week_start="2026-11-02", month="2026-11"):
    """The streamed events, parsed: [("text", "..."), ..., ("done", "")]."""
    response = client.get(
        f"/insights/weekly/{week_start}/summary", params={"month": month}
    )
    if response.status_code != 200:
        return response.status_code
    assert response.headers["content-type"].startswith("text/event-stream")
    events = []
    for block in response.text.split("\n\n"):
        if block.startswith("data: "):
            payload = json.loads(block.removeprefix("data: "))
            events.append((payload["type"], payload["text"]))
    return events


def text_of(events):
    return "".join(text for kind, text in events if kind == "text")


def test_opening_the_list_never_calls_the_llm(client, make_expense, llm):
    make_expense(amount="12.00", date="2026-11-04")
    make_expense(amount="3.00", date="2026-11-10")

    weeks(client)

    assert llm.calls == []


def test_tapping_streams_the_pieces_then_done(client, make_expense, llm):
    make_expense(amount="12.00", date="2026-11-04")

    events = sentence(client)

    assert events == [("text", "Summary number "), ("text", "1."), ("done", "")]
    # Saved only after it finished and passed the check; the list now has it.
    assert weeks(client)["2026-11-02"]["summary"] == "Summary number 1."


def test_a_saved_sentence_comes_back_at_once_with_no_llm_call(
    client, make_expense, llm
):
    make_expense(amount="12.00", date="2026-11-04")
    sentence(client)

    events = sentence(client)

    assert events == [("text", "Summary number 1."), ("done", "")]
    assert len(llm.calls) == 1


def test_changed_numbers_make_the_sentence_out_of_date(client, make_expense, llm):
    make_expense(amount="12.00", date="2026-11-04")
    sentence(client)

    make_expense(amount="3.00", date="2026-11-05")  # e.g. a forgotten expense

    assert weeks(client)["2026-11-02"]["summary"] is None  # old one hidden
    assert text_of(sentence(client)) == "Summary number 2."
    assert llm.calls[-1]["currencies"][0]["spent"] == "15.00"


def test_a_new_prompt_version_rewrites_old_sentences(
    client, make_expense, llm, monkeypatch
):
    make_expense(amount="12.00", date="2026-11-04")
    sentence(client)

    monkeypatch.setattr(insights, "WEEKLY_SUMMARY_PROMPT_VERSION", 99)

    assert weeks(client)["2026-11-02"]["summary"] is None
    assert text_of(sentence(client)) == "Summary number 2."


def test_a_week_with_no_spending_skips_the_llm(client, llm):
    assert sentence(client) == [("text", "No spending this week."), ("done", "")]
    assert llm.calls == []


def test_the_llm_is_only_sent_the_finished_numbers(client, make_expense, llm):
    make_expense(amount="12.00", date="2026-11-04", note="secret note")

    sentence(client)

    sent = llm.calls[0]
    assert set(sent) == {
        "week_start",
        "week_end",
        "in_progress",
        "days_counted",
        "compared_with",
        "currencies",
    }
    assert "secret note" not in json.dumps(sent)


def test_a_reply_running_too_long_is_cut_off_and_not_saved(client, make_expense, llm):
    make_expense(amount="12.00", date="2026-11-04")
    llm.script = ["word " * 20, "word " * 20, "this piece is never shown"]

    events = sentence(client)

    assert events[-1][0] == "error"
    assert len(text_of(events)) <= 160  # nothing past the cap reached the screen
    assert "never shown" not in text_of(events)
    assert weeks(client)["2026-11-02"]["summary"] is None


def test_an_empty_reply_is_an_error_and_not_saved(client, make_expense, llm):
    make_expense(amount="12.00", date="2026-11-04")
    llm.script = ["   "]

    assert sentence(client)[-1][0] == "error"
    assert weeks(client)["2026-11-02"]["summary"] is None


def test_a_stream_breaking_halfway_saves_nothing(client, make_expense, llm):
    make_expense(amount="12.00", date="2026-11-04")
    llm.script = ["This week was ", LLMError("connection dropped")]

    events = sentence(client)

    assert events[0] == ("text", "This week was ")
    assert events[-1][0] == "error"
    assert weeks(client)["2026-11-02"]["summary"] is None

    llm.script = None  # the next tap tries again, because nothing was saved
    assert sentence(client)[-1] == ("done", "")


@pytest.mark.parametrize(
    "week_start",
    ["2026-11-03", "2026-11-16", "2026-10-19"],
    ids=["not-a-monday", "future-week", "not-in-the-month"],
)
def test_a_week_outside_the_months_list_is_404_before_streaming(
    client, llm, week_start
):
    assert sentence(client, week_start) == 404
    assert llm.calls == []


def test_another_users_spending_is_never_included(
    client, make_user, client_for, make_expense, llm
):
    make_expense(amount="12.00", date="2026-11-04")
    sentence(client)  # mine, saved
    other = client_for(make_user("other@example.com"))

    week = weeks(other)["2026-11-02"]

    assert week["currencies"] == []
    assert week["summary"] is None  # my saved sentence isn't theirs
    assert text_of(sentence(other)) == "No spending this week."


@pytest.mark.parametrize("month", ["2026-13", "November", ""])
def test_bad_month_returns_422(client, llm, month):
    response = client.get("/insights/weekly", params={"month": month})

    assert response.status_code == 422
    assert sentence(client, month=month) == 422


def test_needs_login(anon_client):
    assert anon_client.get("/insights/weekly?month=2026-11").status_code == 401


def test_comparison_is_named_in_code_for_the_summary_to_copy(client, make_expense, llm):
    make_expense(amount="20.00", date="2026-10-28")  # history before 2 Nov
    make_expense(amount="5.00", date="2026-11-10")

    by_week = weeks(client)

    assert by_week["2026-11-09"]["compared_with"] == "the same 3 days last week"
    assert by_week["2026-11-02"]["compared_with"] == "last week"
    assert by_week["2026-10-26"]["compared_with"] is None  # first week
