from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from db.session import get_db
from db.models import IPO, IPOStatus
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

router = APIRouter()

class IpoResponse(BaseModel):
    id: int
    name: str
    status: str
    auto_detected: bool
    open_date: Optional[datetime]
    close_date: Optional[datetime]
    source: Optional[str]

    class Config:
        from_attributes = True

@router.get("/", response_model=List[IpoResponse])
def get_validated_ipos(
    db: Session = Depends(get_db),
    checkable: bool = Query(
        False,
        description="Return only IPOs whose allotment is announced (i.e. actually checkable right now).",
    ),
):
    """Fetch validated IPOs available for selection.

    With ``checkable=true`` only IPOs in ``Allotment Announced`` status are
    returned, so the dashboard dropdown never offers an IPO whose verdict is
    still pending (a registrar has no record yet for those).
    """
    query = db.query(IPO).filter(IPO.validated == True)
    if checkable:
        query = query.filter(IPO.status == IPOStatus.Allotment_Announced)
    ipos = query.all()
    
    def sort_key(ipo):
        priority = 4
        if ipo.status == IPOStatus.Open:
            priority = 1
        elif ipo.status == IPOStatus.Upcoming:
            priority = 2
        elif ipo.status == IPOStatus.Allotment_Announced:
            priority = 3
        elif ipo.status == IPOStatus.Closed:
            priority = 4
        return (priority, ipo.name)
        
    sorted_ipos = sorted(ipos, key=sort_key)
    
    return [
        {
            "id": ipo.id, 
            "name": ipo.name, 
            "status": ipo.status.value, 
            "auto_detected": ipo.auto_detected,
            "open_date": ipo.open_date,
            "close_date": ipo.close_date,
            "source": ipo.source
        } for ipo in sorted_ipos
    ]
