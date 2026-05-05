from fastapi import FastAPI
from contextlib import asynccontextmanager
from core import kis_auth as ka

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("!!!fast api server start!!!")
    ka.auth()
    yield
    print("!!!fast api server end!!!")

app = FastAPI(
    title="Trading Server",
    lifespan=lifespan
)

@app.get("/")
def read_root():
    return {"Hello": "World"}


@app.get("/items/{item_id}")
def read_item(item_id: int, q: str | None = None):
    return {"item_id": item_id, "q": q}