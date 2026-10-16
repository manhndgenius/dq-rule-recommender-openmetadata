"""Regression tests for rendering Advanced-rule bind parameters."""

from backend.engine.sql_mapper.sql_renderer import render_sql_literal


def test_render_encounter_conditional_dependency_sql() -> None:
    sql = (
        'SELECT * FROM "encounters" WHERE '
        '(("encounter_class" = :rule_param_1) AND '
        '("code" <> :rule_param_2) OR '
        '("encounter_class" = :rule_param_3) AND '
        '("code" <> :rule_param_4))'
    )

    rendered = render_sql_literal(
        sql,
        {
            "rule_param_1": "ambulatory",
            "rule_param_2": "108219001",
            "rule_param_3": "wellness",
            "rule_param_4": "86013001",
        },
    )

    assert ":rule_param_" not in rendered
    assert '"encounter_class" = \'ambulatory\'' in rendered
    assert '"code" <> \'108219001\'' in rendered
    assert '"encounter_class" = \'wellness\'' in rendered
    assert '"code" <> \'86013001\'' in rendered
