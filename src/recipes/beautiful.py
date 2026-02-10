from src.core.recipe import DistroRecipe, UpdateMechanism
from bs4 import BeautifulSoup
import requests
import re
from src.core.logger import log

class ZorinRecipe(DistroRecipe):
    def __init__(self, edition: str = "Core"):
        # Editions: Core, Lite
        name = f"Zorin OS {edition}"
        super().__init__(name, "Debian-based", edition, "x86_64", UpdateMechanism.HtmlScraper)


    def get_download_info(self) -> tuple[str, str, str]:
        # Zorin OS - Main site triggers captcha or complex JS.
        # Use SourceForge RSS or Directory scraping.
        # RSS: https://sourceforge.net/projects/zorin-os/rss
        
        rss_url = "https://sourceforge.net/projects/zorin-os/rss"
        session = self.get_session()
        try:
            log.debug(f"[{self.name}] Fetching RSS: {rss_url}")
            r = session.get(rss_url, timeout=10)
            r.raise_for_status()
            
            # Simple limit parse
            from lxml import etree
            root = etree.fromstring(r.content)
            
            # Items are usually releases
            # We look for title/link containing "Core" or "Lite" and ".iso"
            # namespaces = {'media': 'http://search.yahoo.com/mrss/'} # Not used in the provided snippet
            
            # match_str = f"Zorin-OS" # Not used in the provided snippet
            flavor_str = self.flavor # Core or Lite
            
            matches = []
            for item in root.xpath('//channel/item'):
                link_node = item.find('link')
                title_node = item.find('title')
                
                link_text = link_node.text if link_node is not None else None
                title_text = title_node.text if title_node is not None else None
                
                if not link_text or not title_text: continue
                if ".iso" in link_text and flavor_str in link_text:
                     # version extraction
                     m = re.search(r'Zorin-OS-(\d+(\.\d+)?)', title_text)
                     if m: 
                         v_str = m.group(1)
                         try:
                             v_num = float(v_str)
                             matches.append((v_num, v_str, link_text))
                         except:
                             pass
            
            if matches:
                matches.sort(key=lambda x: x[0], reverse=True)
                best = matches[0]
                log.info(f"[{self.name}] Best RSS match: {best[1]}")
                return (best[1], best[2], "")

            log.warning(f"[{self.name}] No RSS match found.")
            return ("Download link not found in RSS", "", "")
            
        except Exception as e:
            log.exception(f"[{self.name}] Error")
            return (f"Error: {e}", "", "")

class KDENeonRecipe(DistroRecipe):
    def __init__(self):
        super().__init__("KDE Neon", "Ubuntu-based", "User", "x86_64", UpdateMechanism.HtmlScraper)

    def get_download_info(self) -> tuple[str, str, str]:
        base_url = "https://files.kde.org/neon/images/user/current/"
        session = self.get_session()
        try:
            log.debug(f"[{self.name}] Checking {base_url}")
            r = session.get(base_url, timeout=10)
            r.raise_for_status()
            soup = BeautifulSoup(r.text, 'lxml')
            
            # neon-user-20250109-0716.iso
            for a in soup.find_all('a'):
                href = a.get('href', '')
                if href.endswith(".iso") and "neon-user" in href:
                     # extract date
                     m = re.search(r'neon-user-(\d+)-', href)
                     ver = m.group(1) if m else "Current"
                     log.info(f"[{self.name}] Found ISO: {ver} -> {base_url + href}")
                     return (ver, base_url + href, "")
            
            log.warning(f"[{self.name}] ISO not found.")
            return ("ISO not found", "", "")
        except Exception as e:
            log.exception("KDE Neon Error")
            return (f"Error: {e}", "", "")

class PopOSRecipe(DistroRecipe):
    def __init__(self, variant: str = "Standard"):
        name = f"Pop!_OS {variant}"
        super().__init__(name, "Ubuntu-based", variant, "x86_64", UpdateMechanism.PopOSAPI)
        self.variant = variant # Standard or NVIDIA

    def get_download_info(self) -> tuple[str, str, str]:
        from src.core.logger import log
        # API is unreliable. Mirror is 403 Forbidden for directory listing.
        # But we can guess the URL if we know the build number.
        # Format: https://iso.pop-os.org/{ver}/amd64/{type}/{build}/pop-os_{ver}_amd64_{type}_{build}.iso
        
        v_type = "nvidia" if self.variant == "NVIDIA" else "intel"
        # Try finding 22.04 builds (LTS) as it is most reliable.
        
        session = self.get_session()
        target_vers = ["22.04"]

        for ver in target_vers:
            base_url = f"https://iso.pop-os.org/{ver}/amd64/{v_type}"
            log.info(f"[{self.name}] Probing {ver} builds...")
            
            # Start from a reasonable upper bound for build numbers. 
            # 22.04 is around build 30-40.
            for build in range(40, 5, -1):
                # HEAD request to check existence
                iso_name = f"pop-os_{ver}_amd64_{v_type}_{build}.iso"
                url = f"{base_url}/{build}/{iso_name}"
                
                try:
                    r = session.head(url, timeout=2)
                    if r.status_code == 200:
                        log.info(f"[{self.name}] Found valid build: {build}")
                        return (f"{ver} (Build {build})", url, "")
                except:
                    continue
                    
        log.warning(f"[{self.name}] Probing failed. Using Hardcoded Fallback.")
        fallback_ver = "22.04 LTS (Fallback)"
        fallback_url = "https://iso.pop-os.org/22.04/amd64/intel/37/pop-os_22.04_amd64_intel_37.iso"
        if "nvidia" in v_type:
            fallback_url = "https://iso.pop-os.org/22.04/amd64/nvidia/37/pop-os_22.04_amd64_nvidia_37.iso"
            
        return (fallback_ver, fallback_url, "")

    def old_logic_ignored(self):
        pass
