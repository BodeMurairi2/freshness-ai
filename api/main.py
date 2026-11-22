import uvicorn
from fastapi import FastAPI
from api.router import routing
from api.services.app_description import app_information

app = FastAPI(
    title=app_information["title"],
    summary=app_information["summary"],
    description=app_information["description"],
    version=app_information["version"]
)

@app.get("/")
async def welcome():
    return {
        "message":"Welcome to Freshnesss-ai"
    }

routing(app=app)

if __name__ == "__main__":
    uvicorn.run(
        app="api.main:app",
        port=8000,
        reload=True
    )
