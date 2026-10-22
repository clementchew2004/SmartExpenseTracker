from fastapi import FastAPI

from app.routers import expenses, parse, stats

app = FastAPI(title="Smart Expense Tracker")
app.include_router(expenses.router)
app.include_router(stats.router)
app.include_router(parse.router)


@app.get("/health")
def health():
    return {"status": "ok"}
