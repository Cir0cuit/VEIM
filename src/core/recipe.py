from abc import ABC, abstractmethod
import requests
from enum import Enum, auto

class UpdateMechanism(Enum):
    FedoraAPI = auto()
    UbuntuStreams = auto()
    HtmlScraper = auto()
    GithubRelease = auto()
    DirectMido = auto()
    DebianDirectory = auto()
    PopOSAPI = auto()
    Custom = auto()

class DistroRecipe(ABC):
    def __init__(self, name: str, family: str, flavor: str, arch: str = "x86_64", update_mechanism: UpdateMechanism = UpdateMechanism.Custom):
        self.name = name
        self.family = family
        self.flavor = flavor
        self.arch = arch
        self.update_mechanism = update_mechanism
        
        # Common headers for spoofing
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        }

    def get_session(self) -> requests.Session:
        """Returns a requests.Session with spoofed User-Agent."""
        from src.core.logger import log
        session = requests.Session()
        session.headers.update(self.headers)
        
        # Hook to log requests
        def log_request(response, *args, **kwargs):
            log.debug(f"HTTP {response.status_code} {response.request.method} {response.url}")
            if response.status_code != 200:
                log.warning(f"  > Response: {response.text[:200]}...")
                
        session.hooks['response'] = [log_request]
        return session

    @abstractmethod
    def get_download_info(self) -> tuple[str, str, str]:
        """
        Returns (LatestVersionString, DownloadURL, HashString).
        HashString can be None or empty if not available.
        """
        pass

    def __repr__(self):
        return f"<DistroRecipe {self.name} ({self.flavor})>"
