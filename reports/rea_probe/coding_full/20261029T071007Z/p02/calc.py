from fastapi import FastAPI

app = FastAPI()

@app.get("/ledger/period")
def get_ledger_period():
    return {"period": "2024-01"}
