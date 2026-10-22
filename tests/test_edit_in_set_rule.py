import pytest
from backend.contracts.candidate_rule import CandidateRule
from backend.contracts.review import ReviewActionRequest
from backend.review.review_service import ReviewService
from backend.integrations.openmetadata_publisher import OpenMetadataPublisher
from backend.storage.generation_cache import GenerationCache


def test_review_action_request_normalizes_case_and_syncs_params():
    # Test case-insensitive action and parameters alias
    req1 = ReviewActionRequest(action="edit", parameters={"allowedValues": ["A", "B"]})
    assert req1.action == "EDITED"
    assert req1.edited_parameters == {"allowedValues": ["A", "B"]}

    req2 = ReviewActionRequest(action="ACCEPTED", edited_parameters={"allowedValues": ["A"]})
    assert req2.action == "ACCEPTED"
    assert req2.edited_parameters == {"allowedValues": ["A"]}


def test_review_service_updates_in_set_rule_to_valid():
    service = ReviewService()
    initial_rule = CandidateRule(
        id="rule_inset_test_1",
        rule_type="columnValuesToBeInSet",
        target_columns=["status"],
        parameters={},
        reason="Low cardinality",
        validation_status="WARNING",
        validation_message="Cần nhập allowedValues trước khi Accept/Publish rule.",
        status="DRAFT",
    )
    service.save_candidates([initial_rule])

    req = ReviewActionRequest(
        action="EDITED",
        edited_parameters={"allowedValues": ["ACTIVE", "INACTIVE", "PENDING"]},
    )
    updated = service.review("rule_inset_test_1", req)

    assert updated is not None
    assert updated.status == "EDITED"
    assert updated.parameters == {"allowedValues": ["ACTIVE", "INACTIVE", "PENDING"]}
    assert updated.edited_parameters == {"allowedValues": ["ACTIVE", "INACTIVE", "PENDING"]}
    assert updated.validation_status == "VALID"
    assert updated.validation_message is None

    # Verify publisher produces valid payload with comma-separated values
    publisher = OpenMetadataPublisher("http://openmetadata.test/api/v1")
    payload, err = publisher.build_test_case_payload(updated, "svc.db.public.users")
    assert err is None
    assert payload["parameterValues"] == [
        {"name": "allowedValues", "value": "ACTIVE,INACTIVE,PENDING"}
    ]


def test_generation_cache_updates_in_set_rule_to_valid():
    cache = GenerationCache()
    rule = CandidateRule(
        id="rule_cache_inset_1",
        rule_type="columnValuesToBeInSet",
        target_columns=["status"],
        parameters={},
        reason="Test",
        validation_status="WARNING",
        validation_message="Cần nhập allowedValues",
        status="DRAFT",
    )
    cache.save("svc.db.public.orders", "BASIC", [rule])

    success = cache.update_status(
        "rule_cache_inset_1",
        "EDITED",
        edited_parameters={"allowedValues": ["NEW", "PAID"]},
    )
    assert success is True

    cached_rules = cache.get("svc.db.public.orders", "BASIC")
    assert len(cached_rules) == 1
    cached = cached_rules[0]
    assert cached.status == "EDITED"
    assert cached.validation_status == "VALID"
    assert cached.validation_message is None
    assert cached.parameters == {"allowedValues": ["NEW", "PAID"]}
