import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routers import auth, budgets, expenses, parse, repeats, stats

# Without a handler, Python only prints WARNING and above, so the LLM client's
# token/duration INFO lines were silently dropped. Libraries stay at WARNING.
logging.basicConfig(format="%(levelname)s:     %(name)s: %(message)s")
logging.getLogger("app").setLevel(logging.INFO)

app = FastAPI(title="Smart Expense Tracker")
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().CORS_ORIGINS,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Content-Type", "Authorization"],
    # Lets the browser send and store the refresh cookie on cross-origin calls.
    # Requires an explicit origin list - it's refused with "*".
    allow_credentials=True,
)
app.include_router(auth.router)
app.include_router(expenses.router)
app.include_router(stats.router)
app.include_router(parse.router)
app.include_router(budgets.router)
app.include_router(repeats.router)


@app.get("/health")
def health():
    return {"status": "ok"}
