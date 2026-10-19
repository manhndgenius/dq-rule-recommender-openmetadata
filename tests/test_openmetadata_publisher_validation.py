from backend.contracts.candidate_rule import CandidateRule
from backend.integrations.openmetadata_publisher import OpenMetadataPublisher


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
