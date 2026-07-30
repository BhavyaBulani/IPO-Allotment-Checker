from abc import ABC, abstractmethod
from typing import Optional

class CaptchaProvider(ABC):
    """Base interface for all CAPTCHA solving mechanisms."""
    
    @abstractmethod
    def solve(self, image_bytes: bytes, context: dict = None) -> Optional[str]:
        """
        Takes an image as bytes and returns the solved CAPTCHA string.
        Context can contain additional info like registrar_name, ipo_name.
        Returns None if solving fails or is aborted.
        """
        pass
    
    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Name of the provider (e.g. 'manual', '2captcha', 'mock_auto')"""
        pass
