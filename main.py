from fastapi import FastAPI
import uvicorn
import os
from routes.user_route import user_router
from routes.messaging_routes import messaging_router
from helpers import get_env_value
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()
app.include_router(user_router)
app.include_router(messaging_router)
frontend_origins = os.getenv("FRONTEND_BASE_URL", "")
if frontend_origins:
    origins = [o.strip() for o in frontend_origins.split(",")]
else:
    # local dev defaults
    origins = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,          # or ["*"] for local dev
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if __name__ == "__main__":
    port: str = get_env_value("PORT", default="8000")
    uvicorn.run("main:app", host="0.0.0.0", port=int(port), log_level="info", reload=True)
