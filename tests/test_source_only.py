from scripts.generate_brief import sample_items, source_only_brief


def test_source_only_brief_does_not_include_ai_fields() -> None:
    brief = source_only_brief("daily", sample_items(), 10)

    assert "(Source-Only)" in brief
    assert "AI scoring, John angles, draft quotes" in brief
    assert "Draft quote:" not in brief
    assert "Score:" not in brief


def test_source_only_brief_handles_empty_items() -> None:
    brief = source_only_brief("weekly", [], 10)

    assert "No recent source items were collected" in brief
    assert "did not call the OpenAI API" in brief
