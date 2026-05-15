from fastapi import FastAPI

from app.api.routes import router

# =========================================================
# FASTAPI APP INITIALIZATION
# =========================================================
app = FastAPI(
    title="GuardPath-NG",
    version="1.0.0"
)

# =========================================================
# ROUTES
# =========================================================
app.include_router(router)
