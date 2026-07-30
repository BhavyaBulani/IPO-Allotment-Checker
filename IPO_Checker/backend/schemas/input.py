from pydantic import BaseModel, constr, Field
from typing import List

class SingleCheckRequest(BaseModel):
    # Basic validation for PAN: 5 letters, 4 digits, 1 letter. Client Code has its own format.
    # To support both, we do basic alphanumeric validation and handle specifics later.
    identifier: constr(min_length=1, max_length=20) = Field(..., description="PAN or Client Code")
    ipo_ids: List[int] = Field(..., min_items=1, description="List of IPO IDs to check against")
