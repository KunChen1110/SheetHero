import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional
from pydantic import BaseModel

from backend.agent.core.SheetHero import SheetHero
from backend.config.settings import Config
from backend.service.sheethero_service import SheetHeroService
from backend.service.stream_dialogue_driver import StreamDialogueDriver

sessions: dict[str, StreamDialogueDriver] = {}

app = FastAPI()
origins = ["http://localhost:3480"]
app.add_middleware(
    CORSMiddleware,
    allow_origins = origins,
    allow_credentials = True,
    allow_methods = ["*"],
    allow_headers = ["*"],
)


# Request for starting a new conversation
class SheetHeroStartRequest(BaseModel):
    session_id: str
    api_key: str
    model: str
    max_turns: int
    prompt: str
    base_url: Optional[str] = None 
    output_file: str
    output_mode: str = "file"
    excel_paths: List[str]


# Request for replying to a clarification question
class SheetHeroReplyRequest(BaseModel):
    session_id: str
    user_reply: str


# Starts a new conversation
@app.post("/sheet-hero/start")
def start_sheet_hero(request: SheetHeroStartRequest):
    service = SheetHeroService(config=Config(
        api_key=request.api_key,
        deployment=request.model,
        max_turns=request.max_turns,
        base_url=request.base_url,
        output_file=request.output_file,
        output_mode=request.output_mode, 
    ))

    driver = StreamDialogueDriver(service)
    sessions[request.session_id] = driver
    
    stream = driver.start(
        excel_paths=request.excel_paths,
        prompt=request.prompt,
    )
    
    events = list(stream)
    return {"events": events}


# Replies to a clarification question
@app.post("/sheet-hero/reply")
def reply_sheet_hero(request: SheetHeroReplyRequest):
    if request.session_id not in sessions:
        return {"error": "Session not found"}
    
    driver = sessions[request.session_id]
    stream = driver.reply(request.user_reply)
    
    events = list(stream)
    return {"events": events}


# Cleans up a session
@app.delete("/sheet-hero/session/{session_id}")
def end_session(session_id: str):
    if session_id in sessions:
        del sessions[session_id]
    return {"status": "ok"}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port = 8000)