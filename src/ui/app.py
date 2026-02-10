import customtkinter as ctk
import os
import threading
import tkinter.filedialog
from src.core.manager import RecipeManager
from src.recipes.fedora import FedoraRecipe
from src.recipes.ubuntu import UbuntuRecipe
from src.recipes.mint import MintRecipe
from src.recipes.security import KaliRecipe, ParrotRecipe
from src.recipes.security import KaliRecipe, ParrotRecipe
from src.recipes.beautiful import ZorinRecipe, KDENeonRecipe, PopOSRecipe
from src.recipes.rolling import ArchRecipe, ManjaroRecipe, EndeavourRecipe
from src.recipes.lightweight import PuppyRecipe, TinyCoreRecipe
from src.ventoy.config import VentoyConfigurator

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class DistroRow:
    def __init__(self, master, index, recipe, app):
        self.app = app
        self.recipe = recipe
        # self.callback = download_callback # Removed, using app directly
        
        # Frame with fixed height and no internal grid expansion acting weird
        self.frame = ctk.CTkFrame(master)
        self.frame.grid(row=index, column=0, sticky="ew", padx=10, pady=2)
        
        # Grid layout with weight only on Name maybe? 
        # Actually to align perfectly, we need fixed widths or precise weights.
        # Let's use fixed width for table-like look.
        
        # Cols: 0=Name, 1=Local, 2=Online, 3=Status, 4=Action
        self.frame.grid_columnconfigure(0, weight=1) # Name expands
        
        self.lbl_name = ctk.CTkLabel(self.frame, text=recipe.name, anchor="w", fg_color="transparent")
        self.lbl_name.grid(row=0, column=0, sticky="ew", padx=(10, 5), pady=5)
        
        self.lbl_local = ctk.CTkLabel(self.frame, text="--", width=120, anchor="center")
        self.lbl_local.grid(row=0, column=1, padx=5)
        
        self.lbl_online = ctk.CTkLabel(self.frame, text="...", width=120, anchor="center")
        self.lbl_online.grid(row=0, column=2, padx=5)

        self.lbl_status = ctk.CTkLabel(self.frame, text="Idle", width=150, anchor="center", text_color="gray")
        self.lbl_status.grid(row=0, column=3, padx=5)
        
        self.btn_action = ctk.CTkButton(self.frame, text="Check", width=90, command=self.on_check)
        self.btn_action.grid(row=0, column=4, padx=(5, 10))

    def on_check(self):
        self.lbl_status.configure(text="Checking...", text_color="yellow")
        self.app.check_single(self)

    def on_download(self):
        # Trigger download
        # For now, just print or show status
        self.lbl_status.configure(text="Downloading...", text_color="cyan")
        # In a real impl, we'd pass this to a download manager
        # self.download_callback(self.recipe) 
        # But we need to implement that in App.
        # For now we reuse callback or add a new one? 
        # Let's assume VOMApp handles it in a specialized method, but we need to pass a ref.
        # Let's cheat and make the button call a method on master (VOMApp) if possible, or pass a second callback.
        # For simplicity, I'll just change the button command in update_ui to a lambda calling master.start_download.
        # For simplicity, I'll just change the button command in update_ui to a lambda calling master.start_download.
        self.detected_version = "Unknown"
        pass

    def update_ui(self, online_ver, status_msg, status_color="white", download_url=None):
        # Truncate version if too long
        display_ver = online_ver
        if len(display_ver) > 15: display_ver = display_ver[:12] + "..."
        
        self.lbl_online.configure(text=display_ver)
        self.lbl_status.configure(text=status_msg, text_color=status_color)
        
        if download_url and "http" in download_url:
            self.detected_version = online_ver # Store full version string
            self.btn_action.configure(text="Download", fg_color="blue", command=lambda: self.app.start_download(self.recipe, download_url, self.detected_version))
        else:
            self.btn_action.configure(text="Check", fg_color="#1f538d", command=self.on_check)

class VOMApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Ventoy Easy Iso Manager (VEIM)")
        self.geometry("1100x800")
        
        self.ventoy_path = ""
        self.manager = RecipeManager()
        self.init_recipes()
        self.rows = []

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Sidebar
        self.sidebar = ctk.CTkFrame(self, width=220, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_rowconfigure(4, weight=1)
        
        self.lbl_logo = ctk.CTkLabel(self.sidebar, text="VEIM", font=ctk.CTkFont(size=22, weight="bold"))
        self.lbl_logo.grid(row=0, column=0, padx=20, pady=(30, 20))
        
        self.btn_path = ctk.CTkButton(self.sidebar, text="Select Ventoy Drive", command=self.select_drive)
        self.btn_path.grid(row=1, column=0, padx=20, pady=10)
        
        self.lbl_path = ctk.CTkLabel(self.sidebar, text="No drive selected", text_color="gray", wraplength=180)
        self.lbl_path.grid(row=2, column=0, padx=20, pady=10)

        # Main Area
        self.main_frame = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.main_frame.grid(row=0, column=1, sticky="nsew")
        self.main_frame.grid_rowconfigure(2, weight=1) # Row 2 is scroll frame
        self.main_frame.grid_columnconfigure(0, weight=1)
        
        # Header Row (To match DistroRow)
        self.header_frame = ctk.CTkFrame(self.main_frame, height=40, fg_color="transparent")
        self.header_frame.grid(row=0, column=0, sticky="ew", padx=20, pady=(10, 0))
        self.header_frame.grid_columnconfigure(0, weight=1)
        
        # Matching columns to DistroRow
        ctk.CTkLabel(self.header_frame, text="Distro Name", anchor="w", font=("Arial", 12, "bold")).grid(row=0, column=0, sticky="w", padx=20)
        ctk.CTkLabel(self.header_frame, text="Local Ver", width=120, anchor="center", font=("Arial", 12, "bold")).grid(row=0, column=1, padx=5)
        ctk.CTkLabel(self.header_frame, text="Online Ver", width=120, anchor="center", font=("Arial", 12, "bold")).grid(row=0, column=2, padx=5)
        ctk.CTkLabel(self.header_frame, text="Status", width=150, anchor="center", font=("Arial", 12, "bold")).grid(row=0, column=3, padx=5)
        ctk.CTkLabel(self.header_frame, text="Action", width=90, anchor="center", font=("Arial", 12, "bold")).grid(row=0, column=4, padx=(5, 30)) # extra padding for scrollbar
        
        # Separator
        ctk.CTkFrame(self.main_frame, height=2, fg_color="gray").grid(row=1, column=0, sticky="ew", padx=20, pady=(5, 5))
        
        # Scrollable List
        self.scroll_frame = ctk.CTkScrollableFrame(self.main_frame, label_text="")
        self.scroll_frame.grid(row=2, column=0, sticky="nsew", padx=20, pady=(0, 20))
        self.scroll_frame.grid_columnconfigure(0, weight=1)
        
        # Footer
        self.footer = ctk.CTkFrame(self.main_frame, height=60, fg_color="transparent")
        self.footer.grid(row=3, column=0, sticky="ew", padx=20, pady=10)
        
        self.btn_update_all = ctk.CTkButton(self.footer, text="Update All Catalogs", font=ctk.CTkFont(size=14), command=self.update_all, fg_color="green")
        self.btn_update_all.pack(side="right", padx=20, pady=10)
        
        self.progress = ctk.CTkProgressBar(self.footer)
        self.progress.pack(side="left", padx=20, fill="x", expand=True)
        self.progress.set(0)

        self.populate_rows()

    def init_recipes(self):
        # Family A: The Big Three & Flavors
        self.manager.register_recipe(FedoraRecipe("Workstation"))
        self.manager.register_recipe(FedoraRecipe("KDE Plasma"))
        self.manager.register_recipe(FedoraRecipe("Cinnamon"))
        self.manager.register_recipe(FedoraRecipe("Xfce"))
        self.manager.register_recipe(FedoraRecipe("Budgie"))
        
        self.manager.register_recipe(UbuntuRecipe("Desktop"))
        self.manager.register_recipe(UbuntuRecipe("Kubuntu"))
        self.manager.register_recipe(UbuntuRecipe("Xubuntu"))
        self.manager.register_recipe(UbuntuRecipe("Lubuntu"))
        self.manager.register_recipe(UbuntuRecipe("Ubuntu MATE"))
        self.manager.register_recipe(UbuntuRecipe("Ubuntu Budgie"))
        
        self.manager.register_recipe(MintRecipe("Cinnamon"))
        self.manager.register_recipe(MintRecipe("MATE"))
        self.manager.register_recipe(MintRecipe("Xfce"))

        # Family B: Security
        self.manager.register_recipe(KaliRecipe("Live")) # Everything
        self.manager.register_recipe(ParrotRecipe("Security"))
        self.manager.register_recipe(ParrotRecipe("Home"))

        # Family C: Beautiful
        self.manager.register_recipe(ZorinRecipe("Core"))
        self.manager.register_recipe(ZorinRecipe("Lite"))
        self.manager.register_recipe(KDENeonRecipe())
        self.manager.register_recipe(PopOSRecipe("Standard"))
        self.manager.register_recipe(PopOSRecipe("NVIDIA"))

        # Family D: Rolling
        self.manager.register_recipe(ArchRecipe())
        self.manager.register_recipe(ManjaroRecipe("Plasma"))
        self.manager.register_recipe(ManjaroRecipe("GNOME"))
        self.manager.register_recipe(ManjaroRecipe("Xfce"))
        self.manager.register_recipe(EndeavourRecipe())

        # Family E: Lightweight
        self.manager.register_recipe(PuppyRecipe("BookwormPup64"))
        self.manager.register_recipe(PuppyRecipe("FossaPup64"))
        self.manager.register_recipe(TinyCoreRecipe("CorePlus"))
        self.manager.register_recipe(TinyCoreRecipe("TinyCore"))

        # Family F: Windows - REMOVED per user request
        # self.manager.register_recipe(Windows11Recipe())

    def populate_rows(self):
        recipes = self.manager.get_all_recipes()
        for i, r in enumerate(recipes):
            row = DistroRow(self.scroll_frame, i, r, self)
            self.rows.append(row)

    def select_drive(self):
        path = tkinter.filedialog.askdirectory()
        if path:
            self.ventoy_path = path
            self.lbl_path.configure(text=path)
            # Create Managed folder
            os.makedirs(os.path.join(path, "Managed_ISOs"), exist_ok=True)
            
            # Init Inventory
            from src.core.inventory import InventoryManager
            self.inventory = InventoryManager(path)
            
            # Refresh local versions
            for row in self.rows:
                local = self.inventory.get_installed_version(row.recipe.name)
                row.lbl_local.configure(text=local)

    def start_download(self, recipe, url, version="Unknown"):
        from src.core.logger import log
        log.info(f"Button Clicked for {recipe.name}. URL: {url}")
        
        if not self.ventoy_path:
            log.warning("Download attempted without Ventoy path selected.")
            self.lbl_path.configure(text_color="red")
            return
        
        if not os.path.exists(self.ventoy_path):
             log.error(f"Selected path does not exist: {self.ventoy_path}")
             return

        import threading
        t = threading.Thread(target=self._download_worker, args=(recipe, url, version), daemon=True)
        t.start()
        log.info(f"Download thread started for {recipe.name}")

    def _download_worker(self, recipe, url, version):
        from src.core.logger import log
        row = next((r for r in self.rows if r.recipe == recipe), None)
        
        try:
            log.info(f"Starting download for {recipe.name} from {url}")
            filename = url.split('/')[-1]
            if not filename.endswith(".iso"): filename = f"{recipe.name.replace(' ', '_')}.iso"
            
            dest = os.path.join(self.ventoy_path, "Managed_ISOs", filename)
            log.debug(f"Destination: {dest}")
            
            if row: self.after(0, lambda: row.update_ui("Downloading...", "Starting...", "cyan"))
            
            import requests
            session = recipe.get_session() 
            
            # FIX: timeouts. (Connect, Read). None means infinite read wait (needed for large files)
            with session.get(url, stream=True, timeout=(10, None)) as r:
                r.raise_for_status()
                total_length = int(r.headers.get('content-length', 0))
                log.info(f"Content-Length: {total_length}")
                
                dl = 0
                with open(dest, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=65536): # 64k chunks
                        if chunk:
                            f.write(chunk)
                            dl += len(chunk)
                            if total_length and row:
                                pct = int(100 * dl / total_length)
                                if pct % 2 == 0: # update every 2% to avoid lag
                                    # Use safe call
                                    self.after(0, lambda p=pct: row.update_ui("Downloading...", f"{p}%", "cyan"))
            
            log.info(f"Download complete: {dest}")
            
            # Update Inventory
            ver = version
            if ver == "Unknown" and row and row.detected_version != "Unknown":
                 ver = row.detected_version
            # Better: manager results cache? 
            # For now, let's trust the text or "Latest"
            
            if hasattr(self, 'inventory'):
                self.inventory.update_entry(recipe.name, ver, filename, url)
                if row: self.after(0, lambda: row.lbl_local.configure(text=ver))

            if row: self.after(0, lambda: row.update_ui("Done", "Installed", "green"))
            
        except Exception as e:
            log.exception(f"Download failed for {recipe.name}")
            if row: self.after(0, lambda: row.update_ui("Error", "Failed", "red"))

            
    def check_single(self, row_obj):
        threading.Thread(target=self._worker_single, args=(row_obj,), daemon=True).start()

    def _worker_single(self, row_obj):
        from src.core.logger import log
        try:
            log.info(f"Checking update for {row_obj.recipe.name}...")
            ver, url, hash_val = row_obj.recipe.get_download_info()
            log.info(f"Result for {row_obj.recipe.name}: Ver={ver}, URL={url}")
            
            if "Error" in ver or not url:
                row_obj.update_ui(ver, "Failed", "red")
            else:
                row_obj.update_ui(ver, "Available", "green", download_url=url)
        except Exception as e:
            log.exception(f"Worker crashed for {row_obj.recipe.name}")
            row_obj.update_ui("Error", str(e), "red")

    def update_all(self):
        from src.core.logger import log
        log.info("Update All triggered")
        self.btn_update_all.configure(state="disabled", text="Updating...")
        # Reset progress
        self.progress.set(0)
        self.completed_count = 0
        self.total_checks = len(self.rows)
        
        threading.Thread(target=self._worker_staggered_start, daemon=True).start()

    def _worker_staggered_start(self):
        from src.core.logger import log
        import time
        log.info("Starting staggered update...")
        
        if self.total_checks == 0:
            self.after(0, lambda: self.btn_update_all.configure(state="normal", text="Update All Catalogs"))
            return

        for row in self.rows:
            # Update Status to "Checking..."
            self.after(0, lambda r=row: r.lbl_status.configure(text="Checking...", text_color="yellow"))
            
            # Spawn worker for this row
            threading.Thread(target=self._worker_single_row, args=(row,), daemon=True).start()
            
            # Wait 200ms before starting next check
            time.sleep(0.2)

    def _worker_single_row(self, row):
        from src.core.logger import log
        try:
            # log.info(f"Checking update for {row.recipe.name}...")
            # Reduce log noise or keep it
            ver, url, hash_val = row.recipe.get_download_info()
            
            # Update UI for this row
            if "Error" in ver or not url or "Fallback" in ver:
                color = "orange" if "Fallback" in ver else "red"
                self.after(0, lambda r=row, v=ver, c=color: r.update_ui(v, "Done" if c=="orange" else "Failed", c, download_url=url))
            else:
                self.after(0, lambda r=row, v=ver, u=url: r.update_ui(v, "Available", "green", download_url=u))
                
        except Exception as e:
            log.exception(f"Error checking {row.recipe.name}")
            self.after(0, lambda r=row: r.update_ui("Error", "Error", "red"))
        
        # Safe completion update in main thread
        self.after(0, self._on_row_completed)

    def _on_row_completed(self):
        from src.core.logger import log
        self.completed_count += 1
        pct = self.completed_count / self.total_checks
        self.progress.set(pct)
        
        if self.completed_count == self.total_checks:
            self.btn_update_all.configure(state="normal", text="Update All Catalogs")
            log.info("All updates finished.")

    # _worker_all removed in favor of sequential

if __name__ == "__main__":
    app = VOMApp()
    app.mainloop()
