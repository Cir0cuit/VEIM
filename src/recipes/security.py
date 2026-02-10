from src.core.recipe import DistroRecipe, UpdateMechanism
from bs4 import BeautifulSoup
import re

class KaliRecipe(DistroRecipe):
    def __init__(self, variant: str = "Live"):
        # Variants: "Live" (Standard/Everything), "KDE", "Xfce"
        # Since Kali 2020, they have one "Installer" and one "Live" usually, or separated DEs.
        # User request: "Everything: kali-linux-everything-live-amd64.iso", "KDE", "Xfce"
        name = f"Kali {variant}"
        super().__init__(name, "Debian-based", variant, "x86_64", UpdateMechanism.DebianDirectory)
        self.variant_key = variant.lower()

    def get_download_info(self) -> tuple[str, str, str]:
        # Kali 'current' is a good pointer
        base_url = "https://cdimage.kali.org/current/"
        session = self.get_session()
        
        try:
            r = session.get(base_url, timeout=10)
            r.raise_for_status()
            soup = BeautifulSoup(r.text, 'lxml')
            
            # Find ISOs
            # Expect: kali-linux-2024.1-live-amd64.iso
            # OR kali-linux-2024.1-live-kde-amd64.iso
            
            # Map user variant to filename part
            if self.variant_key == "live" or self.variant_key == "everything":
                # Fallback to "installer" if live is missing, OR "live"
                # Actually, main page usually has "installer-amd64.iso" and "live-amd64.iso"
                # Let's try finding the loose match "amd64.iso"
                search_term = "amd64.iso"
            elif self.variant_key == "kde":
                search_term = "kde-amd64.iso" # relax match
            elif self.variant_key == "xfce":
                search_term = "xfce-amd64.iso" # relax match
            else:
                search_term = "amd64.iso" 

            # Special logic: prefer "live" if available, else take "installer"
            candidates = []
            for link in soup.find_all('a'):
                href = link.get('href', '')
                if href.endswith('.iso') and search_term in href:
                    candidates.append(href)
            
            # Filter for 'live' if possible
            live_candidates = [c for c in candidates if "live" in c]
            final_href = live_candidates[0] if live_candidates else (candidates[0] if candidates else None)
            
            if final_href:
                # Extract version
                m = re.search(r'kali-linux-([\d\.]+)-', final_href)
                ver = m.group(1) if m else "Rolling"
                return (ver, base_url + final_href, "")
                
            log.warning(f"[{self.name}] ISO not found. Calling Safety Net.")
            return self.safety_net()


        except Exception as e:
            pass
            
        return self.safety_net()

    def safety_net(self):
        # 2024.4
        base = "https://cdimage.kali.org/kali-2024.4/"
        v = "2024.4 (Fallback)"
        
        if self.variant_key == "kde":
             return (v, f"{base}kali-linux-2024.4-live-kde-amd64.iso", "")
        elif self.variant_key == "xfce":
             return (v, f"{base}kali-linux-2024.4-live-xfce-amd64.iso", "")
        
        return (v, f"{base}kali-linux-2024.4-live-amd64.iso", "")

class ParrotRecipe(DistroRecipe):
    def __init__(self, edition: str = "Security"):
        # Editions: Security, Home
        name = f"Parrot {edition}"
        super().__init__(name, "Debian-based", edition, "x86_64", UpdateMechanism.HtmlScraper)
        self.edition = edition

    def get_download_info(self) -> tuple[str, str, str]:
        # Parrot structure often changes.
        # Try scraping download page or a known mirror.
        # https://deb.parrot.sh/parrot/iso/ is a good index.
        
        base_url = "https://deb.parrot.sh/parrot/iso/"
        session = self.get_session()
        
        try:
            r = session.get(base_url, timeout=10)
            r.raise_for_status()
            soup = BeautifulSoup(r.text, 'lxml')
            
            # Find latest version directory (e.g. 6.0, 6.1)
            versions = []
            for link in soup.find_all('a'):
                href = link.get('href', '').strip('/')
                if href and href[0].isdigit() and 'current' not in href:
                    versions.append(href)
            
            # Also check 'current' but version number is better
            if not versions:
                # fallback to 'current' logic?
                pass
                
            versions.sort(key=lambda s: [int(u) for u in s.split('.') if u.isdigit()], reverse=True)
            
            latest_v = versions[0] if versions else "current"
            
            target_dir = f"{base_url}{latest_v}/"
            r2 = session.get(target_dir, timeout=10)
            soup2 = BeautifulSoup(r2.text, 'lxml')
            
            # Filename: Parrot-security-6.0_amd64.iso or Parrot-home-6.0_amd64.iso
            key = self.edition.lower() # security or home
            
            for link in soup2.find_all('a'):
                href = link.get('href', '')
                if href.endswith('.iso') and key in href.lower() and 'amd64' in href:
                    return (latest_v, target_dir + href, "")
            
            return (f"ISO not found for {self.edition}", "", "")
            
        except Exception as e:
            return (f"Error: {e}", "", "")
