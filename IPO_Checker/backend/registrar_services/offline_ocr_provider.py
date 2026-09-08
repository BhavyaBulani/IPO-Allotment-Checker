"""Offline CAPTCHA OCR provider backed by ddddocr.

Solves image CAPTCHAs locally (no 2Captcha key, no human in the loop). Bigshare
currently serves a clean six-character image CAPTCHA, and ddddocr's bundled
model reads it reliably. The model is loaded once and cached; the import is
lazy so the rest of the app keeps working even when ddddocr is not installed
(in which case ``solve`` simply returns None and callers fall back).
"""

import logging
from typing import Optional

from .captcha_provider import CaptchaProvider

logger = logging.getLogger(__name__)

_OCR = None
_OCR_ERROR = None


class OfflineOcrProvider(CaptchaProvider):
    """Solve image CAPTCHAs with ddddocr's onnx model."""

    def _get_model(self):
        global _OCR, _OCR_ERROR
        if _OCR is None and _OCR_ERROR is None:
            try:
                import ddddocr  # noqa: PLC0415 - lazy so a missing dep is not fatal
                _OCR = ddddocr.DdddOcr(show_ad=False)
            except Exception as exc:  # noqa: BLE001 - any failure disables OCR cleanly
                _OCR_ERROR = exc
                logger.warning("ddddocr offline OCR unavailable: %s", exc)
        return _OCR

    def solve(self, image_bytes: bytes, context: dict = None) -> Optional[str]:
        model = self._get_model()
        if model is None:
            return None
        try:
            result = model.classification(image_bytes)
        except Exception as exc:  # noqa: BLE001 - a bad image must not crash the check
            logger.warning("Offline OCR classification failed: %s", exc)
            return None
        text = (result or "").strip()
        return text or None

    @property
    def provider_name(self) -> str:
        return "offline_ocr"
