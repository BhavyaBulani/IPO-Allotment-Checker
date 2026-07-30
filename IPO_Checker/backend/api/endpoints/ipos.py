from fastapi import APIRouter, Depends
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
        orm_mode = True
        from_attributes = True

@router.get("/", response_model=List[IpoResponse])
def get_validated_ipos(db: Session = Depends(get_db)):
    """Fetch all validated IPOs available for selection."""
    ipos = db.query(IPO).filter(IPO.validated == True).all()
    
    def sort_key(ipo):
        priority = 3
        if ipo.status == IPOStatus.Allotment_Announced:
            priority = 1
        elif ipo.status == IPOStatus.Open:
            priority = 2
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
