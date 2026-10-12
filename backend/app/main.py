from fastapi import FastAPI

from app.routers import expenses

app = FastAPI(title="Smart Expense Tracker")
app.include_router(expenses.router)


@app.get("/health")
def health():
    return {"status": "ok"}
