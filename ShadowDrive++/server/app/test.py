from fastapi import FastAPI

app = FastAPI()
#to run-> uvicorn app.test:app --reload
@app.get("/")
def read_root():
    return {"message": "Hello, ShadowDrive!"}