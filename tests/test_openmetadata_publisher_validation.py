from backend.contracts.candidate_rule import CandidateRule
from backend.integrations.openmetadata_publisher import OpenMetadataPublisher


class _Response:
    def __init__(self, status_code, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text

    def json(self):
        return self._payload


def _in_set_rule(parameters):
    return CandidateRule(
        rule_type="columnValuesToBeInSet",
        target_columns=["event_status"],
        parameters=parameters,
        reason="Low-cardinality column",
        status="ACCEPTED",
    )


def test_in_set_rule_requires_allowed_values_before_publish():
    payload, error = OpenMetadataPublisher(
        server_url="http://openmetadata.test/api/v1"
    ).build_test_case_payload(
        _in_set_rule({}),
        "svc.db.public.events",
    )

    assert payload == {}
    assert error == "allowedValues must be configured before publishing"


def test_in_set_rule_can_publish_after_allowed_values_are_configured():
    payload, error = OpenMetadataPublisher(
        server_url="http://openmetadata.test/api/v1"
    ).build_test_case_payload(
        _in_set_rule({"allowedValues": ["OPEN", "CLOSED"]}),
        "svc.db.public.events",
    )

    assert error is None
    assert payload["parameterValues"] == [
        {"name": "allowedValues", "value": "OPEN,CLOSED"}
    ]


def _not_null_rule():
    return CandidateRule(
        id="basic_1f1322413c9e79a30817",
        rule_type="columnValuesToBeNotNull",
        target_columns=["patient_id"],
        engine="BASIC",
        confidence=1.0,
        reason="Column profile has no null values",
        status="ACCEPTED",
    )


def test_publish_posts_when_test_case_does_not_exist(monkeypatch):
    publisher = OpenMetadataPublisher(
        server_url="http://openmetadata.test/api/v1",
        token="bot-token",
    )
    calls = []

    monkeypatch.setattr(
        "backend.integrations.openmetadata_publisher.requests.get",
        lambda url, **kwargs: calls.append(("GET", url, kwargs))
        or _Response(404),
    )

    def fake_post(url, **kwargs):
        calls.append(("POST", url, kwargs))
        return _Response(
            201,
            {
                "id": "case-id",
                "name": kwargs["json"]["name"],
                "fullyQualifiedName": (
                    "healthcare_postgres.HealthCare.public.claims."
                    + kwargs["json"]["name"]
                ),
            },
        )

    monkeypatch.setattr(
        "backend.integrations.openmetadata_publisher.requests.post",
        fake_post,
    )
    monkeypatch.setattr(
        "backend.integrations.openmetadata_publisher.requests.put",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("PUT must not create a missing TestCase")
        ),
    )

    result = publisher.publish_rules(
        [_not_null_rule()],
        "claims",
        table_fqn="healthcare_postgres.HealthCare.public.claims",
    )

    assert result["published_count"] == 1
    assert result["failed_count"] == 0
    assert [method for method, _, _ in calls] == ["GET", "POST"]
    assert calls[0][1].endswith(
        "/dataQuality/testCases/name/"
        "healthcare_postgres.HealthCare.public.claims."
        "claims_patient_id_columnvaluestobenotnull_a30817"
    )
    assert calls[1][2]["headers"]["Authorization"] == "Bearer bot-token"


def test_publish_puts_when_test_case_already_exists(monkeypatch):
    publisher = OpenMetadataPublisher(
        server_url="http://openmetadata.test/api/v1",
        token="bot-token",
    )
    calls = []

    monkeypatch.setattr(
        "backend.integrations.openmetadata_publisher.requests.get",
        lambda url, **kwargs: calls.append(("GET", url))
        or _Response(200, {"id": "case-id"}),
    )

    def fake_put(url, **kwargs):
        calls.append(("PUT", url))
        return _Response(
            200,
            {
                "id": "case-id",
                "name": kwargs["json"]["name"],
                "fullyQualifiedName": (
                    "healthcare_postgres.HealthCare.public.claims."
                    + kwargs["json"]["name"]
                ),
            },
        )

    monkeypatch.setattr(
        "backend.integrations.openmetadata_publisher.requests.put",
        fake_put,
    )
    monkeypatch.setattr(
        "backend.integrations.openmetadata_publisher.requests.post",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("POST must not recreate an existing TestCase")
        ),
    )

    result = publisher.publish_rules(
        [_not_null_rule()],
        "claims",
        table_fqn="healthcare_postgres.HealthCare.public.claims",
    )

    assert result["published_count"] == 1
    assert result["failed_count"] == 0
    assert [method for method, _ in calls] == ["GET", "PUT"]
