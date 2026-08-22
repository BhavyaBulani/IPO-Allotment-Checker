from pydantic import BaseModel, constr, Field
from typing import List


class SingleCheckRequest(BaseModel):
    # Kept for backwards compatibility with the previous multi-IPO flow.
    identifier: constr(min_length=1, max_length=20) = Field(..., description="PAN or Client Code")
    ipo_ids: List[int] = Field(..., min_items=1, description="List of IPO IDs to check against")


class PanCheckRequest(BaseModel):
    """PAN-only check: the backend checks the identifier against all validated IPOs."""

    identifier: constr(min_length=10, max_length=10) = Field(
        ..., description="Indian PAN (10 characters, e.g. ABCDE1234F)"
    )
