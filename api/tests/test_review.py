import csv
import io
import json

import pytest

from tests.test_records import A, B, analyze, api, fake, jpeg_with_gps, save, save_payload  # noqa: F401  (fixtures)

R = {"Authorization": "Bearer token-r"}
R2 = {"Authorization": "Bearer token-r2"}


@pytest.fixture
def saved(api):  # noqa: F811
    """Farmer A saves two analyses with photo consent and one without."""
    first = analyze(api)
    ids = []
    for consent in (True, True, False):
        r = save(api, A, save_payload(first, photo_consent=consent), photo=jpeg_with_gps())
        assert r.status_code == 201, r.text
        ids.append(r.json()["analysis"]["id"])
    return {"consented": ids[:2], "private": ids[2], "model_bcs": r.json()["analysis"]["bcs_score"]}


def test_only_reviewers_can_review(api, saved):  # noqa: F811
    for headers in (A, B):
        r = api.get("/review/queue", headers=headers)
        assert r.status_code == 403 and r.json()["error"] == "not_reviewer"
        assert api.put(f"/review/{saved['consented'][0]}", headers=headers, json={"decision": "confirmed"}).status_code == 403
    assert api.get("/review/queue").status_code == 401


def test_queue_lists_consented_unreviewed_with_photos(api, saved):  # noqa: F811
    body = api.get("/review/queue", headers=R).json()
    assert body["waiting"] == 2
    assert {i["id"] for i in body["items"]} == set(saved["consented"])  # the private one is never listed
    assert all(i["photo_urls"]["side"].startswith("https://fake.supabase.co/") for i in body["items"])
    assert api.get(f"/review/{saved['private']}", headers=R).status_code == 404


def test_confirm_fills_in_model_values_and_leaves_queue(api, saved):  # noqa: F811
    target = saved["consented"][0]
    r = api.put(f"/review/{target}", headers=R, json={"decision": "confirmed", "notes": "looks right"})
    assert r.status_code == 200, r.text
    review = r.json()
    assert review["bcs_score"] == saved["model_bcs"] and review["breed_slug"] == "gir"

    queue = api.get("/review/queue", headers=R2).json()  # another reviewer no longer sees it
    assert queue["waiting"] == 1 and [i["id"] for i in queue["items"]] == [saved["consented"][1]]

    item = api.get(f"/review/{target}", headers=R).json()
    assert item["my_review"]["decision"] == "confirmed" and "side" in item["photo_urls"]


def test_correct_and_update_review(api, saved, fake):  # noqa: F811
    target = saved["consented"][0]
    r = api.put(f"/review/{target}", headers=R, json={"decision": "corrected", "bcs_score": 3.5, "breed_slug": "kankrej"})
    assert r.status_code == 200, r.text
    r = api.put(f"/review/{target}", headers=R, json={"decision": "corrected", "bcs_score": 3.75})
    assert r.status_code == 200
    assert len(fake.tables["reviews"]) == 1  # updated, not duplicated
    assert fake.tables["reviews"][0]["bcs_score"] == 3.75

    # the farmer can see the review of their own analysis
    detail = api.get(f"/analyses/{target}", headers=A)
    assert detail.status_code == 200


@pytest.mark.parametrize("payload,message", [
    ({"decision": "corrected"}, "needs a different"),
    ({"decision": "confirmed", "bcs_score": 4.75}, "use decision 'corrected'"),
])
def test_review_rules(api, saved, payload, message):  # noqa: F811
    r = api.put(f"/review/{saved['consented'][0]}", headers=R, json=payload)
    assert r.status_code == 422 and message in r.json()["message"]


@pytest.mark.parametrize("payload", [
    {"decision": "corrected", "bcs_score": 3.1},
    {"decision": "corrected", "bcs_score": 6},
    {"decision": "corrected", "breed_slug": "jersey"},
    {"decision": "maybe"},
])
def test_review_validation(api, saved, payload):  # noqa: F811
    assert api.put(f"/review/{saved['consented'][0]}", headers=R, json=payload).status_code == 422


def test_export_jsonl_and_csv(api, saved):  # noqa: F811
    api.put(f"/review/{saved['consented'][0]}", headers=R, json={"decision": "corrected", "bcs_score": 3.5})
    api.put(f"/review/{saved['consented'][1]}", headers=R, json={"decision": "confirmed"})

    r = api.get("/review/export/labels", headers=R)
    assert r.status_code == 200 and r.headers["content-type"].startswith("application/x-ndjson")
    rows = [json.loads(line) for line in r.text.splitlines()]
    assert len(rows) == 2
    corrected = next(x for x in rows if x["decision"] == "corrected")
    assert corrected["label_bcs"] == 3.5 and corrected["model_bcs"] == saved["model_bcs"]
    assert corrected["photos"]["side"].endswith("/side.jpg") and corrected["points"]["side"]["nose"]

    r = api.get("/review/export/labels?format=csv", headers=R)
    table = list(csv.DictReader(io.StringIO(r.text)))
    assert len(table) == 2 and json.loads(table[0]["photos"])["side"]

    assert api.get("/review/export/labels", headers=R2).text == ""  # R2 reviewed nothing
    assert api.get("/review/export/labels", headers=A).status_code == 403


def test_export_is_readable_by_training_code(api, saved, tmp_path):  # noqa: F811
    from gopalan_ml.review_data import read_review_export

    api.put(f"/review/{saved['consented'][0]}", headers=R, json={"decision": "corrected", "bcs_score": 3.5})
    api.put(f"/review/{saved['consented'][1]}", headers=R, json={"decision": "confirmed"})
    for fmt in ("jsonl", "csv"):
        f = tmp_path / f"labels.{fmt}"
        f.write_text(api.get(f"/review/export/labels?format={fmt}", headers=R).text, encoding="utf-8")
        labels = read_review_export(f)
        assert {lab.decision for lab in labels} == {"confirmed", "corrected"}
        corrected = next(lab for lab in labels if lab.decision == "corrected")
        assert corrected.label_bcs == 3.5
        assert corrected.bcs_error == pytest.approx(saved["model_bcs"] - 3.5)
        assert corrected.photos["side"].endswith("side.jpg") and "nose" in corrected.points["side"]
