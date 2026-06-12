from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from agents.planner import PlannerAgent, PlannerError

app = FastAPI(title="Agentic SDLC API")
planner = PlannerAgent()


class PlanRequest(BaseModel):
    requirements: str = Field(min_length=1)


@app.post("/plan")
async def create_plan(request: PlanRequest) -> dict:
    try:
        return await planner.plan(request.requirements)
    except PlannerError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
