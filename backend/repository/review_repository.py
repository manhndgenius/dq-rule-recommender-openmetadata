from backend.contracts.review import ReviewActionRequest


class ReviewRepository:
    def save(self, rule_id: str, review: ReviewActionRequest) -> None:
        raise NotImplementedError
