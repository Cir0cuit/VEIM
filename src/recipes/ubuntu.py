from src.core.recipe import DistroRecipe, UpdateMechanism
from bs4 import BeautifulSoup
import re

class UbuntuRecipe(DistroRecipe):
    def __init__(self, flavor: str = "Desktop"):
        # Flavors: "Desktop" (Standard), "Kubuntu", "Xubuntu", "Lubuntu", "Ubuntu MATE", "Ubuntu Budgie"
        name = f"Ubuntu {flavor}"
        super().__init__(name, "Debian-based", flavor, "x86_64", UpdateMechanism.UbuntuStreams)
        self.target_flavor = flavor

    def get_download_info(self) -> tuple[str, str, str]:
        from src.core.logger import log
        session = self.get_session()
        
        # Determine Base URL
        if self.target_flavor == "Desktop":
            base_url = "https://releases.ubuntu.com/"
        else:
            # Map flavor to URL slug
            slug_map = {
                "Kubuntu": "kubuntu",
                "Xubuntu": "xubuntu",
                "Lubuntu": "lubuntu",
                "Ubuntu MATE": "ubuntu-mate",
                "Ubuntu Budgie": "ubuntu-budgie"
            }
            slug = slug_map.get(self.target_flavor, "ubuntu")
            base_url = f"https://cdimage.ubuntu.com/{slug}/releases/"

        log.debug(f"[{self.name}] Checking base URL: {base_url}")

        # Step 1: Get list of release versions
        try:
            r = session.get(base_url, timeout=10)
            r.raise_for_status()
            soup = BeautifulSoup(r.text, 'lxml')
            
            versions = []
            for link in soup.find_all('a'):
                href = link.get('href', '').strip('/')
                if not href: continue
                # Check if it starts with digit
                if href[0].isdigit() and re.match(r'^\d+\.\d+(\.\d+)?$', href):
                    versions.append(href)
            
            if not versions:
                log.error(f"[{self.name}] No versions found at {base_url}")
                return ("Error parsing versions", "", "")
                
            # Sort semantic versions descending
            versions.sort(key=lambda s: [int(u) for u in s.split('.') if u.isdigit()], reverse=True)
            log.debug(f"[{self.name}] Top versions found: {versions[:5]}")
            
            # Check top 12 versions to bypass daily/dev builds
            for ver in versions[:12]:
                # Try standard directory first, then 'release' subfolder (common on cdimage)
                paths_to_check = [f"{base_url}{ver}/", f"{base_url}{ver}/release/"]
                
                for release_url in paths_to_check:
                    try:
                        log.debug(f"[{self.name}] Checking ISOs in {release_url}")
                        r2 = session.get(release_url, timeout=5)
                        if r2.status_code != 200: continue
                        
                        soup2 = BeautifulSoup(r2.text, 'lxml')
                        # Look for ISO
                        found_isos = []
                        for link in soup2.find_all('a'):
                            href = link.get('href', '')
                            if href.endswith('.iso'): found_isos.append(href)
                            
                            target_slug = "ubuntu"
                            if "beta" in href: continue 
                            
                            if self.target_flavor == "Desktop": target_slug = "ubuntu"
                            elif self.target_flavor == "Kubuntu": target_slug = "kubuntu"
                            elif self.target_flavor == "Xubuntu": target_slug = "xubuntu"
                            elif self.target_flavor == "Lubuntu": target_slug = "lubuntu"
                            elif "MATE" in self.target_flavor: target_slug = "ubuntu-mate"
                            elif "Budgie" in self.target_flavor: target_slug = "ubuntu-budgie"
                            
                            if href.endswith('.iso') and 'amd64' in href and target_slug in href:
                                 full_url = release_url + href
                                 log.info(f"[{self.name}] FOUND ISO: {full_url}")
                                 return (ver, full_url, "")
                                 
                        log.debug(f"[{self.name}] ISOs in {ver} but no match: {found_isos}")
                    except Exception as e:
                        log.warning(f"[{self.name}] Error checking {release_url}: {e}")
                        continue
            
            log.error(f"[{self.name}] Exhausted valid versions without finding ISO.")
            return (f"No ISO found in any recent version (checked {versions[:3]})", "", "")
        except Exception as e:
            log.exception(f"[{self.name}] Critical Error")
            return (f"Error: {str(e)}", "", "")
