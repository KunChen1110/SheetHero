import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from typing import List
from pydantic import BaseModel

from src.backend.agent.core.SheetHero import SheetHero
from src.backend.config.settings import Config
from src.backend.service.sheethero_service import SheetHeroService
from src.backend.service.stream_dialogue_driver import StreamDialogueDriver

sessions: Dict[str, StreamDialogueDriver] = {}

app = FastAPI()
origins = ["http://localhost:3480"]
app.add_middleware(
    CORSMiddleware,
    allow_origins = origins,
    allow_credentials = True,
    allow_methods = ["*"],
    allow_headers = ["*"],
)

class SheetHeroStartRequest(BaseModel):
    session_id: str
    api_key: str
    model: str
    max_turns: int
    prompt: str
    excel_paths: List[str]


class SheetHeroReplyRequest(BaseModel):
    session_id: str
    user_reply: str

@app.post("/sheet-hero/start")
def start_sheet_hero(request: SheetHeroStartRequest):
    """Start a new conversation"""
    service = SheetHeroService(config=Config(
        api_key=request.api_key,
        deployment=request.model,
        max_turns=request.max_turns,
    ))

    driver = StreamDialogueDriver(service)
    sessions[request.session_id] = driver
    
    stream = driver.start(
        excel_paths=request.excel_paths,
        prompt=request.prompt,
    )
    
    events = list(stream)
    return {"events": events}

@app.post("/sheet-hero/reply")
def reply_sheet_hero(request: SheetHeroReplyRequest):
    """Reply to a clarification question"""
    if request.session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    driver = sessions[request.session_id]
    stream = driver.reply(request.user_reply)
    
    events = list(stream)
    return {"events": events}

@app.delete("/sheet-hero/session/{session_id}")
def end_session(session_id: str):
    """Clean up a session"""
    if session_id in sessions:
        del sessions[session_id]
    return {"status": "ok"}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port = 8000)