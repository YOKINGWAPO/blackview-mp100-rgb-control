#!/usr/bin/env python3
"""
RGB LED Control - Interfaz grafica portable para Windows y Linux.

Controla el RGB de la placa CYX (chip CH340) replicando el protocolo serie
del programa original, y permite activar/desactivar la accion al arranque.

Protocolo (5 bytes): [250, modo, 6-brillo, 6-velocidad, checksum]
  modo: 1=Arcoiris 2=Respiracion 3=Ciclo 4=Apagar 5=Auto
  checksum = suma(primeros 4) & 0xFF
  brillo/velocidad: 1..5
El firmware solo admite estos efectos + brillo + velocidad (no color fijo).

Requisitos: Python 3 con tkinter (incluido) y pyserial (pip install pyserial).
tkinter solo se carga al abrir la ventana; el modo --apply-startup no lo necesita.
"""

import os
import sys
import json
import time

import serial
import serial.tools.list_ports

# --------------------------------------------------------------------------
# Protocolo
# --------------------------------------------------------------------------
# nombre -> (valor, color_ui, emoji)
MODES = {
    "Apagar":      (4, "#3a3f5c", "⏻"),
    "Arcoiris":    (1, "#c0392b", "\U0001f308"),
    "Respiracion": (2, "#8e44ad", "\U0001f4a8"),
    "Ciclo":       (3, "#2980b9", "\U0001f504"),
    "Auto":        (5, "#27ae60", "✨"),
}
MODE_ORDER = ["Apagar", "Arcoiris", "Respiracion", "Ciclo", "Auto"]

CH340_VID = 0x1A86
CH340_PID = 0x7523
BAUDRATE = 10000
APP_NAME = "RGBLedControl"

# Paleta de la interfaz
BG = "#15151f"
CARD = "#1f1f2e"
FG = "#e8e8f0"
MUTED = "#9aa0c0"
ACCENT = "#5b8cff"
OK = "#7ed957"
ERR = "#ff6b6b"


# --------------------------------------------------------------------------
# Configuracion persistente
# --------------------------------------------------------------------------
def config_dir():
    if os.name == "nt":
        base = os.environ.get("APPDATA", os.path.expanduser("~"))
    else:
        base = os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config"))
    d = os.path.join(base, APP_NAME)
    os.makedirs(d, exist_ok=True)
    return d


CONFIG_FILE = os.path.join(config_dir(), "config.json")
DEFAULT_CONFIG = {
    "mode": "Apagar",
    "brightness": 3,
    "speed": 3,
    "startup_enabled": False,
    "startup_mode": "Apagar",
    "port": "",
}


def load_config():
    cfg = dict(DEFAULT_CONFIG)
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            cfg.update(json.load(f))
    except Exception:
        pass
    return cfg


def save_config(cfg):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
    except Exception:
        pass


# --------------------------------------------------------------------------
# Serie
# --------------------------------------------------------------------------
def list_ports():
    return list(serial.tools.list_ports.comports())


def find_port(preferred=""):
    if preferred:
        for p in list_ports():
            if p.device == preferred:
                return preferred
    for p in list_ports():
        if p.vid == CH340_VID and p.pid == CH340_PID:
            return p.device
    for p in list_ports():
        desc = (p.description or "").lower()
        if "ch340" in desc or "wch" in desc:
            return p.device
    return None


def build_frame(mode_value, brightness=3, speed=3):
    brightness = max(1, min(5, int(brightness)))
    speed = max(1, min(5, int(speed)))
    data = bytearray([250, mode_value, 6 - brightness, 6 - speed, 0])
    data[4] = sum(data[:4]) & 0xFF
    return data


def send_frame(port, frame):
    sp = serial.Serial(port=port, baudrate=BAUDRATE,
                       bytesize=serial.EIGHTBITS, parity=serial.PARITY_NONE,
                       stopbits=serial.STOPBITS_ONE, timeout=0.2)
    try:
        for b in frame:
            time.sleep(0.005)
            sp.write(bytes([b]))
        sp.flush()
    finally:
        sp.close()


def apply_mode(mode_value, brightness, speed, preferred_port=""):
    port = find_port(preferred_port)
    if not port:
        raise RuntimeError("No se encontro el dispositivo RGB (CH340).\n"
                           "Comprueba la conexion o elige el puerto manualmente.")
    send_frame(port, build_frame(mode_value, brightness, speed))
    return port


# --------------------------------------------------------------------------
# Accion de arranque (sin ventana, sin tkinter):  rgb_gui --apply-startup
# --------------------------------------------------------------------------
def run_startup_action():
    try:
        cfg = load_config()
        name = cfg.get("startup_mode", "Apagar")
        value = MODES.get(name, MODES["Apagar"])[0]
        port = find_port(cfg.get("port", ""))
        if port:
            send_frame(port, build_frame(value, cfg.get("brightness", 3),
                                         cfg.get("speed", 3)))
        return 0
    except Exception:
        return 1


# --------------------------------------------------------------------------
# Arranque automatico multiplataforma
# --------------------------------------------------------------------------
def _launcher_command():
    if getattr(sys, "frozen", False):
        return sys.executable, ["--apply-startup"]
    exe = sys.executable
    if os.name == "nt":
        pyw = os.path.join(os.path.dirname(exe), "pythonw.exe")
        if os.path.exists(pyw):
            exe = pyw
    return exe, [os.path.abspath(__file__), "--apply-startup"]


def _win_startup_set(enable):
    import winreg
    key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
    exe, args = _launcher_command()
    cmd = '"%s" %s' % (exe, " ".join(args))
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0,
                        winreg.KEY_SET_VALUE) as k:
        if enable:
            winreg.SetValueEx(k, APP_NAME, 0, winreg.REG_SZ, cmd)
        else:
            try:
                winreg.DeleteValue(k, APP_NAME)
            except FileNotFoundError:
                pass


def _win_startup_get():
    import winreg
    key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0,
                            winreg.KEY_QUERY_VALUE) as k:
            winreg.QueryValueEx(k, APP_NAME)
            return True
    except FileNotFoundError:
        return False


def _linux_autostart_path():
    base = os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config"))
    return os.path.join(base, "autostart", "%s.desktop" % APP_NAME)


def _linux_startup_set(enable):
    path = _linux_autostart_path()
    if enable:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        exe, args = _launcher_command()
        exec_line = '"%s" %s' % (exe, " ".join('"%s"' % a for a in args))
        with open(path, "w") as f:
            f.write("[Desktop Entry]\nType=Application\n"
                    "Name=RGB LED Control (accion al inicio)\n"
                    "Exec=%s\nX-GNOME-Autostart-enabled=true\nHidden=false\n"
                    % exec_line)
    elif os.path.exists(path):
        os.remove(path)


def startup_set(enable):
    _win_startup_set(enable) if os.name == "nt" else _linux_startup_set(enable)


def startup_get():
    return _win_startup_get() if os.name == "nt" else os.path.exists(_linux_autostart_path())


# --------------------------------------------------------------------------
# Interfaz grafica (tkinter se importa aqui, solo al abrir la ventana)
# --------------------------------------------------------------------------
def launch_gui():
    import tkinter as tk
    from tkinter import ttk, messagebox

    class App(tk.Tk):
        def __init__(self):
            super().__init__()
            self.cfg = load_config()
            self.title("RGB LED Control")
            self.resizable(False, False)
            self.configure(bg=BG)

            self.brightness = tk.IntVar(value=self.cfg["brightness"])
            self.speed = tk.IntVar(value=self.cfg["speed"])
            self.active_mode = tk.StringVar(value=self.cfg["mode"])
            self.port_var = tk.StringVar(value=self.cfg.get("port", ""))
            self.startup_var = tk.BooleanVar(value=startup_get())
            self.startup_mode_var = tk.StringVar(value=self.cfg["startup_mode"])

            self._build_styles(ttk)
            self._build_ui(tk, ttk)
            self.refresh_ports()
            self._update_mode_highlight()

        def _build_styles(self, ttk):
            st = ttk.Style(self)
            try:
                st.theme_use("clam")
            except Exception:
                pass
            st.configure("TCombobox", fieldbackground=CARD, background=CARD,
                         foreground=FG, arrowcolor=FG)
            st.configure("Horizontal.TScale", background=BG, troughcolor=CARD)

        def _build_ui(self, tk, ttk):
            root = tk.Frame(self, bg=BG)
            root.pack(padx=18, pady=14)

            tk.Label(root, text="RGB LED Control", font=("Segoe UI", 18, "bold"),
                     fg=FG, bg=BG).pack(anchor="w")
            self.status = tk.Label(root, text="", font=("Segoe UI", 9),
                                   fg=MUTED, bg=BG)
            self.status.pack(anchor="w", pady=(0, 10))

            tk.Label(root, text="MODO", font=("Segoe UI", 9, "bold"),
                     fg=MUTED, bg=BG).pack(anchor="w")
            cards = tk.Frame(root, bg=BG)
            cards.pack(fill="x", pady=(4, 12))
            self.mode_buttons = {}
            for i, name in enumerate(MODE_ORDER):
                value, color, emoji = MODES[name]
                card = tk.Button(
                    cards, text="%s\n%s" % (emoji, name), width=9, height=3,
                    bg=CARD, fg=FG, relief="flat", bd=0,
                    activebackground=color, activeforeground="white",
                    font=("Segoe UI", 10, "bold"), cursor="hand2",
                    highlightthickness=2, highlightbackground=CARD,
                    command=lambda n=name: self.on_mode(n))
                card.grid(row=i // 3, column=i % 3, padx=4, pady=4, sticky="nsew")
                self.mode_buttons[name] = (card, color)

            sl = tk.Frame(root, bg=BG)
            sl.pack(fill="x", pady=(2, 8))
            self._slider(tk, ttk, sl, "Brillo", self.brightness, 0)
            self._slider(tk, ttk, sl, "Velocidad", self.speed, 1)

            pf = tk.Frame(root, bg=BG)
            pf.pack(fill="x", pady=(6, 10))
            tk.Label(pf, text="Puerto", font=("Segoe UI", 10), fg=FG, bg=BG
                     ).pack(side="left")
            self.port_combo = ttk.Combobox(pf, textvariable=self.port_var,
                                           state="readonly", width=26)
            self.port_combo.pack(side="left", padx=8)
            tk.Button(pf, text="↻", command=self.refresh_ports, bg=CARD, fg=FG,
                      relief="flat", width=3, cursor="hand2").pack(side="left")

            tk.Frame(root, bg="#2a2a3d", height=1).pack(fill="x", pady=8)

            tk.Label(root, text="AL INICIAR EL EQUIPO", font=("Segoe UI", 9, "bold"),
                     fg=MUTED, bg=BG).pack(anchor="w")
            sf = tk.Frame(root, bg=BG)
            sf.pack(fill="x", pady=(4, 0))
            tk.Checkbutton(sf, text="Aplicar automaticamente:",
                           variable=self.startup_var, command=self.on_toggle_autostart,
                           fg=FG, bg=BG, selectcolor=CARD, activebackground=BG,
                           activeforeground=FG, font=("Segoe UI", 10)).pack(side="left")
            self.startup_combo = ttk.Combobox(sf, textvariable=self.startup_mode_var,
                                              state="readonly", width=12,
                                              values=MODE_ORDER)
            self.startup_combo.pack(side="left", padx=8)
            self.startup_combo.bind("<<ComboboxSelected>>", lambda e: self.persist())

        def _slider(self, tk, ttk, parent, label, var, row):
            tk.Label(parent, text=label, font=("Segoe UI", 10), fg=FG, bg=BG,
                     width=10, anchor="w").grid(row=row, column=0, sticky="w", pady=3)
            scale = ttk.Scale(parent, from_=1, to=5, orient="horizontal", length=180,
                              variable=var)
            scale.grid(row=row, column=1, padx=8)
            val = tk.Label(parent, text=str(var.get()), font=("Segoe UI", 11, "bold"),
                           fg=ACCENT, bg=BG, width=2)
            val.grid(row=row, column=2)

            def on_move(_=None):
                var.set(round(var.get()))
                val.config(text=str(var.get()))
                self.persist()
            scale.configure(command=on_move)

        def refresh_ports(self):
            ports = list_ports()
            values = ["%s  -  %s" % (p.device, p.description) for p in ports]
            self._port_map = {v: p.device for v, p in zip(values, ports)}
            self.port_combo["values"] = values
            auto = find_port(self.port_var.get())
            for v, dev in self._port_map.items():
                if dev == auto:
                    self.port_combo.set(v)
                    self.port_var.set(dev)
                    break
            if auto:
                self.status.config(text="Dispositivo detectado en %s" % auto, fg=OK)
            else:
                self.status.config(text="No se detecta el dispositivo RGB (CH340)",
                                   fg=ERR)
            self.port_combo.bind("<<ComboboxSelected>>", self._on_port_pick)

        def _on_port_pick(self, _=None):
            sel = self.port_combo.get()
            dev = getattr(self, "_port_map", {}).get(sel, "")
            if dev:
                self.port_var.set(dev)
                self.persist()

        def _update_mode_highlight(self):
            active = self.active_mode.get()
            for name, (card, color) in self.mode_buttons.items():
                if name == active:
                    card.config(bg=color, fg="white", highlightbackground=ACCENT)
                else:
                    card.config(bg=CARD, fg=FG, highlightbackground=CARD)

        def on_mode(self, name):
            try:
                value = MODES[name][0]
                port = apply_mode(value, self.brightness.get(), self.speed.get(),
                                  self.port_var.get())
                self.active_mode.set(name)
                self._update_mode_highlight()
                self.status.config(text="'%s' aplicado en %s" % (name, port), fg=OK)
                self.persist()
            except Exception as e:
                messagebox.showerror("Error", str(e))
                self.refresh_ports()

        def on_toggle_autostart(self):
            try:
                startup_set(self.startup_var.get())
                self.persist()
            except Exception as e:
                messagebox.showerror("Error",
                                     "No se pudo cambiar el arranque:\n%s" % e)
                self.startup_var.set(startup_get())

        def persist(self):
            self.cfg.update({
                "mode": self.active_mode.get(),
                "brightness": self.brightness.get(),
                "speed": self.speed.get(),
                "startup_enabled": self.startup_var.get(),
                "startup_mode": self.startup_mode_var.get(),
                "port": self.port_var.get(),
            })
            save_config(self.cfg)

    App().mainloop()
    return 0


def main():
    if "--apply-startup" in sys.argv:
        return run_startup_action()
    return launch_gui()


if __name__ == "__main__":
    sys.exit(main())
