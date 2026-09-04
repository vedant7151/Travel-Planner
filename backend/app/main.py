from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Travel Planner API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)

@app.get("/")
def read_root():
    return {"status": "ok"}

@app.post("/api/v1/trips/plan")
def plan_trip(request: dict):
    # Stub for planning logic
    return {"status": "queued", "trip_id": "test"}
