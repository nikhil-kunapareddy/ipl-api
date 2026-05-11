from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.middleware import APIKeyMiddleware
from app.routes import register, matches, players, teams

app = FastAPI(
    title="IPL API",
    description="A production-ready REST API for IPL cricket data powered by Cricsheet.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(APIKeyMiddleware)

app.include_router(register.router, prefix="/v1")
app.include_router(matches.router, prefix="/v1")
app.include_router(players.router, prefix="/v1")
app.include_router(teams.router, prefix="/v1")


@app.get("/")
def root():
    return {
        "name": "IPL API",
        "version": "1.0.0",
        "docs": "/docs",
    }
