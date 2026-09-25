"""Small production-candidate smoke test. Run after installing requirements."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import app


def main():
    client = app.test_client()

    health = client.get("/healthz")
    assert health.status_code == 200, health.data

    ready = client.get("/readyz")
    assert ready.status_code == 200, ready.data

    check_page = client.get("/check")
    assert check_page.status_code == 200
    with client.session_transaction() as sess:
        csrf = sess.get("_csrf_token")
    assert csrf

    response = client.post("/check", data={
        "_csrf_token": csrf,
        "app_name": "GeM Sahay",
    })
    assert response.status_code == 200, response.data[:500]
    assert b"Identity Verification" in response.data
    assert b"Cost calculation was skipped" in response.data

    if app.config.get("ENABLE_API"):
        api = client.post("/api/v1/check", json={"app_name": "GeM Sahay"})
        assert api.status_code == 200, api.data
        payload = api.get_json()
        assert payload["directory"]["status"] in {"Listed", "Unclear", "Not listed"}
        assert "decision" in payload
        directory_status = payload["directory"]["status"]
        decision = payload["decision"]["verdict"]
    else:
        api = client.post("/api/v1/check", json={"app_name": "GeM Sahay"})
        assert api.status_code == 404, api.data
        directory_status = "checked via browser flow"
        decision = "checked via browser flow"

    print("Production smoke test: PASS")
    print("Ready:", ready.get_json().get("status"))
    print("Directory:", directory_status)
    print("Decision:", decision)


if __name__ == "__main__":
    main()
