import tkinter as tk
from tkinter import ttk, messagebox
import json
import math
import ctypes

def _fmt_vec(v):
    if isinstance(v, (list, tuple)) and len(v) >= 2:
        return f"({float(v[0]):.2f}, {float(v[1]):.2f})"
    if isinstance(v, dict):
        return f"({float(v.get('x',0)):.2f}, {float(v.get('y',0)):.2f})"
    return str(v)

# --- DPI fix for Windows ---
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    pass

class InspectorPanel(tk.Frame):
    def __init__(self, master, on_center=None, **kwargs):
        super().__init__(master, bg="#f1f5f9", **kwargs)
        self._on_center = on_center
        self._current_obj = None

        self.colors = {
            "bg": "#f1f5f9",
            "card": "#ffffff",
            "text": "#1e293b",
            "muted": "#64748b",
            "indigo": "#4f46e5",
            "emerald": "#10b981",
            "amber": "#f59e0b",
            "red": "#ef4444",
            "gray": "#cbd5e1"
        }
        self.font_base = 10
        self._build_ui()

    def _build_ui(self):
        # ---------------- Scrollable Canvas ----------------
        self.canvas = tk.Canvas(self, bg=self.colors["bg"], highlightthickness=0)
        self.scrollbar = tk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.scrollbar.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)

        self.scrollable_frame = tk.Frame(self.canvas, bg=self.colors["bg"])
        self.window_id = self.canvas.create_window((0,0), window=self.scrollable_frame, anchor="nw")

        # Dynamic scrollregion and width
        self.scrollable_frame.bind("<Configure>", self._on_frame_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)

        # Mouse wheel support
        self.scrollable_frame.bind("<Enter>", lambda e: self.canvas.bind_all(
            "<MouseWheel>", self._on_mousewheel if self.scrollbar.winfo_ismapped() else lambda e: None))
        self.scrollable_frame.bind("<Leave>", lambda e: self.canvas.unbind_all("<MouseWheel>"))

        parent = self.scrollable_frame

        # ---------------- Header ----------------
        header = tk.Frame(parent, bg=self.colors["card"], padx=16, pady=12,
                          highlightthickness=1, highlightbackground=self.colors["indigo"])
        header.pack(fill="x", padx=12, pady=(12,6))
        top_row = tk.Frame(header, bg=self.colors["card"])
        top_row.pack(fill="x")
        tk.Label(top_row, text="INSPECTOR", font=("Inter", self.font_base, "bold"),
                 fg=self.colors["muted"], bg=self.colors["card"]).pack(side="left", anchor="w")
        btns = tk.Frame(top_row, bg=self.colors["card"])
        btns.pack(side="right", anchor="e")
        tk.Button(btns, text="Kopiuj JSON", command=self._copy_json,
                  bg=self.colors["indigo"], fg="white", relief="flat", font=("Inter",self.font_base)).pack(side="left", padx=(0,6))
        tk.Button(btns, text="Pokaż surowe", command=self._show_raw, relief="flat",
                  font=("Inter",self.font_base)).pack(side="left", padx=(0,6))
        self.btn_center = tk.Button(btns, text="Wycentruj", command=self._center_request,
                                    relief="flat", font=("Inter",self.font_base))
        self.btn_center.pack(side="left")
        self.lbl_id = tk.Label(header, text="ID: -", font=("JetBrains Mono", self.font_base+4, "bold"),
                               fg=self.colors["indigo"], bg=self.colors["card"])
        self.lbl_id.pack(anchor="w", pady=(8,0))

        # ---------------- Cards ----------------
        self.dyn_card = self._create_card("Dynamics", self.colors["indigo"], parent)
        self.props_table = {}
        fields = ["positionXY","velocityXY","speed","theta","omega","mass","I","drag_lin_forward","drag_lin_side","drag_rot","destroyed"]
        for f in fields:
            row = tk.Frame(self.dyn_card, bg=self.colors["card"])
            row.pack(fill="x", pady=4)
            tk.Label(row, text=f, font=("Inter", self.font_base), fg=self.colors["muted"], bg=self.colors["card"]).pack(side="left")
            val = tk.Label(row, text="-", font=("JetBrains Mono", self.font_base, "bold"), fg=self.colors["text"], bg=self.colors["card"])
            val.pack(side="right")
            self.props_table[f] = val

        self.eng_card = self._create_card("Engines", self.colors["emerald"], parent)
        self.eng_card.pack_propagate(True)  # <-- ustawiamy raz
        self.eng_container = tk.Frame(self.eng_card, bg=self.colors["card"])
        self.eng_container.pack(fill="x", pady=4)

        self.sens_card = self._create_card("Sensors", self.colors["amber"], parent)
        style = ttk.Style()
        style.configure("Treeview", font=("Inter", self.font_base), rowheight=self.font_base*3)
        self.sensors_tv = ttk.Treeview(self.sens_card, columns=("cat","scan"), show="headings", height=6)
        self.sensors_tv.heading("cat", text="Category")
        self.sensors_tv.heading("scan", text="Scan")
        self.sensors_tv.column("cat", width=100)
        self.sensors_tv.column("scan", width=250)
        self.sensors_tv.pack(fill="both", expand=True, pady=2)

    # ---------------- Scroll handling ----------------
    def _on_frame_configure(self, event):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        bbox = self.canvas.bbox("all")
        if bbox and bbox[3] > self.canvas.winfo_height():
            self.scrollbar.pack(side="right", fill="y")
        else:
            self.scrollbar.pack_forget()

    def _on_canvas_configure(self, event):
        self.canvas.itemconfig(self.window_id, width=event.width)

    def _on_mousewheel(self, event):
        self.canvas.yview_scroll(int(-1*(event.delta/120)), "units")

    # ---------------- Card creation ----------------
    def _create_card(self, title, accent_color, parent):
        container = tk.Frame(parent, bg=self.colors["card"], padx=12, pady=8,
                             highlightthickness=1, highlightbackground=self.colors["indigo"])
        container.pack(fill="x", padx=12, pady=6)
        title_row = tk.Frame(container, bg=self.colors["card"])
        title_row.pack(fill="x", pady=(0,6))
        tk.Frame(title_row, bg=accent_color, width=4, height=14).pack(side="left")
        tk.Label(title_row, text=title.upper(), font=("Inter", self.font_base-2, "bold"),
                 fg=self.colors["muted"], bg=self.colors["card"], padx=6).pack(side="left")
        return container

    # ---------------- Update / Actions ----------------
    def update_view(self,obj):
        if not obj:
            self.clear()
            return
        self._current_obj = obj
        self.lbl_id.config(text=f"ID: {obj.get('id','-')}")

        pos = obj.get("positionXY", obj.get("position","-"))
        vel = obj.get("velocityXY", obj.get("velocity",[0,0]))
        vx,vy = (0.0,0.0)
        if isinstance(vel,(list,tuple)) and len(vel)>=2:
            vx,vy=float(vel[0]),float(vel[1])
        speed = math.hypot(vx,vy)
        bp = obj.get("body_params",{})
        self.props_table["positionXY"].config(text=_fmt_vec(pos))
        self.props_table["velocityXY"].config(text=_fmt_vec(vel))
        self.props_table["speed"].config(text=f"{speed:.2f}")
        self.props_table["theta"].config(text=f"{float(obj.get('theta',0)):.2f}")
        self.props_table["omega"].config(text=f"{float(obj.get('omega',0)):.2f}")
        self.props_table["mass"].config(text=str(obj.get("mass", bp.get("mass","-"))))
        self.props_table["I"].config(text=str(obj.get("I", bp.get("I","-"))))
        self.props_table["drag_lin_forward"].config(text=str(obj.get("drag_lin_forward", bp.get("drag_lin_forward","-"))))
        self.props_table["drag_lin_side"].config(text=str(obj.get("drag_lin_side", bp.get("drag_lin_side", "-"))))
        self.props_table["drag_rot"].config(text=str(obj.get("drag_rot", bp.get("drag_rot","-"))))
        self.props_table["destroyed"].config(text=str(bool(obj.get("destroyed",False))))

        # --- Engines ---
        engines = obj.get("engines", []) or []

        # usuń poprzedni kontener
        if hasattr(self, "eng_container") and self.eng_container.winfo_exists():
            self.eng_container.destroy()

        # utwórz nowy kontener tylko jeśli są silniki
        if engines:
            self.eng_container = tk.Frame(self.eng_card, bg=self.colors["card"])
            self.eng_container.pack(fill="x", pady=4)
            for e in engines:
                self._create_engine_row(self.eng_container, e)
        else:
            # jeśli brak silników, utwórz "placeholder" ale nie pakuj
            self.eng_container = tk.Frame(self.eng_card, bg=self.colors["card"])

        # wymuś przeliczenie geometrii i aktualizację scrollregion
        self.eng_container.update_idletasks()
        self.eng_card.update_idletasks()
        self.scrollable_frame.update_idletasks()
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

        # --- Sensors ---
        for i in self.sensors_tv.get_children():
            self.sensors_tv.delete(i)
        count = 0
        for s in obj.get("sensors", []):
            if not s.get("enabled", True):
                continue

            scan = s.get("scan", "-")

            if scan is None:
                scan_str = "-"
            elif isinstance(scan, (list, tuple)):
                # Jeśli lista krotek, konwertujemy każdą wartość na string z formatowaniem liczby
                scan_str = ", ".join(f"{v:.2f}" if isinstance(v, (int, float)) else str(v) for v in scan)
            elif isinstance(scan, dict):
                scan_str = ", ".join(f"{k}:{v}" for k, v in scan.items())
            else:
                scan_str = str(scan)

            self.sensors_tv.insert("", "end", values=(s.get("category", "-"), scan_str))
            count += 1

        self.sensors_tv.configure(height=max(1, count))

    def _create_engine_row(self, parent, engine):
        fr = tk.Frame(parent, bg=self.colors["card"], pady=4)
        fr.pack(fill="x")
        tk.Label(fr, text=str(engine.get("id", "-")), font=("Inter", self.font_base, "bold"),
                 bg=self.colors["card"]).pack(side="left")

        thrust = float(engine.get("thrust", 0))
        max_thrust = float(engine.get("max_thrust", engine.get("maxThrust", 1)))
        p_val = min(100, (abs(thrust) / max_thrust) * 100 if max_thrust else 0)

        style_name = "Green.Horizontal.TProgressbar"
        style = ttk.Style()
        style.configure(style_name, troughcolor=self.colors["card"], background=self.colors["emerald"])

        p = ttk.Progressbar(fr, orient="horizontal", length=140, mode="determinate", value=p_val, style=style_name)
        p.pack(side="right", padx=5)

        tk.Label(fr, text=f"{thrust:.2f}/{max_thrust:.2f}", font=("JetBrains Mono", self.font_base - 1),
                 bg=self.colors["card"], width=12, anchor="e").pack(side="right", padx=(4, 8))

    def clear(self):
        self._current_obj = None
        self.lbl_id.config(text="ID: -")
        for k in self.props_table.values(): k.config(text='-')
        for w in self.eng_container.winfo_children(): w.destroy()
        for i in self.sensors_tv.get_children(): self.sensors_tv.delete(i)

    def _copy_json(self):
        if not self._current_obj: return
        state = self._extract_state(self._current_obj)
        self.clipboard_clear()
        self.clipboard_append(json.dumps(state, indent=2, ensure_ascii=False))
        messagebox.showinfo("OK","Stan obiektu skopiowany do schowka")

    def _show_raw(self):
        if not self._current_obj: return
        state = self._extract_state(self._current_obj)
        win = tk.Toplevel(self)
        win.title(f"Stan obiektu - {self._current_obj.get('id','-')}")
        txt = tk.Text(win, wrap='none', width=120, height=30)
        txt.pack(fill="both",expand=True)
        txt.insert("1.0", json.dumps(state, indent=2, ensure_ascii=False))
        txt.config(state='disabled')

    def _center_request(self):
        if self._current_obj and self._on_center:
            self._on_center(self._current_obj)

    def _extract_state(self,obj):
        if not obj: return {}
        state_keys = ("id","positionXY","velocityXY","theta","omega","destroyed","removed")
        state = {k: obj.get(k) for k in state_keys if k in obj}
        if "engines" in obj:
            state["engines"]=[{"id":e.get("id"), "rotor_omega":e.get("rotor_omega"), "thrust":e.get("thrust"),"torque":e.get("torque")} for e in obj.get("engines",[])]
        if "sensors" in obj:
            state["sensors"]=[{"id":s.get("id"),"category":s.get("category"),"scan":s.get("scan")} for s in obj.get("sensors",[]) if s.get("enabled",True)]
        return state

# ------------------- Test -------------------
if __name__ == "__main__":
    root = tk.Tk()
    root.geometry("500x700")
    root.tk.call('tk', 'scaling', 1.5)

    inspector = InspectorPanel(root)
    inspector.pack(fill="both", expand=True)

    demo_obj = {
        "id": "bot-42",
        "positionXY": [12.35, 30.0],
        "velocityXY": [1.2, -0.4],
        "theta": 0.785,
        "omega": 0.02,
        "destroyed": False,
        "body_params": {"mass":3.5,"I":1.2,"drag_lin":0.1,"drag_rot":0.01},
        "engines": [{"id":"L","thrust":22.5,"max_thrust":40.0,"torque":0.5, "rotor_omega": 370}],
        "sensors": [{"id":"s0","category":"scan","scan":[0.0,12.0],"enabled":True}]
    }

    inspector.update_view(demo_obj)
    root.mainloop()
