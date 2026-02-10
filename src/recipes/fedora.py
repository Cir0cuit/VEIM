from src.core.recipe import DistroRecipe, UpdateMechanism

class FedoraRecipe(DistroRecipe):
    def __init__(self, variant: str = "Workstation"):
        # Variant map: "Workstation", "KDE", "Cinnamon", "Xfce", "Budgie"
        name = f"Fedora {variant}"
        super().__init__(name, "RPM-based", variant, "x86_64", UpdateMechanism.FedoraAPI)
        self.variant = variant

    def get_download_info(self) -> tuple[str, str, str]:
        from src.core.logger import log
        url = "https://fedoraproject.org/releases.json"
        session = self.get_session()
        try:
            response = session.get(url, timeout=30)
            response.raise_for_status()
            data = response.json()
            log.debug(f"[{self.name}] JSON fetched. {len(data)} entries.")
        except Exception as e:
            log.exception(f"[{self.name}] API Error")
            return (f"API Error: {e}", "", "")

        candidates = []
        for entry in data:
            # Arch check
            if entry.get('arch', '') != 'x86_64': continue
            
            # Robust Stability Check
            stable_raw = entry.get('stable', False)
            is_stable = str(stable_raw).lower() == 'true' if isinstance(stable_raw, str) else bool(stable_raw)
            
            # Version String
            ver = str(entry.get('version', '0'))
            
            # Variant Matching
            variant_entry = entry.get('variant', '').lower()
            target_variant = self.variant.lower()
            
            # Match Logic
            match = False
            if target_variant == "workstation" and "workstation" in variant_entry: match = True
            elif "kde" in target_variant and "kde" in variant_entry: match = True
            elif "cinnamon" in target_variant and "cinnamon" in variant_entry: match = True
            elif "xfce" in target_variant and "xfce" in variant_entry: match = True
            elif "budgie" in target_variant and "budgie" in variant_entry: match = True
            elif "server" in target_variant and "server" in variant_entry: match = True
            
            if match:
                 # If stable, high priority. If not stable (but not explicitly beta/rawhide in version), lower priority.
                 # We'll just collect them and sort later.
                 priority = 2 if is_stable else 1
                 if 'beta' in ver.lower() or 'rawhide' in ver.lower(): priority = 0
                 
                 candidates.append((ver, entry, priority))

        # Sort candidates by Priority desc, then Version desc
        def parse_ver(v):
            try: return float(v)
            except: return 0.0
        
        candidates.sort(key=lambda x: (x[2], parse_ver(x[0])), reverse=True)

        # Filter out priority 0 unless that's all we have? No, safe to skip beta/rawhide.
        candidates = [c for c in candidates if c[2] > 0]

        if not candidates:
             log.warning(f"[{self.name}] No primary match in JSON.")
             # Fallback: try to find any Workstation entry if specific variant failed
             if self.variant != "Workstation":
                 log.info(f"[{self.name}] Retrying with Workstation as generic fallback source...")
                 for entry in data:
                     if entry.get('arch', '') == 'x86_64' and entry.get('variant', '') == 'Workstation':
                         candidates.append((str(entry.get('version', '0')), entry, 1))
                 candidates.sort(key=lambda x: (x[2], parse_ver(x[0])), reverse=True)

        if not candidates:
            return self.safety_net()
            
        best_ver, best_entry, _ = candidates[0]
        log.info(f"[{self.name}] Selected Version: {best_ver}")
        
        # Construct Download URL
        # Structure often: https://download.fedoraproject.org/pub/fedora/linux/releases/{ver}/Workstation/x86_64/iso/
        # Or .../Spins/x86_64/iso/
        
        base_url = f"https://download.fedoraproject.org/pub/fedora/linux/releases/{best_ver}"
        
        # Determine paths to check
        paths = []
        if self.variant == "Workstation":
            paths.append(f"{base_url}/Workstation/x86_64/iso/")
        else:
            paths.append(f"{base_url}/Spins/x86_64/iso/")
            # Fallback path if Spin structure changes
            paths.append(f"{base_url}/Workstation/x86_64/iso/") 

        for iso_dir in paths:
            try:
                log.debug(f"[{self.name}] Checking ISO dir: {iso_dir}")
                r = session.get(iso_dir, timeout=30)
                if r.status_code != 200: continue
                
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(r.text, 'lxml')
                
                # Keywords to match
                keywords = [self.variant.lower(), "live", "x86_64", ".iso"]
                # Adjust keywords for specific variants
                if "kde" in self.variant.lower(): keywords = ["kde", "live", "x86_64", ".iso"]
                
                for a in soup.find_all('a'):
                    href = a.get('href', '')
                    if not href.endswith('.iso'): continue
                    
                    href_lower = href.lower()
                    if all(k in href_lower for k in keywords):
                        # Verify it's not a CHECKSUM file misread or something
                        full_url = iso_dir + href
                        return (best_ver, full_url, "")
                        
                    # Relaxed fallback: if "Workstation" failed, just grab first "Fedora-Workstation" ISO
                    if self.variant == "Workstation" and "workstation" in href_lower and "live" in href_lower:
                         return (best_ver, iso_dir + href, "")

            except Exception as e:
                log.warning(f"[{self.name}] Error checking {iso_dir}: {e}")
                continue
                
        log.warning(f"[{self.name}] ISO not found in directories.")
        return self.safety_net()

    def safety_net(self):
         # Valid Fedora 41 link
         return ("41 (Safe Fallback)", "https://download.fedoraproject.org/pub/fedora/linux/releases/41/Workstation/x86_64/iso/Fedora-Workstation-Live-x86_64-41-1.4.iso", "")

