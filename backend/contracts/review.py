from typing import Any, Dict, Literal, Optional

from pydantic import BaseModel


class ReviewActionRequest(BaseModel):
    action: Literal["ACCEPTED", "REJECTED", "EDITED"]
    edited_parameters: Optional[Dict[str, Any]] = None
    comment: Optional[str] = None
