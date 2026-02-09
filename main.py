import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.backend.agent.core.SheetHero import SheetHero
from src.backend.config.settings import Config

app = FastAPI()
origins = ["http://localhost:3480"]
app.add_middleware(
    CORSMiddleware,
    allow_origins = origins,
    allow_credentials = True,
    allow_methods = ["*"],
    allow_headers = ["*"],
)


@app.get("/test")
def test():
    print("test")
    return "This is a test"


@app.get("/sheet-hero/run")
def run_sheet_hero_api():
    config = Config(
        api_key = ""
    )
    agent = SheetHero(
        excel_paths = ["D:\\output.xlsx"],
        config = config,
    )

    result = agent.run(
        user_question = "test",
    )

    return { "result": result }


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port = 8000)