from typing import List, Literal

from pydantic import BaseModel, Field


class ValidationResult(BaseModel):
    status: Literal["PENDING", "VALID", "WARNING", "INVALID"] = "PENDING"
    messages: List[str] = Field(default_factory=list)
