from typing import Any, Dict, Literal, Optional

from pydantic import BaseModel, field_validator, model_validator


class ReviewActionRequest(BaseModel):
    action: Literal["ACCEPTED", "REJECTED", "EDITED"]
    edited_parameters: Optional[Dict[str, Any]] = None
    parameters: Optional[Dict[str, Any]] = None
    comment: Optional[str] = None

    @field_validator("action", mode="before")
    @classmethod
    def normalize_action(cls, v: Any) -> str:
        if isinstance(v, str):
            val = v.upper()
            if val in ("ACCEPT", "ACCEPTED"):
                return "ACCEPTED"
            if val in ("REJECT", "REJECTED"):
                return "REJECTED"
            if val in ("EDIT", "EDITED"):
                return "EDITED"
        return v

    @model_validator(mode="after")
    def sync_parameters(self) -> "ReviewActionRequest":
        if self.edited_parameters is None and self.parameters is not None:
            self.edited_parameters = self.parameters
        elif self.edited_parameters is not None and self.parameters is None:
            self.parameters = self.edited_parameters
        return self
