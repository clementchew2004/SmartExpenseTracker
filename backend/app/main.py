from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routers import expenses, parse, stats

app = FastAPI(title="Smart Expense Tracker")
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().CORS_ORIGINS,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Content-Type"],
)
app.include_router(expenses.router)
app.include_router(stats.router)
app.include_router(parse.router)


@app.get("/health")
def health():
    return {"status": "ok"}
