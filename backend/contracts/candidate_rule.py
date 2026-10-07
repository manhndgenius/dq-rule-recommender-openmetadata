from typing import List, Optional, Dict, Any, Literal
from pydantic import BaseModel, Field
import uuid
from datetime import datetime, timezone

class CandidateRule(BaseModel):
    id: str = Field(default_factory=lambda: f"rule_{uuid.uuid4().hex[:8]}")
    rule_type: str
    description: Optional[str] = None
    target_columns: List[str]
    parameters: Dict[str, Any] = Field(default_factory=dict)
    expression: Optional[str] = None
    engine: Literal["BASIC", "ADVANCED"] = "BASIC"
    confidence: float = 1.0
    reason: str
    evidence: Dict[str, Any] = Field(default_factory=dict)
    validation_status: Literal["VALID", "WARNING", "INVALID"] = "VALID"
    validation_message: Optional[str] = None
    status: Literal["DRAFT", "ACCEPTED", "EDITED", "REJECTED"] = "DRAFT"
    edited_parameters: Optional[Dict[str, Any]] = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
