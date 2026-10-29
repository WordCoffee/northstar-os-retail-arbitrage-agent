from fastapi.testclient import TestClient
from calc import app

client = TestClient(app)

def test_ledger_period():
    resp = client.get("/ledger/period")
    assert resp.status_code == 200
    assert resp.json() == {"period": "2024-01"}
