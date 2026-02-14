import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from typing import List
from pydantic import BaseModel

from src.backend.agent.core.SheetHero import SheetHero
from src.backend.config.settings import Config
from src.backend.service.sheethero_service import SheetHeroService
from src.backend.service.stream_dialogue_driver import StreamDialogueDriver

app = FastAPI()
origins = ["http://localhost:3480"]
app.add_middleware(
    CORSMiddleware,
    allow_origins = origins,
    allow_credentials = True,
    allow_methods = ["*"],
    allow_headers = ["*"],
)

class SheetHeroRequest(BaseModel):
    api_key: str
    model: str
    max_turns: int
    prompt: str
    excel_paths: List[str]

@app.post("/sheet-hero/run")
def run_sheet_hero_api(request: SheetHeroRequest):
    print(request.api_key)
    service = SheetHeroService(config = Config(
        api_key=request.api_key,
        deployment=request.model,
        max_turns=request.max_turns,
    ))
    result = service.submit_turn(
        excel_paths=request.excel_paths,
        prompt=request.prompt,
    )

    return { "result": result }


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port = 8000)