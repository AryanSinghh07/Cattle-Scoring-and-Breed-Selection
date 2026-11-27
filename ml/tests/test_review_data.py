import json

import pytest

from gopalan_ml.review_data import read_review_export

RECORD = {
    "analysis_id": "a1", "decision": "corrected", "label_bcs": 3.25, "label_breed": "gir",
    "model_bcs": 2.75, "model_breed": "kankrej", "photos": {"side": "u/a1/side.jpg"},
    "points": {"side": {"nose": {"x": 1, "y": 2}}}, "marker": {"side": 0.4}, "measurements": {}, "model_versions": {},
}


def write(tmp_path, *records):
    p = tmp_path / "labels.jsonl"
    p.write_text("".join(json.dumps(r) + "\n" for r in records), encoding="utf-8")
    return p


def test_reads_jsonl_and_computes_error(tmp_path):
    [lab] = read_review_export(write(tmp_path, RECORD))
    assert lab.label_bcs == 3.25 and lab.label_breed == "gir"
    assert lab.bcs_error == pytest.approx(-0.5)
    assert lab.photos == {"side": "u/a1/side.jpg"}


@pytest.mark.parametrize("bad", [{"label_bcs": 3.1}, {"label_bcs": 6}, {"label_breed": "jersey"}, {"decision": "maybe"}])
def test_rejects_invalid_labels(tmp_path, bad):
    with pytest.raises(ValueError):
        read_review_export(write(tmp_path, {**RECORD, **bad}))


def test_empty_export(tmp_path):
    assert read_review_export(write(tmp_path)) == []
