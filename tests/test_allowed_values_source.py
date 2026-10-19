from backend.storage.rule_repository import RuleRepository


def test_upsert_removes_only_stale_draft_for_same_logical_rule():
    class Cursor:
        def __init__(self):
            self.calls = []

        def execute(self, query, params):
            self.calls.append((" ".join(query.split()), params))

        @staticmethod
        def fetchone():
            return None

    cursor = Cursor()
    rule = {
        "id": "basic-new",
        "table_name": "encounters",
        "table_fqn": "svc.db.public.encounters",
        "engine": "BASIC",
        "rule_type": "columnValuesToBeInSet",
        "target_columns": ["encounter_class"],
        "parameters": {},
        "rule_fingerprint": "new-fingerprint",
    }

    assert RuleRepository()._upsert(cursor, rule) == "inserted"
    delete_query, delete_params = cursor.calls[0]
    assert delete_query.startswith("DELETE FROM dq_rules")
    assert "status='DRAFT'" in delete_query
    assert delete_params == (
        "svc.db.public.encounters",
        "BASIC",
        "columnValuesToBeInSet",
        ["encounter_class"],
        "new-fingerprint",
    )
