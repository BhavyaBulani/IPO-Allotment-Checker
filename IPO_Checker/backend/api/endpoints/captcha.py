import base64
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from registrar_services.captcha_manager import captcha_manager
from typing import List

router = APIRouter()

class CaptchaResponse(BaseModel):
    captcha_id: str
    image_base64: str

class CaptchaSubmitRequest(BaseModel):
    captcha_id: str
    solution: str

@router.get("/pending", response_model=List[CaptchaResponse])
def get_pending_captchas():
    """Returns a list of currently pending CAPTCHAs that need manual solving."""
    results = []
    for cid, data in captcha_manager.pending_captchas.items():
        if data["status"] == "pending":
            b64 = base64.b64encode(data["image"]).decode('utf-8')
            results.append(CaptchaResponse(captcha_id=cid, image_base64=b64))
    return results

@router.post("/submit")
def submit_captcha_solution(request: CaptchaSubmitRequest):
    """Submits a solution for a pending CAPTCHA."""
    success = captcha_manager.submit_solution(request.captcha_id, request.solution)
    if not success:
        raise HTTPException(status_code=400, detail="Invalid captcha_id or CAPTCHA is already solved/expired.")
    return {"status": "success", "message": "Solution accepted."}
