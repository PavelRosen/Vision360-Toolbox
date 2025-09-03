import tkinter as tk
from tkinter import ttk, filedialog, scrolledtext, messagebox
import subprocess
import os
import shutil
import re
import threading
import json
from glob import glob
import datetime
import gpxpy
import gpxpy.gpx
from tkintermapview import TkinterMapView
import webbrowser
import sys  # <-- שינוי 1: נוסף import נדרש

# --- פונקציית עזר לאיתור קבצים בסביבת PyInstaller ---
def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)

# --- Backend Logic (No changes here) ---

def find_executable(name: str) -> str:
    base_path = os.path.dirname(os.path.abspath(__file__))
    local_path = os.path.join(base_path, name)
    if os.path.isfile(local_path): return local_path
    return shutil.which(name)

def extract_gpx_using_proven_method(exiftool_path: str, video_path: str, output_gpx_path: str, log_callback=None):
    if log_callback: log_callback(f"[*] Starting proven GPX extraction for: {os.path.basename(video_path)}")
    command = [exiftool_path, "-ee", "-p", "$gpsdatetime,$gpslatitude#,$gpslongitude#,$gpsaltitude#", "-d", "%Y-%m-%dT%H:%M:%SZ", video_path]
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=True, encoding='utf-8')
        gps_raw_data = result.stdout
        if not gps_raw_data.strip():
            if log_callback: log_callback("[!] ERROR: ExifTool extracted no GPS data.", "error"); return False
    except subprocess.CalledProcessError:
        if log_callback: log_callback(f"    This often means no GPS tags were found in the file.", "error"); return False
    except Exception as e:
        if log_callback: log_callback(f"[!] An unexpected error occurred with ExifTool: {e}", "error"); return False
    try:
        gpx = gpxpy.gpx.GPX(); gpx_track = gpxpy.gpx.GPXTrack(); gpx.tracks.append(gpx_track); gpx_segment = gpxpy.gpx.GPXTrackSegment(); gpx_track.segments.append(gpx_segment)
        point_count = 0
        for line in gps_raw_data.strip().split('\n'):
            try:
                parts = line.split(',');
                if len(parts) < 4: continue
                time_str, lat_str, lon_str, alt_str = parts
                point_time = datetime.datetime.strptime(time_str, '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=datetime.timezone.utc)
                gpx_segment.points.append(gpxpy.gpx.GPXTrackPoint(latitude=float(lat_str), longitude=float(lon_str), elevation=float(alt_str), time=point_time))
                point_count += 1
            except (ValueError, IndexError): continue
        if point_count == 0:
            if log_callback: log_callback("[!] ERROR: No valid GPS points could be parsed.", "error"); return False
        with open(output_gpx_path, 'w', encoding='utf-8') as f: f.write(gpx.to_xml())
        if log_callback: log_callback(f"[+] Success! Created GPX file with {point_count} track points at: {output_gpx_path}", "success")
        return True
    except Exception as e:
        if log_callback: log_callback(f"[!] ERROR: Failed to build GPX file: {e}", "error"); return False

def get_video_resolution(file_path: str, log_callback=None):
    ffprobe_path = find_executable("ffprobe")
    if not ffprobe_path:
        if log_callback: log_callback("[-] Warning: 'ffprobe' not found.", "error"); return None
    command = [ffprobe_path, "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "json", file_path]
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        return json.loads(result.stdout)["streams"][0]["width"], json.loads(result.stdout)["streams"][0]["height"]
    except Exception as e:
        if log_callback: log_callback(f"[!] Could not get video resolution: {e}", "error"); return None

def convert_video_with_sdk(sdk_path: str, model_dir: str, video_path: str, output_path: str, resolution: str, stitcher_model: str, enhancements: dict, log_callback=None):
    if log_callback: log_callback(f"\n[*] Starting video conversion for: {os.path.basename(video_path)}")
    resolutions_map = {"8K": (7680, 3840), "5.7K": (5760, 2880), "4K": (3840, 1920), "3K": (3008, 1504)}
    try: width, height = resolutions_map[resolution]; output_size_str = f"{width}x{height}"
    except KeyError:
        if log_callback: log_callback(f"[!] ERROR: Invalid resolution '{resolution}'.", "error"); return None
    command = [sdk_path, "-inputs", video_path, "-output", output_path, "-output_size", output_size_str, "-stitch_type", "aistitch", "-ai_stitching_model", os.path.join(model_dir, stitcher_model), "-enable_flowstate", "ON", "-disable_cuda", "true", "-enable_soft_decode", "true", "-enable_soft_encode", "true"]
    active_enhancements = []
    for key, (model_file, params) in enhancements.items():
        command.extend(params); command.append(os.path.join(model_dir, model_file)); active_enhancements.append(key.replace("_", " ").title())
    if log_callback:
        log_callback(f"    Resolution: {output_size_str}"); log_callback(f"    Stitcher Model: {stitcher_model}")
        if active_enhancements: log_callback(f"    Enhancements: {', '.join(active_enhancements)}")
        log_callback(f"    Outputting to: {output_path}")
    try: return subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8', bufsize=1)
    except Exception as e:
        if log_callback: log_callback(f"\n[!] ERROR: Failed to start process: {e}", "error"); return None

# --- GUI Application ---

class InstaToolApp:
    def __init__(self, master):
        self.master = master
        
        # <-- שינוי 3: טעינת והגדרת הלוגו כאייקון החלון -->
        try:
            # החלף את "logo.png" בשם המדויק של קובץ הלוגו שלך
            logo_path = resource_path("logo.png") 
            logo_image = tk.PhotoImage(file=logo_path)
            master.iconphoto(True, logo_image)
        except Exception as e:
            print(f"Error loading application icon: {e}")
        # <-- סוף קטע הקוד של הלוגו -->

        master.title("Insta360 Toolbox")
        master.geometry("900x800")
        self.btc_address = "BC1QM2E6SE7FUE4WEPMXU2ASM47AS59WVX4WL6WRXW"
        self.kofi_url = "https://ko-fi.com/pavelrst"
        self.contact_email = "Pavelrzt@gmail.com"
        self.sdk_path = find_executable("testSDKDemo"); self.exiftool_path = find_executable("exiftool")
        self.model_dir = os.path.join(os.path.dirname(self.sdk_path), "modelfile") if self.sdk_path else None
        self.input_file_var = tk.StringVar(); self.output_folder_var = tk.StringVar(); self.resolution_var = tk.StringVar(); self.stitcher_model_var = tk.StringVar()
        self.ENHANCEMENT_MAP = {'ColorPlus': {'pattern': 'colorplus_model*.ins', 'params': ["-enable_colorplus", "ON", "-colorplus_model"]},'AI Denoise': {'pattern': 'jpg_denoise*.ins', 'params': ["-enable_denoise", "ON", "-image_denoise_model"]},'Deflicker': {'pattern': 'deflicker*.ins', 'params': ["-enable_deflicker", "ON", "-deflicker_model"]},'Defringe HR': {'pattern': 'defringe_hr*.ins', 'params': ["-enable_defringe", "ON", "-hr_defringe_model"]},'Defringe LR': {'pattern': 'defringe_lr*.ins', 'params': ["-enable_defringe", "ON", "-lr_defringe_model"]},}
        self.enhancement_vars = {key: tk.BooleanVar() for key in self.ENHANCEMENT_MAP}
        self.found_models = {}; self.available_stitcher_models = []
        self.discover_models()
        self.current_process = None
        self.gpx_input_file_var = tk.StringVar(); self.gpx_output_file_var = tk.StringVar()
        self.create_widgets()
        self.check_executables()

    def create_widgets(self):
        main_frame = ttk.Frame(self.master, padding="10"); main_frame.pack(fill=tk.BOTH, expand=True)
        main_frame.rowconfigure(0, weight=1); main_frame.columnconfigure(0, weight=1)
        style = ttk.Style(self.master); style.theme_use('clam'); style.configure("blue.Horizontal.TProgressbar", troughcolor='#E0E0E0', background='#0078D7', thickness=20)
        style.configure("Link.TLabel", foreground="blue", font=('TkDefaultFont', 10, 'underline'))
        self.notebook = ttk.Notebook(main_frame); self.notebook.grid(row=0, column=0, sticky="nsew")
        convert_tab = ttk.Frame(self.notebook, padding="10"); self.notebook.add(convert_tab, text="Convert to 360 MP4")
        gpx_tab = ttk.Frame(self.notebook, padding="10"); self.notebook.add(gpx_tab, text="Extract GPX")
        map_tab = ttk.Frame(self.notebook, padding="10"); self.notebook.add(map_tab, text="Map Viewer")
        about_tab = ttk.Frame(self.notebook, padding="10"); self.notebook.add(about_tab, text="About")
        self.create_conversion_tab(convert_tab)
        self.create_gpx_tab(gpx_tab)
        self.create_map_tab(map_tab)
        self.create_about_tab(about_tab)
        log_frame = ttk.LabelFrame(main_frame, text="Log Output"); log_frame.grid(row=1, column=0, sticky="ew", pady=(10,0))
        self.log_text = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD, height=8, font=("monospace", 9)); self.log_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.log_text.configure(state='disabled'); self.log_text.tag_config("error", foreground="#d9534f"); self.log_text.tag_config("success", foreground="#5cb85c")

    def create_conversion_tab(self, tab):
        # ... no changes ...
        input_frame = ttk.LabelFrame(tab, text="1. Select Input File"); input_frame.pack(fill=tk.X, padx=5, pady=5)
        ttk.Entry(input_frame, textvariable=self.input_file_var, state="readonly").pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5, pady=5)
        ttk.Button(input_frame, text="Browse...", command=self.select_convert_input_file).pack(side=tk.LEFT, padx=5, pady=5)
        output_frame = ttk.LabelFrame(tab, text="2. Select Output Folder"); output_frame.pack(fill=tk.X, padx=5, pady=5)
        ttk.Entry(output_frame, textvariable=self.output_folder_var, state="readonly").pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5, pady=5)
        ttk.Button(output_frame, text="Browse...", command=self.select_output_folder).pack(side=tk.LEFT, padx=5, pady=5)
        options_frame = ttk.LabelFrame(tab, text="3. Conversion Options"); options_frame.pack(fill=tk.X, padx=5, pady=5)
        res_frame = ttk.Frame(options_frame); res_frame.pack(fill=tk.X, padx=5, pady=2)
        ttk.Label(res_frame, text="Output Resolution:", width=16).pack(side=tk.LEFT)
        self.res_combobox = ttk.Combobox(res_frame, textvariable=self.resolution_var, state="disabled"); self.res_combobox.pack(side=tk.LEFT, fill=tk.X, expand=True)
        stitcher_frame = ttk.Frame(options_frame); stitcher_frame.pack(fill=tk.X, padx=5, pady=2)
        ttk.Label(stitcher_frame, text="Stitcher Model:", width=16).pack(side=tk.LEFT)
        self.stitcher_combobox = ttk.Combobox(stitcher_frame, textvariable=self.stitcher_model_var, values=self.available_stitcher_models, state="disabled"); self.stitcher_combobox.pack(side=tk.LEFT, fill=tk.X, expand=True)
        enhancements_frame = ttk.LabelFrame(tab, text="4. Enhancements"); enhancements_frame.pack(fill=tk.X, padx=5, pady=5)
        self.enhancement_checkboxes = {}
        for name in self.ENHANCEMENT_MAP.keys():
            cb = ttk.Checkbutton(enhancements_frame, text=name, variable=self.enhancement_vars[name], state="disabled")
            cb.pack(side=tk.LEFT, padx=10, pady=5); self.enhancement_checkboxes[name] = cb
            if name in self.found_models: cb.config(state="normal")
        control_frame = ttk.Frame(tab); control_frame.pack(fill=tk.X, padx=5, pady=10)
        self.convert_button = ttk.Button(control_frame, text="Start Conversion", command=self.start_conversion_thread, state="disabled"); self.convert_button.pack(side=tk.LEFT, padx=5)
        self.cancel_button = ttk.Button(control_frame, text="Cancel", command=self.cancel_conversion, state="disabled"); self.cancel_button.pack(side=tk.LEFT, padx=5)
        progress_container = ttk.Frame(control_frame); progress_container.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        self.progress_bar = ttk.Progressbar(progress_container, style="blue.Horizontal.TProgressbar"); self.progress_bar.pack(fill=tk.X, expand=True)
        self.progress_label = ttk.Label(progress_container, text="0%", anchor="center", font=("Arial", 10, "bold"), background='#E0E0E0', foreground='black'); self.progress_label.place(relwidth=1.0, relheight=1.0)
    
    def create_gpx_tab(self, tab):
        # ... no changes ...
        gpx_input_frame = ttk.LabelFrame(tab, text="1. Select Input INSV File"); gpx_input_frame.pack(fill=tk.X, padx=5, pady=10)
        ttk.Entry(gpx_input_frame, textvariable=self.gpx_input_file_var, state="readonly").pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5, pady=5)
        ttk.Button(gpx_input_frame, text="Browse...", command=self.select_gpx_input_file).pack(side=tk.LEFT, padx=5, pady=5)
        gpx_output_frame = ttk.LabelFrame(tab, text="2. Select Output GPX File Path"); gpx_output_frame.pack(fill=tk.X, padx=5, pady=10)
        ttk.Entry(gpx_output_frame, textvariable=self.gpx_output_file_var, state="readonly").pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5, pady=5)
        ttk.Button(gpx_output_frame, text="Browse...", command=self.select_gpx_output_file).pack(side=tk.LEFT, padx=5, pady=5)
        gpx_control_frame = ttk.Frame(tab); gpx_control_frame.pack(fill=tk.X, padx=5, pady=20)
        self.gpx_extract_button = ttk.Button(gpx_control_frame, text="Extract GPX", command=self.start_gpx_extraction_thread, state="disabled"); self.gpx_extract_button.pack()

    def create_map_tab(self, tab):
        # ... no changes ...
        tab.rowconfigure(1, weight=1); tab.columnconfigure(0, weight=1)
        self.tile_servers = {"Google Normal": "https://mt0.google.com/vt/lyrs=m&hl=en&x={x}&y={y}&z={z}&s=Ga", "Google Satellite": "https://mt0.google.com/vt/lyrs=s,h&hl=en&x={x}&y={y}&z={z}&s=Ga", "OpenStreetMap": "https://a.tile.openstreetmap.org/{z}/{x}/{y}.png"}
        controls_frame = ttk.Frame(tab); controls_frame.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        ttk.Button(controls_frame, text="Load GPX File...", command=self.load_gpx_from_dialog).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Label(controls_frame, text="Map Type:").pack(side=tk.LEFT)
        self.map_type_combo = ttk.Combobox(controls_frame, state="readonly", values=list(self.tile_servers.keys())); self.map_type_combo.pack(side=tk.LEFT); self.map_type_combo.set("OpenStreetMap"); self.map_type_combo.bind("<<ComboboxSelected>>", self.change_map_type)
        self.map_widget = TkinterMapView(tab, corner_radius=0); self.map_widget.grid(row=1, column=0, sticky="nsew"); self.map_widget.set_tile_server(self.tile_servers[self.map_type_combo.get()]); self.map_widget.set_position(48.8566, 2.3522); self.map_widget.set_zoom(5)
        
    def create_about_tab(self, tab):
        tab.columnconfigure(0, weight=1)
        
        # --- App Description ---
        desc_frame = ttk.LabelFrame(tab, text="What is this thing anyway?", padding=15)
        desc_frame.grid(row=0, column=0, sticky="ew", pady=10)
        title_font = ('TkDefaultFont', 12, 'bold')
        ttk.Label(desc_frame, text="Your Insta360 Desktop Workflow Hub", font=title_font).pack(anchor="w", pady=(0,10))
        desc_text = "    This toolbox simplifies your workflow by combining the power of the official Insta360 SDK for flawless video conversion with the precision of the renowned ExifTool for GPS data extraction, all wrapped in one simple interface."
        ttk.Label(desc_frame, text=desc_text, wraplength=700, justify="left").pack(anchor="w")

        # --- Credits and Support ---
        support_frame = ttk.LabelFrame(tab, text="Credits & Support", padding=15)
        support_frame.grid(row=1, column=0, sticky="ew", pady=10)
        
        credit_text = "Vision and concept Lovingly crafted by Pavel Rosental.\nWith Help by his AI assistant, Gemini."
        ttk.Label(support_frame, text=credit_text, font=('TkDefaultFont', 10, 'italic'), justify="left").pack(anchor="w", pady=(0, 15))

        ttk.Label(support_frame, text="If this tool saved you time or a headache, consider fueling future development:", justify="left").pack(anchor="w", pady=(0, 10))

        # Contact
        contact_frame = ttk.Frame(support_frame)
        contact_frame.pack(anchor="w", pady=5, padx=20)
        ttk.Label(contact_frame, text=" • Contact: ").pack(side=tk.LEFT)
        self.email_link = ttk.Label(contact_frame, text=self.contact_email, style="Link.TLabel", cursor="hand2")
        self.email_link.pack(side=tk.LEFT)
        self.email_link.bind("<Button-1>", lambda e: self.copy_to_clipboard(self.email_link, self.contact_email, "Email"))
        
        # Coffee (Ko-fi) link
        kofi_frame = ttk.Frame(support_frame)
        kofi_frame.pack(anchor="w", pady=5, padx=20)
        ttk.Label(kofi_frame, text=" • Buy me a coffee at: ").pack(side=tk.LEFT)
        self.kofi_link = ttk.Label(kofi_frame, text=self.kofi_url, style="Link.TLabel", cursor="hand2")
        self.kofi_link.pack(side=tk.LEFT)
        self.kofi_link.bind("<Button-1>", lambda e: self.copy_to_clipboard(self.kofi_link, self.kofi_url, "URL"))

        # Bitcoin donations
        btc_frame = ttk.Frame(support_frame)
        btc_frame.pack(anchor="w", pady=5, padx=20)
        ttk.Label(btc_frame, text=" • Bitcoin donations:").pack(anchor="w", pady=(5,2))
        btc_addr_frame = ttk.Frame(btc_frame); btc_addr_frame.pack(anchor="w", pady=5)
        btc_entry = ttk.Entry(btc_addr_frame, width=45); btc_entry.insert(0, self.btc_address); btc_entry.config(state="readonly"); btc_entry.pack(side=tk.LEFT)
        self.copy_button = ttk.Button(btc_addr_frame, text="Copy", command=self.copy_btc_address, width=8); self.copy_button.pack(side=tk.LEFT, padx=5)

    def copy_to_clipboard(self, widget, text_to_copy, item_name="Text"):
        """Copies text to clipboard and provides feedback on a label widget."""
        self.master.clipboard_clear()
        self.master.clipboard_append(text_to_copy)
        original_text = widget['text']
        widget.config(text="Copied to clipboard!", style="")
        self.master.after(2000, lambda: widget.config(text=original_text, style="Link.TLabel"))
        self.log_message(f"{item_name} copied to clipboard!")

    def copy_btc_address(self):
        """Copies text to clipboard and provides feedback on the BTC button."""
        self.master.clipboard_clear()
        self.master.clipboard_append(self.btc_address)
        original_text = self.copy_button['text']
        self.copy_button.config(text="Copied!")
        self.master.after(1500, lambda: self.copy_button.config(text=original_text))
        self.log_message("BTC address copied to clipboard!")
        
    def change_map_type(self, event=None):
        map_type = self.map_type_combo.get(); self.map_widget.set_tile_server(self.tile_servers[map_type]); self.log_message(f"Map type changed to {map_type}.")
    def load_gpx_from_dialog(self):
        file_path = filedialog.askopenfilename(title="Select GPX File", filetypes=[("GPX files", "*.gpx")])
        if file_path: self.display_gpx_on_map(file_path)
    def display_gpx_on_map(self, gpx_path):
        self.log_message(f"Loading GPX path on map from: {os.path.basename(gpx_path)}")
        try:
            with open(gpx_path, 'r', encoding='utf-8') as f: gpx = gpxpy.parse(f)
            points = [(p.latitude, p.longitude) for t in gpx.tracks for s in t.segments for p in s.points]
            if not points: messagebox.showwarning("No Points", "The selected GPX file contains no track points to display."); return
            self.map_widget.delete_all_path()
            self.map_widget.set_path(points, color="#FF0000", width=3)
            bounds = gpx.get_bounds()
            if bounds:
                top_left = (bounds.max_latitude, bounds.min_longitude)
                bottom_right = (bounds.min_latitude, bounds.max_longitude)
                self.map_widget.fit_bounding_box(top_left, bottom_right)
            self.log_message(f"Successfully displayed {len(points)} points on the map.")
            self.notebook.select(2)
        except Exception as e:
            self.log_message(f"ERROR loading GPX on map: {e}", "error")
            messagebox.showerror("GPX Error", f"Could not load or parse the GPX file.\n\nDetails: {e}")
    def run_gpx_extraction(self):
        input_file, output_file = self.gpx_input_file_var.get(), self.gpx_output_file_var.get()
        success = extract_gpx_using_proven_method(self.exiftool_path, input_file, output_file, self.log_message)
        if success: self.master.after(0, self.display_gpx_on_map, output_file)
        self.master.after(0, self.check_gpx_inputs)
    def discover_models(self):
        if not (self.model_dir and os.path.isdir(self.model_dir)): return
        self.available_stitcher_models = [os.path.basename(f) for f in glob(os.path.join(self.model_dir, 'ai_stitcher*.ins'))]
        for name, data in self.ENHANCEMENT_MAP.items():
            found = glob(os.path.join(self.model_dir, data['pattern']))
            if found: self.found_models[name] = (os.path.basename(found[0]), data['params'])
    def log_message(self, message, tag=None):
        def append(): self.log_text.configure(state='normal'); self.log_text.insert(tk.END, message + "\n", tag); self.log_text.configure(state='disabled'); self.log_text.see(tk.END)
        self.master.after(0, append)
    def update_progress(self, value):
        def update(): self.progress_bar['value'] = value; self.progress_label['text'] = f"{value}%"
        self.master.after(0, update)
    def check_executables(self):
        found_all = True
        if not self.sdk_path: self.log_message("[!] SDK ('testSDKDemo') not found.", "error"); found_all = False
        if not find_executable("ffprobe"): self.log_message("[!] FFprobe not found.", "error"); found_all = False
        if not self.exiftool_path: self.log_message("[!] ExifTool not found. GPX extraction is disabled.", "error"); self.gpx_extract_button.config(state="disabled"); found_all = False
        if found_all: self.log_message("[+] All required executables found.", "success")
        if self.model_dir: self.log_message("[+] Model directory found.", "success")
        else: self.log_message("[!] Model directory not found.", "error")
    def select_convert_input_file(self, *args):
        file_path = filedialog.askopenfilename(title="Select .insv File", filetypes=(("Insta360 Video", "*.insv"), ("All files", "*.*")))
        if file_path: self.input_file_var.set(file_path); self.detect_and_update_options(file_path); self.check_convert_inputs()
    def detect_and_update_options(self, file_path):
        resolution = get_video_resolution(file_path, self.log_message)
        all_options = {"8K": 7680, "5.7K": 5760, "4K": 3840, "3K": 3008}
        if resolution: self.available_resolutions = [res for res, w in all_options.items() if resolution[0] >= w]
        else: self.available_resolutions = ["5.7K", "4K", "3K"]
        if not self.available_resolutions: self.available_resolutions = ["4K"]
        self.res_combobox['values'] = self.available_resolutions; self.resolution_var.set(self.available_resolutions[0]); self.res_combobox.config(state="readonly")
        if self.available_stitcher_models: self.stitcher_model_var.set(self.available_stitcher_models[0])
        self.stitcher_combobox.config(state="readonly")
    def select_output_folder(self, *args):
        folder_path = filedialog.askdirectory(title="Select Output Folder")
        if folder_path: self.output_folder_var.set(folder_path); self.check_convert_inputs()
    def check_convert_inputs(self):
        self.convert_button.config(state="normal" if self.input_file_var.get() and self.output_folder_var.get() else "disabled")
    def set_convert_ui_state(self, is_running: bool):
        state = "disabled" if is_running else "normal"; readonly_state = "disabled" if is_running else "readonly"
        self.convert_button.config(state=state); self.cancel_button.config(state="normal" if is_running else "disabled")
        self.res_combobox.config(state=readonly_state); self.stitcher_combobox.config(state=readonly_state)
        for name, cb in self.enhancement_checkboxes.items():
            if not is_running and name in self.found_models: cb.config(state="normal")
            elif is_running: cb.config(state="disabled")
    def start_conversion_thread(self):
        if not self.sdk_path: self.log_message("[!] Cannot start: SDK not found.", "error"); return
        self.set_convert_ui_state(is_running=True); self.update_progress(0)
        self.log_text.configure(state='normal'); self.log_text.delete(1.0, tk.END); self.log_text.configure(state='disabled')
        threading.Thread(target=self.run_conversion, daemon=True).start()
    def cancel_conversion(self):
        if self.current_process: self.log_message("\n[!] User requested to cancel. Terminating...", "error"); self.current_process.terminate()
    def run_conversion(self):
        input_file, output_folder, resolution, stitcher_model = self.input_file_var.get(), self.output_folder_var.get(), self.resolution_var.get(), self.stitcher_model_var.get()
        enhancements = {name: self.found_models[name] for name, var in self.enhancement_vars.items() if var.get() and name in self.found_models}
        output_file_path = os.path.join(output_folder, f"{os.path.splitext(os.path.basename(input_file))[0]}_{resolution}_360.mp4")
        self.current_process = convert_video_with_sdk(self.sdk_path, self.model_dir, input_file, output_file_path, resolution, stitcher_model, enhancements, self.log_message)
        if self.current_process:
            for line in iter(self.current_process.stdout.readline, ''):
                progress_match = re.search(r"process\s*=\s*(\d+)\s*%", line.strip())
                if progress_match: self.update_progress(int(progress_match.group(1)))
                elif line.strip(): self.log_message(line.strip())
            self.current_process.wait()
            if self.current_process.returncode == 0 and os.path.exists(output_file_path): self.log_message(f"[+] Successfully converted video.", "success"); self.update_progress(100)
            elif "Terminating..." not in self.log_text.get("1.0", tk.END): self.log_message(f"\n[!] ERROR: SDK process failed (code {self.current_process.returncode}).", "error")
        self.master.after(0, self.finalize_convert_ui)
    def finalize_convert_ui(self):
        self.set_convert_ui_state(is_running=False); self.current_process = None
    def select_gpx_input_file(self):
        file_path = filedialog.askopenfilename(title="Select .insv File with GPS Data", filetypes=(("Insta360 Video", "*.insv"), ("All files", "*.*")))
        if file_path:
            self.gpx_input_file_var.set(file_path)
            self.gpx_output_file_var.set(os.path.splitext(file_path)[0] + ".gpx")
            self.check_gpx_inputs()
    def select_gpx_output_file(self):
        file_path = filedialog.asksaveasfilename(title="Save GPX File As...", defaultextension=".gpx", filetypes=(("GPX files", "*.gpx"), ("All files", "*.*")))
        if file_path: self.gpx_output_file_var.set(file_path); self.check_gpx_inputs()
    def check_gpx_inputs(self):
        self.gpx_extract_button.config(state="normal" if self.gpx_input_file_var.get() and self.gpx_output_file_var.get() else "disabled")
    def start_gpx_extraction_thread(self):
        if not self.exiftool_path: self.log_message("[!] Cannot start: 'exiftool' not found.", "error"); return
        self.log_text.configure(state='normal'); self.log_text.delete(1.0, tk.END); self.log_text.configure(state='disabled')
        self.gpx_extract_button.config(state="disabled")
        threading.Thread(target=self.run_gpx_extraction, daemon=True).start()

if __name__ == "__main__":
    root = tk.Tk()
    app = InstaToolApp(root)
    root.mainloop()