from src.core.recipe import DistroRecipe, UpdateMechanism
from bs4 import BeautifulSoup
import re
from src.core.logger import log

class PuppyRecipe(DistroRecipe):
    def __init__(self, variant: str = "BookwormPup64"):
        name = f"Puppy Linux {variant}"
        super().__init__(name, "Puppy", variant, "x86_64", UpdateMechanism.GithubRelease)
        self.variant = variant

    def get_download_info(self) -> tuple[str, str, str]:
        # Puppy Linux: decentralized. We check mirrors for "puppy-{variant}" folders.
        target = self.variant.lower()
        candidates = []
        if "fossa" in target:
            candidates = ["puppy-fossa", "fossapup"]
        elif "bookworm" in target:
            candidates = ["puppy-bookwormpup", "bookwormpup"]
        else:
            candidates = [f"puppy-{target}"]
            
        mirrors = [
            "https://distro.ibiblio.org/puppylinux/",
            "https://ftp.nluug.nl/os/Linux/distr/puppylinux/",
            "https://mirror.aarnet.edu.au/pub/puppylinux/"
        ]
        
        session = self.get_session()
        
        for base_url in mirrors:
            log.info(f"[{self.name}] Checking mirror: {base_url}")
            try:
                r = session.get(base_url, timeout=10)
                if r.status_code != 200: continue
                
                soup = BeautifulSoup(r.text, 'lxml')
                found_dir = None
                
                # Exclusion list
                exclusions = ["pet_packages", "drivers", "firmware", "headers", "help", "huge", "kernels", "packages", "pupget", "devx", "doc", "nls"]
                
                for a in soup.find_all('a'):
                    href = a.get('href', '').strip('/')
                    href_lower = href.lower()
                    if href.startswith('http') or href.startswith('ftp'): continue
                    
                    if any(ex in href_lower for ex in exclusions): continue
                    
                    for c in candidates:
                        if c in href_lower:
                            found_dir = href
                            log.debug(f"[{self.name}] Matched directory: {found_dir}")
                            break
                    if found_dir: break
                
                if found_dir:
                    ver_url = base_url + found_dir
                    if not ver_url.endswith('/'): ver_url += '/'
                    
                    log.debug(f"[{self.name}] Found subdir: {ver_url}")
                    
                    try:
                        r2 = session.get(ver_url, timeout=10)
                        s2 = BeautifulSoup(r2.text, 'lxml')
                        
                        iso_candidates = [] # (version_float, version_str, url)

                        def parse_puppy_ver(filename):
                            # e.g. BookwormPup64_10.0.6.iso -> 10.0.6
                            # fossapup64-9.5.iso -> 9.5
                            m = re.search(r'[\-_]([\d\.]+)(?:[\-_]|\.iso)', filename)
                            if m:
                                try:
                                    v_str = m.group(1).strip('.')
                                    # Handle . at end
                                    parts = v_str.split('.')
                                    # simplistic float: 10.0.6 -> 10006 ? No, just float(10.0) first
                                    # Let's use tuple comparison
                                    return [int(p) for p in parts if p.isdigit()]
                                except: pass
                            return [0]

                        # Helper to check a dir for ISOs
                        def check_dir_for_isos(d_url):
                            try:
                                rd = session.get(d_url, timeout=10)
                                sd = BeautifulSoup(rd.text, 'lxml')
                                for ad in sd.find_all('a'):
                                    hd = ad.get('href', '')
                                    if hd.endswith('.iso'):
                                        full_iso = d_url + hd
                                        # Parse version
                                        v_tuple = parse_puppy_ver(hd)
                                        v_str = ".".join(map(str, v_tuple))
                                        iso_candidates.append((v_tuple, v_str, full_iso))
                            except: pass

                        # Check Level 0
                        check_dir_for_isos(ver_url)
                        
                        # Recurse Level 1
                        l1_dirs = []
                        for a in s2.find_all('a'):
                            href = a.get('href', '').strip('/')
                            if href.startswith('?') or href.startswith('/') or href.startswith('http'): continue
                            if href.lower() in ["parent directory", "..", "."]: continue
                            if '/' in href or not '.' in href:
                                 l1_url = ver_url + href
                                 if not l1_url.endswith('/'): l1_url += '/'
                                 l1_dirs.append(l1_url)
                        
                        for l1_url in l1_dirs:
                             # Check Level 1
                             check_dir_for_isos(l1_url)

                             # Recurse Level 2 (for Version dirs like 10.0.12/)
                             try:
                                 r3 = session.get(l1_url, timeout=10)
                                 s3 = BeautifulSoup(r3.text, 'lxml')
                                 for a3 in s3.find_all('a'):
                                     href3 = a3.get('href', '').strip('/')
                                     if href3.startswith('?') or href3.startswith('/') or href3.startswith('http'): continue
                                     if href3.lower() in ["parent directory", "..", "."]: continue
                                     
                                     # Heuristic: looks like version string? 
                                     # starts with digit
                                     if href3[0].isdigit():
                                          l2_url = l1_url + href3
                                          if not l2_url.endswith('/'): l2_url += '/'
                                          check_dir_for_isos(l2_url)
                             except: pass

                        if iso_candidates:
                             # Sort by version tuple descending
                             iso_candidates.sort(key=lambda x: x[0], reverse=True)
                             best = iso_candidates[0]
                             return (best[1], best[2], "")
                            
                    except Exception as e:
                        log.warning(f"[{self.name}] Error scraping subdir {ver_url}: {e}")
                
            except Exception as e:
                log.warning(f"[{self.name}] Error checking mirror {base_url}: {e}")
                continue
                
        log.warning(f"[{self.name}] All mirrors failed. Calling Safety Net.")
        return self.safety_net()
        
    def safety_net(self):
        # https://distro.ibiblio.org/puppylinux/puppylinux-fossa/puppylinux-9.5-fossa64/FossaPup64-9.5.iso
        if "fossa" in self.flavor.lower():
             return ("9.5 (Fallback)", "https://distro.ibiblio.org/puppylinux/puppylinux-fossa/puppylinux-9.5-fossa64/FossaPup64-9.5.iso", "")
        # Bookworm: https://distro.ibiblio.org/puppylinux/puppylinux-bookworm/BookwormPup64_10.0.6.iso
        return ("10.0.6 (Fallback)", "https://distro.ibiblio.org/puppylinux/puppylinux-bookworm/BookwormPup64_10.0.6.iso", "")

class TinyCoreRecipe(DistroRecipe):
    def __init__(self, variant: str = "CorePlus"):
        name = f"TinyCore {variant}"
        super().__init__(name, "Independent", variant, "x86", UpdateMechanism.HtmlScraper)
        self.variant = variant # Core, TinyCore, CorePlus

    def get_download_info(self) -> tuple[str, str, str]:
        base_url = "http://tinycorelinux.net/15.x/x86/release/"
        session = self.get_session()
        try:
            log.debug(f"[{self.name}] Checking {base_url}")
            r = session.get(base_url, timeout=10)
            r.raise_for_status()
            soup = BeautifulSoup(r.text, 'lxml')
            
            match_str = f"{self.variant}-current.iso"
            
            for a in soup.find_all('a'):
                href = a.get('href', '')
                if "CorePlus" in href and href.endswith('.iso'):
                    # /15.x/x86/release/CorePlus-15.0.iso
                    if not href.startswith('http'): href = base_url + href
                    
                    # Extract version
                    m = re.search(r'CorePlus-([\d\.]+)\.iso', href)
                    ver = m.group(1) if m else "Current"
                    return (ver, href, "")
            
            return ("ISO link not found", "", "")
        except Exception as e:
            return (f"Error: {e}", "", "")
