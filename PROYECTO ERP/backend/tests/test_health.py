def test_healthz(client):
    r = client.get("/healthz")
    assert r.status_code == 200
    body = r.get_json()
    assert body["status"] == "ok"


def test_v1_root(client):
    r = client.get("/api/v1/")
    assert r.status_code == 200
    body = r.get_json()
    assert body["api"] == "casasalco"
