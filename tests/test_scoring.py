from scripts.generate_brief import normalize_score, score_label


def test_normalize_score_accepts_int_float_and_text() -> None:
    assert normalize_score(5) == 5
    assert normalize_score(4.4) == 4
    assert normalize_score("Score: 3 - Monitor") == 3


def test_normalize_score_clamps_out_of_range_values() -> None:
    assert normalize_score(99) == 5
    assert normalize_score(-2) == 1
    assert normalize_score("no score") == 1


def test_score_label_maps_to_required_labels() -> None:
    assert score_label(5) == "Pitch now"
    assert score_label(4) == "Prepare commentary"
    assert score_label(3) == "Monitor"
    assert score_label(2) == "Keep for content"
    assert score_label(1) == "Ignore"
