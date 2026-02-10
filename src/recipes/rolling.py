from src.core.recipe import DistroRecipe, UpdateMechanism
from bs4 import BeautifulSoup
import re

class ArchRecipe(DistroRecipe):
    def __init__(self):
        super().__init__("Arch Linux", "Arch-based", "Rolling", "x86_64", UpdateMechanism.HtmlScraper)

    def get_download_info(self) -> tuple[str, str, str]:
        from src.core.logger import log
        # Arch: https://geo.mirror.pkgbuild.com/iso/latest/archlinux-x86_64.iso
        # Mirror list: https://archlinux.org/mirrors/status/json/
        # Robust strategy: try a few trusted mirrors
        
        mirrors = [
            "https://geo.mirror.pkgbuild.com/iso/",
            "https://mirrors.edge.kernel.org/archlinux/iso/",
            "https://mirror.rackspace.com/archlinux/iso/"
        ]
        
        session = self.get_session()
        for base_url in mirrors:
            try:
                log.debug(f"[{self.name}] Checking mirror: {base_url}")
                # We need to find the version directory.
                # geo.mirror.../iso/ usually lists dates YYYY.MM.DD/
                r = session.get(base_url, timeout=5, verify=False) # Skip SSL verify
                if r.status_code != 200: 
                    log.warning(f"[{self.name}] Mirror unreachable: {r.status_code}")
                    continue
                
                soup = BeautifulSoup(r.text, 'lxml')
                
                # Find the latest version directory (e.g., 2024.01.01/)
                version_dirs = []
                for a in soup.find_all('a'):
                    href = a.get('href', '')
                    if re.match(r'\d{4}\.\d{2}\.\d{2}/', href):
                        version_dirs.append(href.strip('/'))
                
                if not version_dirs: 
                    log.warning(f"[{self.name}] No version directories found.")
                    continue

                # Sort to get the latest version
                version_dirs.sort(key=lambda s: [int(u) for u in s.split('.')], reverse=True)
                latest_version_dir = version_dirs[0] + '/'
                log.info(f"[{self.name}] Latest version dir: {latest_version_dir}")

                # Now go into the latest version directory
                full_version_url = base_url + latest_version_dir
                r_version = session.get(full_version_url, timeout=5, verify=False)
                if r_version.status_code != 200: continue

                soup_version = BeautifulSoup(r_version.text, 'lxml')
                
                # archlinux-2024.01.01-x86_64.iso
                for a in soup_version.find_all('a'):
                    href = a.get('href', '')
                    if href.endswith('.iso') and 'x86_64' in href and 'archlinux' in href:
                        # extract version
                        m = re.search(r'archlinux-(\d+\.\d+\.\d+)-', href)
                        ver = m.group(1) if m else "Latest"
                        return (ver, full_version_url + href, "")
            except Exception as e:
                log.exception(f"[{self.name}] Error checking mirror {base_url}")
                # If any error occurs with this mirror, try the next one
                continue
        
        return ("ISO not found", "", "")

class ManjaroRecipe(DistroRecipe):
    def __init__(self, edition: str = "Plasma"):
        # Plasma, GNOME, Xfce
        name = f"Manjaro {edition}"
        super().__init__(name, "Arch-based", edition, "x86_64", UpdateMechanism.HtmlScraper)
        self.edition = edition.lower() # plasma, gnome, xfce

    def get_download_info(self) -> tuple[str, str, str]:
        from src.core.logger import log
        # Manjaro mirrors structure is tricky. 
        # https://manjaro.org/download/ is a landing page.
        # Direct trusted mirror: https://mirrors.manjaro.org/iso/
        # Structure: .../iso/{edition}/{version}/manjaro-{edition}-{version}-...iso
        
        # Manjaro: Scrape SourceForge for reliable ISOs
        # https://sourceforge.net/projects/manjarolinux/files/
        
        sf_edition = self.edition.lower()
        if sf_edition == "plasma": sf_edition = "kde"
        
        base_url = f"https://sourceforge.net/projects/manjarolinux/files/{sf_edition}/"
        log.debug(f"[{self.name}] Checking SourceForge: {base_url}")
        
        session = self.get_session()
        # SourceForge blocks standard python-requests UA sometimes
        session.headers.update({'User-Agent': 'Mozilla/5.0'})
        
        try:
            r = session.get(base_url, timeout=10)
            if r.status_code == 200:
                soup = BeautifulSoup(r.text, 'lxml')
                
                # Find version directories
                versions = []
                for a in soup.find_all('a'):
                    href = a.get('href', '')
                    title = a.get('title', '')
                    
                    # SourceForge row usually has title="26.0.2" or text="26.0.2"
                    # Link looks like /projects/manjarolinux/files/kde/26.0.2/
                    
                    if not href.startswith(f"/projects/manjarolinux/files/{sf_edition}/"): continue
                    if 'stats' in href: continue
                    
                    # Extract version part
                    parts = href.strip('/').split('/')
                    if not parts: continue
                    ver_str = parts[-1]
                    
                    # Filter for stable versions (x.y or x.y.z)
                    # Exclude rc, pre, beta
                    if any(x in ver_str.lower() for x in ['rc', 'pre', 'beta', 'test']): continue
                    
                    # Simple regex to ensure it starts with digit
                    if not re.match(r'^\d', ver_str): continue
                    
                    versions.append(ver_str)
                
                # Sort versions
                def parse_ver(v):
                    try: 
                        # specific handling for manjaro date-versions if any, but now they seem to be 26.0.2
                        return [int(x) for x in re.sub(r'[^\d.]', '', v).split('.') if x]
                    except: return [0]
                    
                versions.sort(key=parse_ver, reverse=True)
                
                if versions:
                    latest_ver = versions[0]
                    log.info(f"[{self.name}] Found latest version: {latest_ver}")
                    
                    # Now get the ISO
                    ver_url = f"{base_url}{latest_ver}/"
                    r2 = session.get(ver_url, timeout=10)
                    soup2 = BeautifulSoup(r2.text, 'lxml')
                    
                    found_iso = None
                    for a in soup2.find_all('a'):
                        href = a.get('href', '')
                        # SourceForge direct download links often end with /download
                        # But the visible text or properties might show .iso
                        
                        # Look for row that contains .iso
                        row = a.find_parent('tr')
                        if not row: continue
                        
                        # Check filename in the row
                        name_span = row.find('span', class_='name')
                        if name_span and name_span.text.endswith('.iso'):
                            fname = name_span.text
                            if "minimal" not in fname.lower():
                                found_iso = fname
                                break
                    
                    # Fallback to minimal if no full
                    if not found_iso:
                         for a in soup2.find_all('a'):
                             row = a.find_parent('tr')
                             if row:
                                 name_span = row.find('span', class_='name')
                                 if name_span and name_span.text.endswith('.iso'):
                                     found_iso = name_span.text
                                     break

                    if found_iso:
                         download_link = f"https://sourceforge.net/projects/manjarolinux/files/{sf_edition}/{latest_ver}/{found_iso}/download"
                         return (latest_ver, download_link, "")
                         
        except Exception as e:
            log.exception(f"[{self.name}] SourceForge Scraping Error: {e}")

        log.warning(f"[{self.name}] Failed to scrape SourceForge.")
        return self.safety_net()

    def safety_net(self):
        # Hardcoded fallback
        return ("24.1 (Safe Fallback)", "https://mirrors.gigenet.com/manjaro/iso/kde/24.1/manjaro-kde-24.1-minimal-241001-linux66.iso", "")
            


class EndeavourRecipe(DistroRecipe):
    def __init__(self):
        super().__init__("EndeavourOS", "Arch-based", "Rolling", "x86_64", UpdateMechanism.HtmlScraper)

    def get_download_info(self) -> tuple[str, str, str]:
        from src.core.logger import log
        # Edge kernel mirror is inconsistent. Use Alpix or reliable mirror.
        base_url = "https://mirror.alpix.eu/endeavouros/iso/"
        session = self.get_session()
        try:
            log.debug(f"[{self.name}] Checking {base_url}")
            r = session.get(base_url, timeout=10)
            r.raise_for_status()
            soup = BeautifulSoup(r.text, 'lxml')
            
            isos = []
            for a in soup.find_all('a'):
                href = a.get('href', '')
                if href.endswith(".iso") and "EndeavourOS" in href:
                    isos.append(href)
            
            if not isos: 
                log.warning(f"[{self.name}] No ISOs found.")
                return ("No ISOs found", "", "")
            
            # Sort by name (usually contains date)
            isos.sort(reverse=True)
            latest = isos[0]
            log.info(f"[{self.name}] Found ISO: {latest}")
            
            # EndeavourOS_Galileo-2023.11.17.iso or similar
            # Extract date/version
            # Match YYYY.MM.DD
            m = re.search(r'(\d{4}\.\d{2}\.\d{2})', latest)
            ver = m.group(1) if m else "Latest"
            
            return (ver, base_url + latest, "")
            
        except Exception as e:
            log.exception(f"[{self.name}] Error")
            # Fallback
            pass
            
        return self.safety_net()

    def safety_net(self):
        # Hardcoded fallback to a reliable mirror file (e.g. generic KDE)
        # 23.0.1 is a reasonable fallback
        return ("2023.05.28 (Safe Fallback)", "https://mirrors.gigenet.com/endeavouros/iso/EndeavourOS_Cassini_Nova-03-2023_R1.iso", "")
