from src.core.recipe import DistroRecipe, UpdateMechanism
from bs4 import BeautifulSoup

class MintRecipe(DistroRecipe):
    def __init__(self, edition: str = "Cinnamon"):
        # Editions: Cinnamon, MATE, Xfce
        name = f"Linux Mint {edition}"
        super().__init__(name, "Debian-based", edition, "x86_64", UpdateMechanism.HtmlScraper)
        self.edition_key = edition.lower() # cinnamon, mate, xfce

    def get_download_info(self) -> tuple[str, str, str]:
        url = "https://www.linuxmint.com/download_all.php"
        session = self.get_session()
        
        try:
            r = session.get(url, timeout=10)
            r.raise_for_status()
            soup = BeautifulSoup(r.text, 'lxml')
            
            # The table contains links to specific editions.
            # We want the highest version number.
            # Logic: Look for links like "release.php?id=..." or text "Linux Mint 22"
            
            # Quick hack: find all "Linux Mint X.Y" strings, pick max.
            # Table usually has <td>Linux Mint 22</td>
            
            versions = []
            for cell in soup.find_all('td'):
                txt = cell.get_text().strip()
                # Check for "Linux Mint 22" OR just "22.1"
                # Logic: if it looks like a version X.Y, add it.
                # Avoid dates like 2024.
                if txt.lower().startswith("linux mint"):
                    try:
                        v = txt.split("Linux Mint")[-1].strip()
                        if v and v[0].isdigit(): versions.append(v)
                    except: pass
                elif txt.replace('.', '').isdigit() and len(txt) < 10 and '.' in txt:
                    # heuristic for "22.1"
                     versions.append(txt)

            if not versions:
                 # Last ditch: look for links to "version-22"
                 pass
            
            if not versions:
                return ("Error parsing Mint versions", "", "")
                
            # Sort semantic versions
            # handle '21.3' vs '22'
            def parse_ver(v):
                return [int(x) for x in v.split('.')]
                
            versions.sort(key=parse_ver, reverse=True)
            latest_ver = versions[0]
            
            # Construct URL
            # Standard mirror: https://mirrors.edge.kernel.org/linuxmint/stable/{ver}/linuxmint-{ver}-{edition}-64bit.iso
            # edition is cinnamon, mate, xfce
            
            filename = f"linuxmint-{latest_ver}-{self.edition_key}-64bit.iso"
            download_url = f"https://mirrors.edge.kernel.org/linuxmint/stable/{latest_ver}/{filename}"
            
            # We can verify it exists with a HEAD request
            try:
                head = session.head(download_url, timeout=5)
                if head.status_code >= 400:
                    # Fallback to older scheme or different mirror?
                    # Most mint mirrors follow this structure.
                    return (latest_ver, f"Check failed: {download_url}", "")
            except:
                pass

            return (latest_ver, download_url, "")

        except Exception as e:
            return (f"Error: {e}", "", "")
