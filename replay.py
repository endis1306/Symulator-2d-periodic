# sim_replayer_with_bounds.py  (zaktualizowany, artists cache + opt. + toggles)
import json
import math

from matplotlib.patches import Circle, Polygon, FancyArrowPatch, Arc, Wedge
from matplotlib.lines import Line2D
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import matplotlib.patheffects as pe
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import copy

from replayer.utils import get_vec, build_spec_indices, compute_engine_world, compute_sensor_world, normalize_shape, transform_shape_local_to_global
from replayer.inspector import InspectorPanel

import ctypes
import platform

# --- opcjonalnie: ustaw świadomość DPI na Windows ---
if platform.system() == "Windows":
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)  # lub 2
    except Exception:
        pass


class ToggleSwitch(tk.Frame):
    """
    Wyostrzony widget przełącznika typu toggle z wsparciem dla wysokiego DPI.
    """
    def __init__(self, master, label="", initial=True, width=60, height=30,
                 on_color="#4f46e5", off_color="#cbd5e1", knob_color="white", command=None, scale=None):
        super().__init__(master, bg=master["bg"])
        self._width = width
        self._height = height
        self._radius = height / 2
        self._on_color = on_color
        self._off_color = off_color
        self._knob_color = knob_color
        self.command = command
        self.state = bool(initial)



        # automatyczna skala Canvas według DPI
        if scale is None:
            dpi = self.winfo_fpixels('1i')  # liczba pikseli na cal
            scale = dpi / 96.0
        self._scale = scale

        # Canvas w większej rozdzielczości
        self.canvas = tk.Canvas(self, width=width, height=height,
                                highlightthickness=0, bg=self["bg"])
        self.canvas.pack(side="left")
        self.canvas.bind("<Button-1>", self._on_click)

        # Label obok
        self.lbl = tk.Label(self, text=label, bg=self["bg"], fg="#0f172a", font=("Inter", 10, "bold"))
        self.lbl.pack(side="left", padx=(8, 0))

        self._draw()

    def _draw(self):
        self.canvas.delete("all")
        w, h, r = self._width, self._height, self._radius
        s = self._scale
        color = self._on_color if self.state else self._off_color
        pad = 3

        # --- współrzędne przeskalowane ---
        w_s, h_s, r_s, pad_s = w*s, h*s, r*s, pad*s

        # tło toggle
        self.canvas.create_rectangle(r_s, 0, w_s - r_s, h_s,
                                     outline=color, fill=color, width=0)
        self.canvas.create_oval(0, 0, 2*r_s, h_s, outline=color, fill=color, width=0)
        self.canvas.create_oval(w_s - 2*r_s, 0, w_s, h_s, outline=color, fill=color, width=0)

        # knob
        knob_x = w_s - r_s if self.state else r_s
        self.canvas.create_oval(knob_x - (r_s - pad_s), pad_s,
                                knob_x + (r_s - pad_s), h_s - pad_s,
                                outline="#94a3b8", fill=self._knob_color, width=max(1, s))

        # przeskaluj Canvas do nominalnych wymiarów (antialiasing)
        self.canvas.scale("all", 0, 0, 1/s, 1/s)
        self.canvas.config(width=w, height=h)

    def _on_click(self, ev=None):
        self.state = not self.state
        self._draw()
        if callable(self.command):
            try:
                self.command(self.state)
            except Exception:
                pass

    def set(self, val: bool):
        self.state = bool(val)
        self._draw()

    def get(self) -> bool:
        return bool(self.state)





class SimReplayerPy:

    def __init__(self, raw_frames):
        if not raw_frames:
            raise ValueError("Pusty log")

        self.world_init = raw_frames[0]  # INIT
        self.raw_frames = raw_frames[1:]  # FRAME 0,1,2,...

        self.world_info = self.world_init.get("world", {})
        self.base_objects = {}
        self.frames = []

        self._preprocess_frames()

        self.idx = 0
        self.playing = False
        self.selected_id = None

        # cache/opt helpers
        self._artists = {}
        self._axes_initialized = False
        self._cached_obj_list_ids = None
        self._last_inspector_id = None
        self._last_inspector_frame = None

        # speed accumulator for fractional stepping
        self._speed_accumulator = 0.0

        # Boundary/map control
        if self.world_info.get("world_box"):
            wb = self.world_info["world_box"]
            self.bx = max(wb.get("maxx", 50), 50)
            self.by = max(wb.get("maxy", 50), 50)
        else:
            self.bx, self.by = self.estimate_boundaries()

        self.boundary_pts = []

        # --- UI init ---
        self.root = tk.Tk()
        self.root.title("SimReplayer Pro // Fidelity Control")
        self.root.geometry("1600x980")
        self.root.configure(bg="#f8fafc")

        # --- GRID setup on root: 3 columns (left, center, right) + top bar row ---
        # content row is row=1 (row=0 = top_bar)
        self.root.grid_rowconfigure(1, weight=1)

        # kolumny: left (sztywny/min), center (elastyczny), right (średnio elastyczny)
        self.root.grid_columnconfigure(0, weight=2, minsize=240)  # LEFT - nie rośnie
        self.root.grid_columnconfigure(1, weight=4, minsize=440)  # CENTER
        self.root.grid_columnconfigure(2, weight=3, minsize=420)  # RIGHT

        style = ttk.Style()
        style.theme_use('clam')
        style.configure("Treeview", background="white", foreground="#1e293b", fieldbackground="white", borderwidth=1,
                        font=("Inter", 9))
        style.configure("Treeview.Heading", background="#f1f5f9", foreground="#475569", font=("Inter", 8, "bold"))
        style.map("Treeview", background=[('selected', '#4f46e5')])

        # ---------------- Top bar ----------------
        self.top_bar = tk.Frame(self.root, bg="white", height=80, highlightbackground="#e2e8f0", highlightthickness=1)
        # top_bar zajmuje cały wiersz nad trzema kolumnami
        self.top_bar.grid(row=0, column=0, columnspan=3, sticky="ew")

        tk.Label(self.top_bar, text="SIMREPLAYER PRO", bg="white", fg="#4f46e5", font=("Inter", 16, "bold")).pack(
            side="left", padx=20)

        nav_frame = tk.Frame(self.top_bar, bg="white")
        nav_frame.pack(side="left", padx=10)

        btn_cfg = {"bg": "#f1f5f9", "fg": "#475569", "relief": "flat", "font": ("Inter", 12, "bold"), "padx": 15,
                   "pady": 5}
        self.btn_prev = tk.Button(nav_frame, text="❮", command=self.prev_frame, **btn_cfg)
        self.btn_prev.pack(side="left", padx=5)
        self.btn_play = tk.Button(nav_frame, text="▶ PLAY", command=self.toggle_play, bg="#4f46e5", fg="white",
                                  relief="flat", font=("Inter", 11, "bold"), padx=25, pady=8)
        self.btn_play.pack(side="left", padx=8)
        self.btn_next = tk.Button(nav_frame, text="❯", command=self.next_frame, **btn_cfg)
        self.btn_next.pack(side="left", padx=5)




        # --- kontrola prędkości odtwarzania (◀ x0.5 / wartość / ▶ x2) ---
        self.play_speed = 1
        self.base_delay = 700  # fallback w ms gdy brak 'time' w framach

        speed_cfg = {
            "bg": "#f1f5f9",
            "fg": "#475569",
            "relief": "flat",
            "font": ("Inter", 12, "bold"),
            "padx": 10,
            "pady": 5
        }

        self.btn_speed_down = tk.Button(nav_frame, text="◀", command=lambda: self.change_speed(0.5), **speed_cfg)
        self.btn_speed_down.pack(side="left", padx=(14, 4))

        self.lbl_speed = tk.Label(nav_frame, text=f"{self.play_speed:.2f}x", bg="white", fg="#334155",
                                  font=("Inter", 11, "bold"), width=6)
        self.lbl_speed.pack(side="left")

        self.btn_speed_up = tk.Button(nav_frame, text="▶", command=lambda: self.change_speed(2.0), **speed_cfg)
        self.btn_speed_up.pack(side="left", padx=(4, 14))


        self.slider = tk.Scale(self.top_bar, from_=0, to=max(0, len(self.frames) - 1), orient="horizontal",
                               bg="white", fg="#64748b", troughcolor="#f1f5f9", highlightthickness=0, borderwidth=0,
                               command=self.on_slider, length=620)
        self.slider.pack(side="left", fill="x", expand=True, padx=20)

        # ---------------- Left panel ----------------
        self.left_panel = tk.Frame(self.root, bg="#f8fafc")
        self.left_panel.grid(row=1, column=0, sticky="nsew")  # wypełnia cały panel
        self.left_panel.grid_columnconfigure(0, weight=1)
        self.left_panel.grid_rowconfigure(1, weight=1)  # Listbox rośnie w pionie

        # --- Aktywne obiekty ---
        tk.Label(self.left_panel, text="AKTYWNE OBIEKTY", bg="#f8fafc", fg="#64748b",
                 font=("Inter", 9, "bold"), pady=6).grid(row=0, column=0, sticky="ew", padx=4, pady=2)

        self.obj_list = tk.Listbox(self.left_panel, bg="white", fg="#1e293b",
                                   borderwidth=1, highlightthickness=1, highlightbackground="#e2e8f0",
                                   selectbackground="#4f46e5", font=("JetBrains Mono", 9))
        self.obj_list.grid(row=1, column=0, sticky="nsew", padx=4, pady=2)  # rośnie w pionie
        self.obj_list.bind('<<ListboxSelect>>', self.on_list_select)

        # --- Separator ---
        sep = ttk.Separator(self.left_panel, orient='horizontal')
        sep.grid(row=2, column=0, sticky='ew', padx=4, pady=4)

        # --- Map / boundary controls ---
        tk.Label(self.left_panel, text="MAPA I PUNKTY GRANICZNE", bg="#f8fafc", fg="#475569",
                 font=("Inter", 10, "bold")).grid(row=3, column=0, sticky='ew', padx=4, pady=(2, 2))

        map_frame = tk.Frame(self.left_panel, bg="#f8fafc")
        map_frame.grid(row=4, column=0, sticky='ew', padx=4, pady=2)
        for i in range(5):
            map_frame.grid_columnconfigure(i, weight=0)  # tylko Apply button niech się ewentualnie rozpycha
        map_frame.grid_columnconfigure(4, weight=1)  # Apply button "wypycha" resztę, elastycznie

        tk.Label(map_frame, text="Szer.", bg="#f8fafc", fg="#475569").grid(row=0, column=0, sticky='w')
        self.entry_map_w = tk.Entry(map_frame, width=6)
        self.entry_map_w.grid(row=0, column=1, padx=(2, 4))
        tk.Label(map_frame, text="Wys.", bg="#f8fafc", fg="#475569").grid(row=0, column=2, sticky='w')
        self.entry_map_h = tk.Entry(map_frame, width=6)
        self.entry_map_h.grid(row=0, column=3, padx=(2, 2))
        tk.Button(map_frame, text="Apply", command=self.apply_map_size,
                  relief='flat', bg='#4f46e5', fg='white').grid(row=0, column=4, padx=2)

        self.entry_map_w.insert(0, str(int(self.bx)))
        self.entry_map_h.insert(0, str(int(self.by)))

        # --- Boundary points text ---
        tk.Label(self.left_panel, text="Wklej punkty (x,y) po jednym w wierszu lub JSON list:",
                 bg="#f8fafc", fg="#475569", wraplength=220, justify='left').grid(row=5, column=0, sticky='ew', padx=4)
        self.bound_text = tk.Text(self.left_panel, height=6, width=20, bg='white', fg='#0f172a',
                                  font=("JetBrains Mono", 9))
        self.bound_text.grid(row=6, column=0, sticky='ew', padx=4, pady=2)
        tk.Button(self.left_panel, text="Load Points", command=self.load_points_from_text,
                  relief='flat', bg='#10b981', fg='white').grid(row=7, column=0, sticky='ew', padx=4, pady=2)

        # --- Buttons frame ---
        btns_frame = tk.Frame(self.left_panel, bg="#f8fafc")
        btns_frame.grid(row=8, column=0, sticky='ew', padx=4, pady=4)
        tk.Button(btns_frame, text="Start adding (R-click)",
                  command=lambda: messagebox.showinfo("Instrukcja",
                                                      "Prawym przyciskiem klikaj na płótnie aby dodać punkt graniczny."),
                  relief='flat').pack(side='left', expand=True, padx=2)
        tk.Button(btns_frame, text="Undo", command=self.undo_bound_point, relief='flat').pack(side='left', padx=2)
        tk.Button(btns_frame, text="Clear", command=self.clear_bound_points, relief='flat').pack(side='left', padx=2)

        # ---------------- Main container (toggle + canvas) ----------------
        self.main_container = tk.Frame(self.root, bg="#f1f5f9")
        self.main_container.grid(row=1, column=1, sticky="nsew", padx=8, pady=8)

        # main_container grid: row 0 = toggle_bar, row 1 = canvas (canvas rośnie)
        self.main_container.grid_rowconfigure(0, weight=0)  # toggle row
        self.main_container.grid_rowconfigure(1, weight=1)  # canvas row (grow)
        self.main_container.grid_columnconfigure(0, weight=1)

        self.show_velocity = True
        self.show_engines = True
        self.show_sensors = True

        # Toggle bar (używamy grid wewnątrz main_container, żeby nie mieszać z canvas grid)
        toggle_bar = tk.Frame(self.main_container, bg="#f1f5f9")
        toggle_bar.grid(row=0, column=0, sticky="ew", pady=(8, 12))
        toggle_bar.grid_columnconfigure(0, weight=1)

        center_grp = tk.Frame(toggle_bar, bg="#f1f5f9")
        center_grp.grid(row=0, column=0)

        # większe odstępy między przełącznikami i pogrubione etykiety
        self.toggle_speed = ToggleSwitch(center_grp, label="Prędkość", initial=self.show_velocity,
                                         command=self._on_toggle_speed)
        self.toggle_speed.pack(side="left", padx=16)

        self.toggle_engines = ToggleSwitch(center_grp, label="Silniki", initial=self.show_engines,
                                           command=self._on_toggle_engines)
        self.toggle_engines.pack(side="left", padx=16)

        self.toggle_sensors = ToggleSwitch(center_grp, label="Sensory", initial=self.show_sensors,
                                           command=self._on_toggle_sensors)
        self.toggle_sensors.pack(side="left", padx=16)

        tk.Frame(toggle_bar, bg="#f1f5f9").grid(row=0, column=1, sticky="e")  # right spacer

        # Canvas
        self.fig = Figure(figsize=(10, 8), facecolor='#f1f5f9', dpi=100)
        self.ax = self.fig.add_subplot(111, facecolor='white')
        self.ax.set_aspect('equal')
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.main_container)
        self.fig.canvas.mpl_connect('button_press_event', self.on_click)
        # canvas zajmuje row=1 w main_container
        self.canvas.get_tk_widget().grid(row=1, column=0, sticky="nsew")

        # Prawy panel
        self.right_panel = tk.Frame(self.root, bg="white", highlightbackground="#e2e8f0", highlightthickness=1)
        self.right_panel.grid(row=1, column=2, sticky="nsew")
        # (minsize ustawione na root.grid_columnconfigure powyżej)

        # Włącz grid w prawym panelu
        self.right_panel.grid_rowconfigure(0, weight=1)
        self.right_panel.grid_columnconfigure(0, weight=1)

        # InspectorPanel wypełnia cały panel
        self.inspector_panel = InspectorPanel(self.right_panel, on_center=self._center_on_object)
        self.inspector_panel.grid(row=0, column=0, sticky="nsew")

        # wymuszenie dopasowania scrollable canvas
        self.right_panel.update_idletasks()
        self.inspector_panel.canvas.configure(scrollregion=self.inspector_panel.canvas.bbox("all"))

        # ---------------- Initial draw ----------------
        self.update_frame()
        self.playback_loop()
        self.root.mainloop()




    # Toggle callbacks
    def _on_toggle_speed(self, state: bool):
        self.show_velocity = bool(state)
        self.update_frame()

    def _on_toggle_engines(self, state: bool):
        self.show_engines = bool(state)
        self.update_frame()

    def _on_toggle_sensors(self, state: bool):
        self.show_sensors = bool(state)
        self.update_frame()

    # ------------------------- helpers -------------------------
    def _ensure_axes(self):
        """Inicjalizacja osi raz (unikamy ax.clear() co klatkę)."""
        if not self._axes_initialized:
            self.ax.set_xlim(0, self.bx)
            self.ax.set_ylim(0, self.by)
            self.ax.grid(color='#e2e8f0', linestyle='--', linewidth=0.7)
            self._axes_initialized = True


    def _ensure_object_artists(self, oid):
        """Utwórz (tylko raz) kontenery artistów dla obiektu."""
        oid = str(oid)
        if oid in self._artists:
            return self._artists[oid]

        # strukturka domyślna
        d = {
            "shape": None,
            "vel": None,  # velocity arrow
            "vel_text": None,  # numeric speed/omega
            "heading": None,  # orientation arrow / heading indicator
            "omega": None,  # omega arc (existing)
            "omega_arrow": None,  # small arrow at arc end to show rotation dir
            "engines": [],
            "engine_texts": [],
            "engine_bases": [],  # small base markers for engines
            "vision_wedges": [],
            "scan_lines": [],
            "scan_hits": [],
            "scan_texts": [],
            "id_text": None,
        }

        self._artists[oid] = d
        return d

    def _maybe_update_axes_bounds(self):
        """Update axes limits if map size changed externally."""
        self.ax.set_xlim(0, self.bx)
        self.ax.set_ylim(0, self.by)

    def _center_on_object(self, obj):
        pos = obj.get("positionXY")
        if not pos:
            return

        x, y = float(pos[0]), float(pos[1])

        span = 20.0  # albo dynamicznie
        self.ax.set_xlim(x - span, x + span)
        self.ax.set_ylim(y - span, y + span)
        self.ax.figure.canvas.draw_idle()

    # ------------------------- preprocess -------------------------
    def _preprocess_frames(self):
        """
        Przygotowuje frames z polami:
          - obj['dynamic']
          - obj['derived']
        """
        world_init = self.world_init
        raw_frames = self.raw_frames
        base_objs = {}
        for o in world_init.get("objects", []):
            oid = o.get("id")
            if oid is None:
                continue
            base = copy.deepcopy(o)
            raw_shape = base.pop("shape", None)
            shape_local = normalize_shape(raw_shape) if raw_shape else None
            if shape_local:
                base["shape_local"] = shape_local

            base.setdefault("body_params", {})
            base.setdefault("engines", [])
            base.setdefault("sensors", [])
            base_objs[str(oid)] = base
        spec_idx = build_spec_indices(base_objs)
        frames_out = []
        for frame in raw_frames:
            if "objects" not in frame:
                frames_out.append({
                    "state_index": frame.get("state_index"),
                    "time": frame.get("time"),
                    "objects": []
                })
                continue

            new_objs = []
            for o in frame.get("objects", []):
                oid = str(o.get("id"))
                spec_bundle = spec_idx.get(oid, {})
                spec = spec_bundle.get("spec", {})
                eng_spec_map = spec_bundle.get("engines", {})
                sen_spec_map = spec_bundle.get("sensors", {})

                # dynamic: surowe pola z klatki
                # zrezygnowano z deepcopy jeśli nie mutujemy później
                dynamic = {
                    "positionXY": o.get("positionXY", [0.0, 0.0]),
                    "velocityXY": o.get("velocityXY", [0.0, 0.0]),
                    "theta": o.get("theta", 0.0),
                    "omega": o.get("omega", 0.0),
                    "static": bool(o.get("static", False)),
                    "destroyed": bool(o.get("destroyed", False)),
                    "removed": bool(o.get("removed", False)),
                    "engines_state": copy.deepcopy(o.get("engines", [])),
                    "sensors_state": copy.deepcopy(o.get("sensors", [])),
                }

                derived = {}

                # shape_world (prefer spec.shape_local, fallback na frame.shape)
                sl = spec.get("shape_local")
                if sl:
                    sw = transform_shape_local_to_global(
                        sl,
                        dynamic["positionXY"],
                        dynamic["theta"]
                    )

                    if isinstance(sw, dict):
                        derived["shape_world"] = sw
                    else:
                        raise TypeError(
                            f"transform_shape_local_to_global() should return dict, "
                            f"got {type(sw).__name__}: {sw!r}"
                        )

                # engines_world: compute using helper
                engines_world = []
                state_engs = {str(e.get("id")): e for e in dynamic["engines_state"]}
                for eid, es in eng_spec_map.items():
                    est = state_engs.get(eid)
                    engines_world.append(compute_engine_world(dynamic["positionXY"], dynamic["theta"], es, est))
                for sid, est in state_engs.items():
                    if sid not in eng_spec_map:
                        if est.get("positionXY"):
                            engines_world.append({
                                "id": est.get("id"),
                                "pos": est.get("positionXY"),
                                "thrust_vec": est.get("thrust_vector", [0, 0]),
                                "thrust": est.get("thrust", 0.0),
                            })
                derived["engines_world"] = engines_world

                # sensors_world
                sensors_world = []
                state_sens = {str(s.get("id")): s for s in dynamic["sensors_state"]}
                for sid, ss in sen_spec_map.items():
                    sst = state_sens.get(sid)
                    sensors_world.append(compute_sensor_world(dynamic["positionXY"], dynamic["theta"], ss, sst))
                for sid, sst in state_sens.items():
                    if sid not in sen_spec_map:
                        p = sst.get("positionXY", dynamic["positionXY"])
                        sensors_world.append({
                            "id": sst.get("id"),
                            "pos": p,
                            "vision": None,
                            "scan": sst.get("scan"),
                            "hit": None
                        })
                derived["sensors_world"] = sensors_world

                # velocity vector
                derived["velocity_vec"] = tuple(dynamic["velocityXY"])

                # omega arc
                if abs(dynamic["omega"]) > 1e-6:
                    r = 3.5 + min(abs(dynamic["omega"]), 2.0) * 1.2
                    span = 40 + min(abs(dynamic["omega"]), 2.0) * 40
                    center_angle = 90 if dynamic["omega"] > 0 else -90
                    theta1 = center_angle - span / 2
                    theta2 = center_angle + span / 2
                    derived["omega_arc"] = {
                        "center": tuple(dynamic["positionXY"]),
                        "r": r,
                        "theta1": theta1,
                        "theta2": theta2,
                    }
                else:
                    derived["omega_arc"] = None

                merged_obj = {
                    "id": o.get("id"),
                    "type": o.get("type", spec.get("type")),
                    "dynamic": dynamic,
                    "derived": derived,
                    "_spec_id": oid,
                }

                new_objs.append(merged_obj)

            frame_out = {
                "state_index": frame.get("state_index"),
                "time": frame.get("time"),
                "objects": new_objs
            }
            frames_out.append(frame_out)
        self.frames = frames_out
        self.base_objects = base_objs
        self.world_info = world_init.get("world", {})

    # ------------------------- estimate / UI glue -------------------------
    def estimate_boundaries(self):
        mx, my = 50, 50
        for f in self.frames:
            for o in f.get("objects", []):
                p = get_vec(o.get("dynamic", {}).get("positionXY") or o.get("positionXY") or [0, 0])
                mx = max(mx, p[0] * 1.2)
                my = max(my, p[1] * 1.2)
        return mx, my

    def apply_map_size(self):
        try:
            w = float(self.entry_map_w.get())
            h = float(self.entry_map_h.get())
            if w <= 0 or h <= 0:
                raise ValueError("Rozmiary muszą być dodatnie.")
            self.bx, self.by = w, h
            # update axes bounds (no full clear)
            self._maybe_update_axes_bounds()
            self.update_frame()
        except Exception as e:
            messagebox.showerror("Błąd", f"Niepoprawny rozmiar mapy: {e}")

    def load_points_from_text(self):
        raw = self.bound_text.get("1.0", tk.END)

        if not raw.strip():
            messagebox.showwarning("Brak danych", "Pole punktów jest puste.")
            return

        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list) and len(parsed) == 0:
                self.boundary_pts = []
                self.update_frame()
                messagebox.showinfo("Granice", "Punkty graniczne zostały wyczyszczone.")
                return
        except Exception:
            pass

        pts = []
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                for el in parsed:
                    if isinstance(el, (list, tuple)) and len(el) >= 2:
                        pts.append([float(el[0]), float(el[1])])
                    elif isinstance(el, dict):
                        x = el.get("x", el.get(0))
                        y = el.get("y", el.get(1))
                        if x is not None and y is not None:
                            pts.append([float(x), float(y)])
        except Exception:
            pass

        if not pts:
            for i, line in enumerate(raw.splitlines(), start=1):
                line = line.strip()
                if not line:
                    continue
                for sep in [",", ";", "\t"]:
                    line = line.replace(sep, " ")
                parts = [p for p in line.split(" ") if p]
                if len(parts) < 2:
                    continue
                try:
                    x = float(parts[0])
                    y = float(parts[1])
                    pts.append([x, y])
                except ValueError:
                    continue

        if not pts:
            messagebox.showerror(
                "Błąd wczytywania",
                "Nie udało się odczytać punktów.\n\n"
                "Poprawne formaty:\n0,0\n50,0\n50,50\n0,50\n\n"
                "lub JSON:\n[[0,0],[50,0],[50,50],[0,50]]"
            )
            return

        self.boundary_pts = pts
        maxx = max(p[0] for p in pts)
        maxy = max(p[1] for p in pts)
        if maxx > self.bx or maxy > self.by:
            self.bx = max(self.bx, maxx)
            self.by = max(self.by, maxy)
            self.entry_map_w.delete(0, tk.END)
            self.entry_map_w.insert(0, str(int(self.bx)))
            self.entry_map_h.delete(0, tk.END)
            self.entry_map_h.insert(0, str(int(self.by)))
        self._maybe_update_axes_bounds()
        self.update_frame()

    def undo_bound_point(self):
        if self.boundary_pts:
            self.boundary_pts.pop()
            self.update_frame()

    def clear_bound_points(self):
        self.boundary_pts = []
        self.update_frame()

    def toggle_play(self):
        self.playing = not self.playing
        self.btn_play.config(text="⏸ PAUSE" if self.playing else "▶ PLAY", bg="#ef4444" if self.playing else "#4f46e5")

    def prev_frame(self):
        self.idx = max(0, self.idx - self.play_speed)
        self.slider.set(self.idx)
        self.update_frame()

    def next_frame(self):
        self.idx = min(len(self.frames) - 1, self.idx + self.play_speed)
        self.slider.set(self.idx)
        self.update_frame()

    def on_slider(self, val):
        self.idx = int(val)
        self.update_frame()

    def change_speed(self, factor):
        self.play_speed *= factor
        self.play_speed = max(1, min(128, int(self.play_speed)))  # minimalnie 1 klatka, maksymalnie 128
        self.lbl_speed.config(text=f"{self.play_speed}x")

    def playback_loop(self):
        delay = 700  # stałe opóźnienie

        if self.playing and self.idx < len(self.frames) - 1:
            self.idx = min(len(self.frames) - 1, self.idx + self.play_speed)
            self.slider.set(self.idx)

        self.root.after(delay, self.playback_loop)  # type: ignore[misc]

    def on_click(self, event):
        if event.xdata is None or event.ydata is None: return
        if getattr(event, "button", None) == 3:
            # dodawanie punktów granicznych
            self.boundary_pts.append([float(event.xdata), float(event.ydata)])
            if event.xdata > self.bx or event.ydata > self.by:
                self.bx = max(self.bx, event.xdata)
                self.by = max(self.by, event.ydata)
                self.entry_map_w.delete(0, tk.END)
                self.entry_map_w.insert(0, str(int(self.bx)))
                self.entry_map_h.delete(0, tk.END)
                self.entry_map_h.insert(0, str(int(self.by)))
                self._maybe_update_axes_bounds()
            self.update_frame()
            return

        best_id, min_d = None, 5.0
        if not self.frames:
            return
        for o in self.frames[self.idx].get("objects", []):
            dyn = o.get("dynamic", {})
            if dyn.get("removed"):
                continue
            p = get_vec(dyn.get("positionXY", [0, 0]))
            d = math.hypot(event.xdata - p[0], event.ydata - p[1])
            if d < min_d: min_d, best_id = d, o["id"]

        if best_id:
            self.selected_id = best_id
            # synchronizacja z lewym panelem
            self._sync_list_selection()
            self.update_frame()

    def _sync_list_selection(self):
        """Zaznacza w Listbox aktualnie wybrany obiekt."""
        if not self.selected_id:
            return
        try:
            idx = self._cached_obj_list_ids.index(str(self.selected_id))
            self.obj_list.selection_clear(0, tk.END)
            self.obj_list.selection_set(idx)
            self.obj_list.activate(idx)
            self.obj_list.see(idx)
        except Exception:
            pass


    def on_list_select(self, event):
        sel = self.obj_list.curselection()
        if sel:
            self.selected_id = self.obj_list.get(sel[0])
            self.update_frame()

    def _hide_artists_for(self, oid):
        a = self._artists.get(str(oid))
        if not a:
            return
        for v in a.values():
            if isinstance(v, list):
                for it in v:
                    try:
                        it.set_visible(False)
                    except Exception:
                        pass
            elif v is not None:
                try:
                    v.set_visible(False)
                except Exception:
                    pass



    # ------------------------- main render loop (optimized) -------------------------
    def update_frame(self):
        if not self.frames:
            return
        f = self.frames[self.idx]
        self._ensure_axes()
        self.ax.set_title(
            f"KLATKA: {self.idx} | CZAS: {f.get('time', 0.0):.6f}s",
            color="#475569",
            fontsize=12,
            fontweight='bold',
            pad=20
        )
        objs = f.get("objects", [])
        self._hide_removed_objects(objs)
        self._validate_selection(objs)
        self._rebuild_obj_list(objs)
        self._render_objects(objs)
        self._update_boundaries()
        self.fig.canvas.draw_idle()

    # --- helper methods ---

    def _hide_removed_objects(self, objs):
        for o in objs:
            dyn = o.get("dynamic", {})
            removed = bool(dyn.get("removed", o.get("removed", False)))
            if removed:
                self._hide_artists_for(o.get("id"))

    def _validate_selection(self, objs):
        valid_ids = {
            str(o.get("id")) for o in objs
            if not (o.get("dynamic", {}).get("removed", o.get("removed", False)))
        }
        if self.selected_id not in valid_ids:
            self.selected_id = None
            try:
                self.inspector_panel.clear()
            except Exception:
                pass
            self._last_inspector_id = None

    def _rebuild_obj_list(self, objs):
        curr_ids = [str(o.get("id")) for o in objs if
                    not (o.get("dynamic", {}).get("removed", o.get("removed", False)))]
        if curr_ids != self._cached_obj_list_ids:
            self.obj_list.delete(0, tk.END)
            for i, oid in enumerate(curr_ids):
                self.obj_list.insert(tk.END, oid)
            # try keep selection
            if self.selected_id:
                try:
                    idx = curr_ids.index(str(self.selected_id))
                    self.obj_list.selection_set(idx)
                    self.obj_list.activate(idx)
                except ValueError:
                    pass
            self._cached_obj_list_ids = curr_ids

    def _render_object_active(self, o, dyn, der, artists, ox, oy):
        destroyed = bool(dyn.get("destroyed", o.get("destroyed", False)))
        color = "#ef4444" if destroyed else "#4f46e5"

        # shape (zawsze)
        self._render_shape(artists, der.get("shape_world"), ox, oy, color, active=True)

        # heading (zawsze)
        self._render_heading(artists, dyn, o, ox, oy)

        # jeśli obiekt jest destroyed — ukryj wszystkie dodatkowe elementy
        if destroyed:
            for key in ["engines", "engine_bases", "engine_texts",
                        "vel", "vel_text", "omega_arc", "omega_arrow",
                        "vision_wedges", "scan_lines", "scan_hits", "scan_texts"]:
                val = artists.get(key)
                if val is None:
                    continue
                if isinstance(val, list):
                    for a in val:
                        try:
                            a.set_visible(False)
                        except Exception:
                            pass
                else:
                    try:
                        val.set_visible(False)
                    except Exception:
                        pass

            # ID label pozostaje widoczny
            self._render_id_label(artists, o, ox, oy)
            # inspector
            self._update_inspector_for(o)
            return

        # === normalne renderowanie dla nie-destroyed ===
        # engines
        if self.show_engines:
            self._render_engines_block(artists, der.get("engines_world", []), o, ox, oy)
        else:
            for eng_arrow in artists.get("engines", []):
                try:
                    eng_arrow.set_visible(False)
                except Exception:
                    pass
            for base in artists.get("engine_bases", []):
                try:
                    base.set_visible(False)
                except Exception:
                    pass
            for txt in artists.get("engine_texts", []):
                try:
                    txt.set_visible(False)
                except Exception:
                    pass

        # velocity + omega
        if self.show_velocity:
            self._render_velocity(artists, der, dyn, *get_vec(dyn.get("velocityXY", [0, 0])), ox, oy)
            self._render_omega(artists, dyn, ox, oy)
            self._render_world_vel_omega_label(artists, der, dyn, *get_vec(dyn.get("velocityXY", [0, 0])), ox, oy)
        else:
            for key in ["vel", "vel_text", "omega_arc", "omega_arrow"]:
                val = artists.get(key)
                if val is None: continue
                try:
                    val.set_visible(False)
                except Exception:
                    pass

        # sensors
        if self.show_sensors:
            self._render_sensors_block(artists, der.get("sensors_world", []), ox, oy)
        else:
            for key in ["vision_wedges", "scan_lines", "scan_hits", "scan_texts"]:
                for a in artists.get(key, []):
                    try:
                        a.set_visible(False)
                    except Exception:
                        pass

        # ID label
        self._render_id_label(artists, o, ox, oy)
        # inspector
        self._update_inspector_for(o)

    def _render_object_inactive(self, o, dyn, der, artists, ox, oy):
        destroyed = bool(dyn.get("destroyed", o.get("destroyed", False)))
        color = "#ef4444" if destroyed else "#38bdf8"  # inactive color

        # shape
        self._render_shape(artists, der.get("shape_world"), ox, oy, color, active=False)

        # heading grot (always visible)
        self._render_heading(artists, dyn, o, ox, oy)

        # hide all extras except heading
        for key in ["engines", "engine_bases", "engine_texts", "vel", "vel_text",
                    "omega_arc", "omega_arrow", "vision_wedges", "scan_lines", "scan_hits", "scan_texts"]:
            val = artists.get(key)
            if val is None:
                continue
            if isinstance(val, list):
                for a in val:
                    try:
                        a.set_visible(False)
                    except Exception:
                        pass
            else:
                try:
                    val.set_visible(False)
                except Exception:
                    pass

        # ID label
        self._render_id_label(artists, o, ox, oy)

    def _render_objects(self, objs):
        for o in objs:
            dyn = o.get("dynamic", {})
            der = o.get("derived", {})

            ox, oy = get_vec(dyn.get("positionXY", o.get("positionXY", [0, 0])))
            removed = bool(dyn.get("removed", o.get("removed", False)))
            if removed:
                self._hide_artists_for(o.get("id"))
                continue

            oid = str(o.get("id"))
            active = oid == str(self.selected_id)
            artists = self._ensure_object_artists(oid)

            if active:
                self._render_object_active(o, dyn, der, artists, ox, oy)
            else:
                self._render_object_inactive(o, dyn, der, artists, ox, oy)

    def _render_shape(self, artists, shape, ox, oy, color, active):
        if shape:
            st = shape.get("type")
            if st == "circle":
                r = float(shape.get("r", 1.0))
                cx, cy = tuple(shape.get("center", (ox, oy)))
                if artists["shape"] is None:
                    c = Circle((cx, cy), r, ec=color, fc=color,
                               alpha=0.45 if active else 0.15,
                               lw=2.5 if active else 1.2, zorder=10)
                    self.ax.add_patch(c)
                    artists["shape"] = c
                else:
                    c = artists["shape"]
                    c.set_edgecolor(color)
                    c.set_facecolor(color)
                    c.set_alpha(0.45 if active else 0.15)
                    c.set_linewidth(2.5 if active else 1.2)
                    c.center = (cx, cy)
                    try:
                        c.set_radius(float(r))
                    except Exception:
                        pass
                artists["shape"].set_visible(True)
            elif st == "polygon":
                pts = shape.get("points", [])
                if len(pts) >= 3:
                    poly_pts = [(float(x), float(y)) for x, y in pts]
                    if artists["shape"] is None:
                        P = Polygon(poly_pts, closed=True, ec=color, fc=color,
                                    alpha=0.45 if active else 0.15,
                                    lw=2.5 if active else 1.2, zorder=10)
                        self.ax.add_patch(P)
                        artists["shape"] = P
                    else:
                        P = artists["shape"]
                        P.set_edgecolor(color)
                        P.set_facecolor(color)
                        P.set_alpha(0.45 if active else 0.15)
                        P.set_linewidth(2.5 if active else 1.2)
                        try:
                            P.set_xy(poly_pts)
                        except Exception:
                            pass
                    artists["shape"].set_visible(True)
        else:
            if artists["shape"] is not None:
                artists["shape"].set_visible(False)

    def _render_engines_block(self, artists, engs, o, ox, oy):
        # ensure arrays length
        while len(artists["engines"]) < len(engs):
            # strzałka silnika
            arr = FancyArrowPatch((0, 0), (0, 0), arrowstyle='-|>', color='#b91c1c',
                                  lw=0.8, mutation_scale=5, alpha=0.8, zorder=13)
            self.ax.add_patch(arr)
            artists["engines"].append(arr)

            # podstawa silnika - czerwone obramowanie, umiarkowana grubość
            base = Circle((0, 0), 0.18, ec='red', fc='white', lw=1.2, zorder=14)
            self.ax.add_patch(base)
            artists["engine_bases"].append(base)

            # tekst silnika - tylko T=..., mniejszy, subtelny
            txt = self.ax.text(0, 0, "", fontsize=7, fontweight='bold',
                               color='#b91c1c', ha="left", va="center", zorder=20)
            txt.set_path_effects([
                pe.Stroke(linewidth=0.8, foreground='white'),
                pe.Normal()
            ])
            artists["engine_texts"].append(txt)

        # hide unused extras
        for i in range(len(engs), len(artists["engines"])):
            artists["engines"][i].set_visible(False)
            artists["engine_bases"][i].set_visible(False)
            artists["engine_texts"][i].set_visible(False)

        for ei, eng in enumerate(engs):
            ex, ey = tuple(eng.get("pos", (ox, oy)))
            tx, ty = tuple(eng.get("thrust_vec", (0.0, 0.0)))
            thrust_val = float(eng.get("thrust", 0.0)) or 0.0

            # display vector: scale thrust_vec by visual factor
            t = min(abs(thrust_val), 1.0)
            vec_norm = math.hypot(tx, ty)
            if vec_norm < 1e-9:
                ux, uy = math.cos(o.get("dynamic", {}).get("theta", 0.0)), math.sin(
                    o.get("dynamic", {}).get("theta", 0.0))
                dx, dy = ux * 0.6, uy * 0.6
            else:
                MAX_LEN = 0.9
                MIN_LEN = 0.25
                display_len = MIN_LEN + (MAX_LEN - MIN_LEN) * math.sqrt(t)
                dx, dy = tx * display_len, ty * display_len

            # aktualizacja strzałki silnika - umiarkowany czerwony
            a = artists["engines"][ei]
            a.set_positions((ex, ey), (ex + dx, ey + dy))
            a.set_visible(True)
            a.set_edgecolor('#b91c1c')
            a.set_facecolor('#b91c1c')
            a.set_linewidth(0.8 + 0.8 * t)
            a.set_mutation_scale(5 + 5 * t)
            a.set_alpha(0.8)

            # aktualizacja podstawy silnika
            base = artists["engine_bases"][ei]
            base.center = (ex, ey)
            base.set_visible(True)
            base.set_edgecolor('red')
            base.set_linewidth(1.2)

            # tekst silnika - tylko T=..., mniejszy, subtelny
            try:
                norm_v = math.hypot(dx, dy) + 1e-9
                nx, ny = -dy / norm_v, dx / norm_v
                side = 1 if (ei % 2 == 0) else -1
                offset = 0.35 + 0.2 * min(norm_v, 2.0)
                lx = ex + dx + nx * offset * side
                ly = ey + dy + ny * offset * side
                ttxt = artists["engine_texts"][ei]
                ttxt.set_position((lx, ly))
                ttxt.set_text(f"T={thrust_val:.2f}")  # tylko T=...
                ttxt.set_fontsize(7)
                ttxt.set_fontweight('bold')
                ttxt.set_color('#b91c1c')
                ttxt.set_path_effects([
                    pe.Stroke(linewidth=0.8, foreground='white'),
                    pe.Normal()
                ])
                ttxt.set_visible(True)
            except Exception:
                artists["engine_texts"][ei].set_visible(False)

    def _render_heading(self, artists, dyn, o, ox, oy):
        theta = float(dyn.get("theta", o.get("theta", 0.0)) or 0.0)
        hlen = 1.2
        hx = ox + math.cos(theta) * hlen
        hy = oy + math.sin(theta) * hlen
        if artists["heading"] is None:
            head = FancyArrowPatch((ox, oy), (hx, hy), arrowstyle='-|>', color='#334155',
                                   lw=1.0, mutation_scale=10, zorder=7)
            self.ax.add_patch(head)
            artists["heading"] = head
        else:
            artists["heading"].set_positions((ox, oy), (hx, hy))
            artists["heading"].set_visible(True)

    def _render_velocity(self, artists, der, dyn, vx, vy, ox, oy):
        vxv, vyv = der.get("velocity_vec", tuple(dyn.get("velocityXY", (vx, vy))))
        speed = math.hypot(vxv, vyv)

        if speed > 0.02:
            # skala strzałki
            vscale = 0.35 + min(speed, 5.0) * 0.15  # zmniejszone z 0.6 + 0.25*speed
            vxp, vyp = vxv * vscale, vyv * vscale
            if artists["vel"] is None:
                v_arr = FancyArrowPatch((ox, oy), (ox + vxp, oy + vyp),
                                        arrowstyle='->', color='#06b6d4', lw=1.2,
                                        mutation_scale=8 + min(speed, 5.0) * 3, zorder=8)  # mniejsze mutation_scale
                self.ax.add_patch(v_arr)
                artists["vel"] = v_arr
            else:
                artists["vel"].set_positions((ox, oy), (ox + vxp, oy + vyp))
                artists["vel"].set_visible(True)

    def _render_omega(self, artists, dyn, ox, oy):
        omega_val = float(dyn.get("omega", 0.0))

        if abs(omega_val) > 0.01:
            radius = 1.4
            max_span = math.radians(160)
            span = min(abs(omega_val) * 0.8, max_span)
            ccw = omega_val > 0
            base_ang = math.pi / 2

            if ccw:
                theta1 = math.degrees(base_ang)
                theta2 = math.degrees(base_ang + span)
                end_ang = base_ang + span
            else:
                theta1 = math.degrees(base_ang - span)
                theta2 = math.degrees(base_ang)
                end_ang = base_ang - span

            if artists.get("omega_arc") is None:
                arc = Arc(
                    (ox, oy),
                    radius * 2, radius * 2,
                    theta1=theta1,
                    theta2=theta2,
                    lw=2.2,
                    color="#f59e0b",
                    alpha=0.85,
                    zorder=8
                )
                self.ax.add_patch(arc)
                artists["omega_arc"] = arc
            else:
                arc = artists["omega_arc"]
                arc.center = (ox, oy)
                arc.theta1 = theta1
                arc.theta2 = theta2
                arc.set_visible(True)

            t = end_ang
            tx, ty = -math.sin(t), math.cos(t)
            if not ccw:
                tx, ty = -tx, -ty

            x0 = ox + math.cos(t) * radius
            y0 = oy + math.sin(t) * radius
            x1 = x0 + tx * 0.45
            y1 = y0 + ty * 0.45

            if artists.get("omega_arrow") is None:
                oa = FancyArrowPatch(
                    (x0, y0), (x1, y1),
                    arrowstyle='-|>',
                    color="#f59e0b",
                    lw=1.6,
                    mutation_scale=14,
                    alpha=0.9,
                    zorder=9
                )
                self.ax.add_patch(oa)
                artists["omega_arrow"] = oa
            else:
                artists["omega_arrow"].set_positions((x0, y0), (x1, y1))
                artists["omega_arrow"].set_visible(True)
        else:
            if artists.get("omega_arc") is not None:
                artists["omega_arc"].set_visible(False)
            if artists.get("omega_arrow") is not None:
                artists["omega_arrow"].set_visible(False)

    def _render_sensors_block(self, artists, vis_list, ox, oy):
        # ensure enough wedge/line/hit artists
        while len(artists["vision_wedges"]) < len(vis_list):
            w = Wedge((0, 0), 0, 0, 0, fc='#10b981', alpha=0.035, zorder=1)
            self.ax.add_patch(w)
            artists["vision_wedges"].append(w)
        while len(artists["scan_lines"]) < len(vis_list):
            ln = Line2D([0, 0], [0, 0], linestyle='--', linewidth=1.2, color="#f43f5e", zorder=11)
            self.ax.add_line(ln)
            artists["scan_lines"].append(ln)
            hitc = Circle((0, 0), 0.35, color="#f43f5e", zorder=12)
            self.ax.add_patch(hitc)
            artists["scan_hits"].append(hitc)
            txt = self.ax.text(0, 0, "", fontsize=7.2, color="#7f1d1d", ha="center", va="center", zorder=20,
                               bbox=dict(fc="white", ec="#f43f5e", alpha=0.95, pad=0.4))
            artists["scan_texts"].append(txt)

        for si, s in enumerate(vis_list):
            vis = s.get("vision")
            pos = s.get("pos", (ox, oy))
            sx, sy = float(pos[0]), float(pos[1])
            w = artists["vision_wedges"][si]
            if vis:
                try:
                    r_max = float(vis.get("max_range", 0.0))
                    a_start = float(vis.get("angle_start", 0.0))
                    a_end = float(vis.get("angle_end", a_start + 2 * math.pi))
                except Exception:
                    w.set_visible(False)
                else:
                    delta = (a_end - a_start) % (2 * math.pi)
                    if r_max <= 0:
                        w.set_visible(False)
                    elif delta <= 1e-9 or delta >= 2 * math.pi - 1e-6:
                        w.set_center((sx, sy))
                        w.set_radius(r_max)
                        w.set_theta1(0)
                        w.set_theta2(360)
                        w.set_visible(True)
                    else:
                        w.set_center((sx, sy))
                        w.set_theta1(math.degrees(a_start))
                        w.set_theta2(math.degrees(a_start + delta))
                        w.set_radius(r_max)
                        w.set_visible(True)
            else:
                w.set_visible(False)

            scan = s.get("scan")
            hit = s.get("hit")
            ln = artists["scan_lines"][si]
            hitc = artists["scan_hits"][si]
            txt = artists["scan_texts"][si]
            if hit and isinstance(hit, (list, tuple)) and len(hit) >= 2:
                hx, hy = float(hit[0]), float(hit[1])
                dx, dy = hx - sx, hy - sy
                dist = math.hypot(dx, dy)
                global_ang = math.atan2(dy, dx)
                ln.set_data([sx, hx], [sy, hy])
                ln.set_visible(True)
                hitc.center = (hx, hy)
                try:
                    hitc.set_radius(0.35)
                except Exception:
                    pass
                hitc.set_visible(True)
                nx, ny = -math.sin(global_ang), math.cos(global_ang)
                side = 1 if (si % 2 == 0) else -1
                label_offset = 0.6 + 0.25 * min(dist, 2.0)
                lx = hx + nx * label_offset * side
                ly = hy + ny * label_offset * side
                txt.set_position((lx, ly))
                sid = s.get("id") or s.get("name") or f"sensor_{si}"
                txt.set_text(f"{sid}\nd={dist:.2f}")
                txt.set_visible(True)
            elif scan:
                if isinstance(scan, (list, tuple)) and len(scan) >= 2:
                    global_ang = float(scan[0])
                    dist = float(scan[1])
                elif isinstance(scan, dict):
                    global_ang = float(scan.get("angle", 0.0))
                    dist = float(scan.get("dist", 0.0))
                else:
                    ln.set_visible(False)
                    hitc.set_visible(False)
                    txt.set_visible(False)
                    continue
                if dist <= 1e-9:
                    ln.set_visible(False)
                    hitc.set_visible(False)
                    txt.set_visible(False)
                    continue
                hx = sx + math.cos(global_ang) * dist
                hy = sy + math.sin(global_ang) * dist
                ln.set_data([sx, hx], [sy, hy])
                ln.set_visible(True)
                hitc.center = (hx, hy)
                hitc.set_visible(True)
                nx, ny = -math.sin(global_ang), math.cos(global_ang)
                side = 1 if (si % 2 == 0) else -1
                label_offset = 0.6 + 0.25 * min(dist, 2.0)
                lx = hx + nx * label_offset * side
                ly = hy + ny * label_offset * side
                txt.set_position((lx, ly))
                sid = s.get("id") or s.get("name") or f"sensor_{si}"
                txt.set_text(f"{sid}\nd={dist:.2f}")
                txt.set_visible(True)
            else:
                ln.set_visible(False)
                hitc.set_visible(False)
                txt.set_visible(False)

    def _render_id_label(self, artists, o, ox, oy):
        if artists["id_text"] is None:
            t = self.ax.text(ox, oy - 2.5, str(o.get("id")),
                             fontsize=9, ha="center", zorder=15)
            artists["id_text"] = t
        else:
            artists["id_text"].set_position((ox, oy - 2.5))
            artists["id_text"].set_text(str(o.get("id")))
        artists["id_text"].set_visible(True)

    def _render_world_vel_omega_label(self, artists, der, dyn, vx, vy, ox, oy):
        omega_val = float(dyn.get("omega", 0.0))
        vxv, vyv = der.get("velocity_vec", tuple(dyn.get("velocityXY", (vx, vy))))
        speed_val = math.hypot(vxv, vyv)
        if speed_val > 0.01 or abs(omega_val) > 0.01:
            if artists["vel_text"] is None:
                vt = self.ax.text(ox + 2.2, oy + 2.2, f"v = {speed_val:.2f}\nω = {omega_val:.2f}",
                                  fontsize=7.6, color="#334155", ha="left", va="bottom", zorder=18,
                                  bbox=dict(fc="white", ec="#94a3b8", alpha=0.9, pad=0.35))
                artists["vel_text"] = vt
            else:
                vt = artists["vel_text"]
                vt.set_position((ox + 2.2, oy + 2.2))
                vt.set_text(f"v = {speed_val:.2f}\nω = {omega_val:.2f}")
                vt.set_visible(True)
        else:
            if artists.get("vel_text") is not None:
                artists["vel_text"].set_visible(False)

    def _update_inspector_for(self, o):
        if self._last_inspector_id == str(o.get("id")) and self._last_inspector_frame == self.idx:
            return
        try:
            dyn = o.get("dynamic", {})
            spec = self.base_objects.get(str(o.get("_spec_id")), {})

            # --- build engine map from spec ---
            spec_engines = spec.get("engines", []) or []
            spec_eng_map = {str(e.get("id")): e for e in spec_engines if e.get("id") is not None}

            merged_engines = []
            for st in dyn.get("engines_state", []) or []:
                sid = str(st.get("id")) if st.get("id") is not None else None
                spec_e = spec_eng_map.get(sid, {}) if sid is not None else {}
                merged = {}
                merged.update(spec_e)
                merged.update(st)
                merged_engines.append(merged)

            # --- sensors ---
            spec_sensors = spec.get("sensors", []) or []
            spec_sen_map = {str(s.get("id")): s for s in spec_sensors if s.get("id") is not None}

            merged_sensors = []
            for ss in dyn.get("sensors_state", []) or []:
                sid = str(ss.get("id")) if ss.get("id") is not None else None
                spec_s = spec_sen_map.get(sid, {}) if sid is not None else {}
                merged_s = {}
                merged_s.update(spec_s)
                merged_s.update(ss)
                merged_sensors.append(merged_s)

            view = {
                "id": o.get("id"),
                "positionXY": dyn.get("positionXY"),
                "velocityXY": dyn.get("velocityXY"),
                "theta": dyn.get("theta", 0.0),
                "omega": dyn.get("omega", 0.0),
                "destroyed": dyn.get("destroyed", False),
                "removed": dyn.get("removed", False),
                "body_params": spec.get("body_params", {}),
                "engines": merged_engines,
                "sensors": merged_sensors,
            }

            self.inspector_panel.update_view(view)
            self._last_inspector_id = str(o.get("id"))
            self._last_inspector_frame = self.idx
        except Exception:
            pass

    def _update_boundaries(self):
        if self.boundary_pts:
            bkey = "__bounds__"
            if bkey not in self._artists:
                self._artists[bkey] = {"shape": None}
            if self._artists[bkey].get("shape") is None:
                try:
                    poly = Polygon(self.boundary_pts, closed=True, ec='#0f172a', fc='#94a3b8', alpha=0.12, zorder=2,
                                   linewidth=1.4)
                    self.ax.add_patch(poly)
                    self._artists[bkey]["shape"] = poly
                except Exception:
                    pass
            else:
                try:
                    poly = self._artists[bkey]["shape"]
                    poly.set_xy(self.boundary_pts)
                    poly.set_visible(True)
                except Exception:
                    pass
        else:
            if "__bounds__" in self._artists and self._artists["__bounds__"].get("shape") is not None:
                self._artists["__bounds__"]["shape"].set_visible(False)


if __name__ == "__main__":
    root = tk.Tk()
    root.withdraw()

    try:
        file_pth = filedialog.askopenfilename(
            title="Wybierz log symulacji",
            filetypes=[("Simulator JSONL logs", "*.jsonl"), ("All files", "*.*")]
        )

        if not file_pth:
            root.destroy()
        else:
            with open(file_pth, "r", encoding="utf-8") as f:
                content_data = [json.loads(line) for line in f if line.strip()]

            root.destroy()
            SimReplayerPy(content_data)

    except Exception as e:
        try:
            root.destroy()
        except Exception:
            pass
        messagebox.showerror("Błąd", str(e))
