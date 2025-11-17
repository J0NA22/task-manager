import tkinter as tk
from tkinter import ttk, messagebox
import psutil, sys

# --------------------------------------------------
# Utilidades
# --------------------------------------------------

def limpiar_tree(tree):
    for row in tree.get_children():
        tree.delete(row)

NUM_CPUS = psutil.cpu_count(logical=True) or 1

# control de actualización automática y último snapshot
auto_update = True
last_snapshot = []

def obtener_procesos_snapshot():
    """
    Toma una 'foto' de todos los procesos con todos los datos que necesitamos.
    Así evitamos recorrer la lista de procesos varias veces.
    """
    snapshot = []
    for proc in psutil.process_iter(
        ['pid', 'name', 'cpu_percent', 'memory_percent',
         'status', 'username', 'memory_info']
    ):
        try:
            snapshot.append(proc.info)
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue
    return snapshot

def pasa_filtro(info, modo, query):
    """
    Aplica filtro por Nombre / PID / Estado / Usuario a un diccionario info de proceso.
    Se usa en pestañas Procesos y Detalles.
    """
    if not query:
        return True  # sin filtro

    q = query.strip()
    if not q:
        return True

    modo = (modo or "Nombre").lower()

    if modo == "nombre":
        nombre = str(info.get("name", "")).lower()
        return q.lower() in nombre

    elif modo == "pid":
        pid_str = str(info.get("pid", ""))
        return pid_str.startswith(q)

    elif modo == "estado":
        estado = str(info.get("status", "")).lower()
        return q.lower() in estado

    elif modo == "usuario":
        usuario = str(info.get("username", "")).lower()
        return q.lower() in usuario

    return True

# ---- Ordenar columnas ----

def _to_number(val):
    try:
        s = str(val).replace("%", "").replace(",", ".").strip()
        return float(s)
    except Exception:
        return 0.0

def sort_treeview(tree, col, reverse, numeric=False):
    # obtener pares (valor, item_id)
    data = [(tree.set(k, col), k) for k in tree.get_children("")]
    if numeric:
        data.sort(key=lambda t: _to_number(t[0]), reverse=reverse)
    else:
        data.sort(key=lambda t: str(t[0]).lower(), reverse=reverse)

    for index, (_, k) in enumerate(data):
        tree.move(k, "", index)

    # toggle al siguiente click
    tree.heading(col, command=lambda: sort_treeview(tree, col, not reverse, numeric))

# --------------------------------------------------
# PROCESOS (pestaña Procesos)
# --------------------------------------------------

def mostrar_procesos(tree, snapshot, search_mode_var, search_query_var):
    # Guardar selección actual (PID) para no perderla al refrescar
    sel = tree.selection()
    selected_pid = None
    if sel:
        try:
            selected_pid = int(tree.item(sel[0])["values"][0])
        except Exception:
            selected_pid = None

    limpiar_tree(tree)
    item_to_select = None

    modo = search_mode_var.get()
    query = search_query_var.get()

    for info in snapshot:
        try:
            if not pasa_filtro(info, modo, query):
                continue

            pid = info['pid']
            nombre = info['name']
            cpu = info.get('cpu_percent') or 0.0
            mem_pct = info.get('memory_percent') or 0.0

            iid = tree.insert(
                "",
                "end",
                values=(
                    pid,
                    nombre,
                    round(cpu, 1),
                    round(mem_pct, 2)
                )
            )
            if selected_pid is not None and pid == selected_pid:
                item_to_select = iid
        except Exception:
            continue

    # Reseleccionar el proceso que estaba marcado antes del refresh
    if item_to_select:
        tree.selection_set(item_to_select)


def terminar_proceso(tree, pid_col_index=0):
    sel = tree.selection()
    if not sel:
        messagebox.showinfo("Información", "Seleccione un proceso para finalizar.")
        return

    try:
        values = tree.item(sel[0])["values"]
        pid = int(values[pid_col_index])  # PID en la columna indicada
    except Exception:
        messagebox.showerror("Error", "No se pudo obtener el PID del proceso seleccionado.")
        return

    if not messagebox.askyesno("Confirmar", f"¿Finalizar proceso con PID {pid}?"):
        return

    try:
        p = psutil.Process(pid)
        p.terminate()
        try:
            p.wait(timeout=3)
        except psutil.TimeoutExpired:
            p.kill()
        messagebox.showinfo("Hecho", f"Se finalizó el proceso {pid}.")
    except psutil.NoSuchProcess:
        messagebox.showinfo("Información", "El proceso ya no existe.")
    except psutil.AccessDenied:
        messagebox.showerror(
            "Acceso denegado",
            "No se tienen permisos para finalizar este proceso.\n"
            "Ejecuta el programa como Administrador si es necesario."
        )
    except Exception as e:
        messagebox.showerror("Error", f"Error al finalizar el proceso:\n{e}")

# --------------------------------------------------
# USUARIOS (tipo pestaña Users de Windows)
# --------------------------------------------------

def mostrar_usuarios(tree, snapshot):
    """
    Usuarios tipo Task Manager:
    Usuario | Estado | CPU % | Memoria (MB) | Disco | Red
    Agrupa por nombre de usuario de los procesos (username) y
    normaliza el CPU % para que esté entre 0 y 100 aprox.
    """
    limpiar_tree(tree)

    stats = {}  # {username: {"cpu_raw": float, "mem": int_bytes}}

    for info in snapshot:
        try:
            user = info.get('username') or "Desconocido"
            cpu_raw = info.get('cpu_percent') or 0.0
            meminfo = info.get('memory_info')
            mem = meminfo.rss if meminfo else 0

            if user not in stats:
                stats[user] = {"cpu_raw": 0.0, "mem": 0}

            stats[user]["cpu_raw"] += cpu_raw
            stats[user]["mem"] += mem
        except Exception:
            continue

    for user, data in stats.items():
        cpu_raw = data["cpu_raw"]
        cpu_percent = cpu_raw / NUM_CPUS
        cpu_percent = round(cpu_percent, 1)
        if cpu_percent > 100:
            cpu_percent = 100.0  # opcional

        mem_mb = round(data["mem"] / (1024 * 1024), 1)
        estado = "Activo"
        disco = "-"
        red = "-"
        tree.insert(
            "",
            "end",
            values=(user, estado, cpu_percent, mem_mb, disco, red)
        )

# --------------------------------------------------
# DETALLES (tipo pestaña Details de Windows)
# --------------------------------------------------

def mostrar_detalles(tree, snapshot, search_mode_var, search_query_var):
    """
    Muestra procesos con columnas:
    Nombre | PID | Estado | Usuario | CPU % | Memoria MB
    """
    # Guardar selección actual por PID
    sel = tree.selection()
    selected_pid = None
    if sel:
        try:
            selected_pid = int(tree.item(sel[0])["values"][1])  # PID está en columna 2
        except Exception:
            selected_pid = None

    limpiar_tree(tree)
    item_to_select = None

    modo = search_mode_var.get()
    query = search_query_var.get()

    for info in snapshot:
        try:
            if not pasa_filtro(info, modo, query):
                continue

            pid = info['pid']
            nombre = info['name']
            estado = info.get('status', '')
            usuario = info.get('username', '')
            cpu = info.get('cpu_percent') or 0.0
            meminfo = info.get('memory_info')
            mem_mb = meminfo.rss / (1024 * 1024) if meminfo else 0.0

            iid = tree.insert(
                "",
                "end",
                values=(
                    nombre,
                    pid,
                    estado,
                    usuario,
                    round(cpu, 1),
                    round(mem_mb, 1)
                )
            )

            if selected_pid is not None and pid == selected_pid:
                item_to_select = iid

        except Exception:
            continue

    if item_to_select:
        tree.selection_set(item_to_select)

# --------------------------------------------------
# SERVICIOS (solo Windows)
# --------------------------------------------------

ES_WINDOWS = sys.platform.startswith("win")

def mostrar_servicios(tree):
    # Guardar selección actual por nombre
    sel = tree.selection()
    selected_name = None
    if sel:
        try:
            selected_name = tree.item(sel[0])["values"][0]
        except Exception:
            selected_name = None

    limpiar_tree(tree)

    if not ES_WINDOWS:
        tree.insert("", "end", values=("N/A", "N/A", "Servicios solo disponibles en Windows"))
        return

    item_to_select = None

    try:
        for s in psutil.win_service_iter():
            try:
                info = s.as_dict()
                name = info["name"]
                iid = tree.insert(
                    "",
                    "end",
                    values=(name, info["status"], info["display_name"])
                )
                if selected_name is not None and name == selected_name:
                    item_to_select = iid
            except Exception:
                continue
    except Exception as e:
        messagebox.showerror("Error", f"No se pudieron obtener los servicios:\n{e}")

    if item_to_select:
        tree.selection_set(item_to_select)


def obtener_nombre_servicio_seleccionado(tree):
    sel = tree.selection()
    if not sel:
        messagebox.showinfo("Información", "Seleccione un servicio primero.")
        return None

    try:
        values = tree.item(sel[0])["values"]
        nombre_servicio = values[0]
        return nombre_servicio
    except Exception:
        messagebox.showerror("Error", "No se pudo obtener el nombre del servicio.")
        return None


def iniciar_servicio(tree):
    if not ES_WINDOWS:
        messagebox.showinfo("Información", "Gestión de servicios solo disponible en Windows.")
        return

    nombre = obtener_nombre_servicio_seleccionado(tree)
    if not nombre:
        return

    try:
        srv = psutil.win_service_get(nombre)
        srv.start()
        messagebox.showinfo("Hecho", f"Servicio '{nombre}' iniciado.")
    except psutil.AccessDenied:
        messagebox.showerror(
            "Acceso denegado",
            "No se tienen permisos para iniciar este servicio.\n"
            "Ejecuta el programa como Administrador."
        )
    except Exception as e:
        messagebox.showerror("Error", f"No se pudo iniciar el servicio:\n{e}")


def detener_servicio(tree):
    if not ES_WINDOWS:
        messagebox.showinfo("Información", "Gestión de servicios solo disponible en Windows.")
        return

    nombre = obtener_nombre_servicio_seleccionado(tree)
    if not nombre:
        return

    if not messagebox.askyesno("Confirmar", f"¿Detener servicio '{nombre}'?"):
        return

    try:
        srv = psutil.win_service_get(nombre)
        srv.stop()
        messagebox.showinfo("Hecho", f"Servicio '{nombre}' detenido.")
    except psutil.AccessDenied:
        messagebox.showerror(
            "Acceso denegado",
            "No se tienen permisos para detener este servicio.\n"
            "Ejecuta el programa como Administrador."
        )
    except Exception as e:
        messagebox.showerror("Error", f"No se pudo detener el servicio:\n{e}")


def reiniciar_servicio(tree):
    if not ES_WINDOWS:
        messagebox.showinfo("Información", "Gestión de servicios solo disponible en Windows.")
        return

    nombre = obtener_nombre_servicio_seleccionado(tree)
    if not nombre:
        return

    if not messagebox.askyesno("Confirmar", f"¿Reiniciar servicio '{nombre}'?"):
        return

    try:
        srv = psutil.win_service_get(nombre)
        srv.stop()
        srv.start()
        messagebox.showinfo("Hecho", f"Servicio '{nombre}' reiniciado.")
    except psutil.AccessDenied:
        messagebox.showerror(
            "Acceso denegado",
            "No se tienen permisos para reiniciar este servicio.\n"
            "Ejecuta el programa como Administrador."
        )
    except Exception as e:
        messagebox.showerror("Error", f"No se pudo reiniciar el servicio:\n{e}")

# --------------------------------------------------
# THEME / MODO CLARO–OSCURO
# --------------------------------------------------

current_theme = "light"

def aplicar_tema(style, root, theme):
    global current_theme
    current_theme = theme

    if theme == "dark":
        bg = "#1e1e1e"
        fg = "#f0f0f0"
        tree_bg = "#252526"
        select_bg = "#094771"
        btn_bg = "#333333"
    else:
        bg = "#f0f0f0"
        fg = "#000000"
        tree_bg = "#ffffff"
        select_bg = "#0078d7"
        btn_bg = "#e0e0e0"

    root.configure(bg=bg)
    style.theme_use("clam")

    # Estilos generales
    style.configure(".", background=bg, foreground=fg)
    style.configure("TFrame", background=bg)
    style.configure("TLabel", background=bg, foreground=fg)
    style.configure("TButton", background=btn_bg, foreground=fg)
    style.configure("TNotebook", background=bg)
    style.configure("TNotebook.Tab", background=btn_bg, foreground=fg)
    style.map("TNotebook.Tab",
              background=[("selected", tree_bg)],
              foreground=[("selected", fg)])

    # Treeview
    style.configure("Treeview",
                    background=tree_bg,
                    fieldbackground=tree_bg,
                    foreground=fg)
    style.map("Treeview",
              background=[("selected", select_bg)],
              foreground=[("selected", fg)])

# --------------------------------------------------
# VENTANA PRINCIPAL
# --------------------------------------------------

root = tk.Tk()
root.title("Simulador de Administrador de Tareas")
root.geometry("1100x680")

style = ttk.Style()
aplicar_tema(style, root, "light")  # empezamos en modo claro

# ---- Barra superior con título y ajustes ----
top_bar = ttk.Frame(root)
top_bar.pack(fill="x", pady=3, padx=5)

lbl_title = ttk.Label(top_bar, text="🖥️ Task Manager By Halley, Sofia and Jona", font=("Segoe UI", 11, "bold"))
lbl_title.pack(side="left")

settings_frame = ttk.Frame(top_bar)  # panel que se mostrará/ocultará

theme_btn_text = tk.StringVar(value="🌙 Modo oscuro")

def toggle_theme():
    if current_theme == "light":
        aplicar_tema(style, root, "dark")
        theme_btn_text.set("☀️ Modo claro")
    else:
        aplicar_tema(style, root, "light")
        theme_btn_text.set("🌙 Modo oscuro")

btn_theme = ttk.Button(settings_frame, textvariable=theme_btn_text, command=toggle_theme)
btn_theme.pack(side="left", padx=5)

# botón Pausar/Reanudar actualización
update_btn_text = tk.StringVar(value="⏸ Pausar actualización")

def toggle_auto_update():
    global auto_update
    auto_update = not auto_update
    if auto_update:
        update_btn_text.set("⏸ Pausar actualización")
    else:
        update_btn_text.set("▶ Reanudar actualización")

btn_update = ttk.Button(settings_frame, textvariable=update_btn_text, command=toggle_auto_update)
btn_update.pack(side="left", padx=5)

def toggle_settings():
    # mostrar/ocultar panel de ajustes
    if settings_frame.winfo_ismapped():
        settings_frame.pack_forget()
    else:
        settings_frame.pack(side="right", padx=5)

btn_settings = ttk.Button(top_bar, text="⚙ Ajustes", command=toggle_settings)
btn_settings.pack(side="right", padx=5)

# ---- Barra de estado CPU/RAM ----
status_bar = ttk.Frame(root)
status_bar.pack(fill="x", padx=5, pady=(0, 3))

lbl_status = ttk.Label(status_bar, text="CPU: -- % | RAM: -- %")
lbl_status.pack(side="right")

# Notebook principal
notebook = ttk.Notebook(root)
notebook.pack(fill="both", expand=True)

# variables de búsqueda
search_proc_mode = tk.StringVar(value="Nombre")
search_proc_query = tk.StringVar()
search_det_mode = tk.StringVar(value="Nombre")
search_det_query = tk.StringVar()

# PESTAÑA PROCESOS
frame_procesos = ttk.Frame(notebook)
# Icono tipo logo usando emoji
notebook.add(frame_procesos, text="🧮 Procesos")

# barra superior con búsqueda (izquierda) y botón (derecha)
top_proc = ttk.Frame(frame_procesos)
top_proc.pack(fill="x", pady=5)

left_proc = ttk.Frame(top_proc)
left_proc.pack(side="left")

ttk.Label(left_proc, text="Buscar por:").pack(side="left", padx=5)
cb_proc = ttk.Combobox(
    left_proc,
    textvariable=search_proc_mode,
    values=("Nombre", "PID", "Estado", "Usuario"),
    state="readonly",
    width=10
)
cb_proc.pack(side="left")

entry_proc = ttk.Entry(left_proc, textvariable=search_proc_query, width=30)
entry_proc.pack(side="left", padx=5)

def limpiar_busqueda_proc():
    search_proc_query.set("")

ttk.Button(left_proc, text="Limpiar", command=limpiar_busqueda_proc).pack(side="left", padx=5)

# botón a la derecha, misma altura
btn_proc = ttk.Button(
    top_proc,
    text="Finalizar tarea seleccionada",
    command=lambda: terminar_proceso(tree_proc, pid_col_index=0)
)
btn_proc.pack(side="right", padx=10)

cols_proc = ("PID", "Nombre", "CPU %", "RAM %")
tree_proc = ttk.Treeview(frame_procesos, columns=cols_proc, show="headings")
for col in cols_proc:
    numeric = col in ("PID", "CPU %", "RAM %")
    tree_proc.heading(col, text=col,
                      command=lambda c=col, n=numeric: sort_treeview(tree_proc, c, False, n))
    tree_proc.column(col, anchor="center")
tree_proc.pack(fill="both", expand=True)

# menú contextual en Procesos
proc_menu = tk.Menu(root, tearoff=0)
proc_menu.add_command(label="Finalizar tarea", command=lambda: terminar_proceso(tree_proc, pid_col_index=0))

def on_proc_right_click(event):
    row = tree_proc.identify_row(event.y)
    if row:
        tree_proc.selection_set(row)
        proc_menu.tk_popup(event.x_root, event.y_root)
        proc_menu.grab_release()

tree_proc.bind("<Button-3>", on_proc_right_click)

# PESTAÑA USUARIOS
frame_usuarios = ttk.Frame(notebook)
notebook.add(frame_usuarios, text="👤 Usuarios")

cols_u = ("Usuario", "Estado", "CPU %", "Memoria (MB)", "Disco", "Red")
tree_user = ttk.Treeview(frame_usuarios, columns=cols_u, show="headings")
for col in cols_u:
    numeric = col in ("CPU %", "Memoria (MB)")
    tree_user.heading(col, text=col,
                      command=lambda c=col, n=numeric: sort_treeview(tree_user, c, False, n))
    tree_user.column(col, anchor="center")
tree_user.pack(fill="both", expand=True)

# PESTAÑA DETALLES
frame_detalles = ttk.Frame(notebook)
notebook.add(frame_detalles, text="📋 Detalles")

top_det = ttk.Frame(frame_detalles)
top_det.pack(fill="x", pady=5)

ttk.Label(top_det, text="Buscar por:").pack(side="left", padx=5)
cb_det = ttk.Combobox(
    top_det,
    textvariable=search_det_mode,
    values=("Nombre", "PID", "Estado", "Usuario"),
    state="readonly",
    width=10
)
cb_det.pack(side="left")

entry_det = ttk.Entry(top_det, textvariable=search_det_query, width=30)
entry_det.pack(side="left", padx=5)

def limpiar_busqueda_det():
    search_det_query.set("")

ttk.Button(top_det, text="Limpiar", command=limpiar_busqueda_det).pack(side="left", padx=5)

cols_d = ("Nombre", "PID", "Estado", "Usuario", "CPU %", "Memoria (MB)")
tree_detalles = ttk.Treeview(frame_detalles, columns=cols_d, show="headings")
for col in cols_d:
    numeric = col in ("PID", "CPU %", "Memoria (MB)")
    tree_detalles.heading(col, text=col,
                          command=lambda c=col, n=numeric: sort_treeview(tree_detalles, c, False, n))
    tree_detalles.column(col, anchor="center")
tree_detalles.pack(fill="both", expand=True)

# menú contextual en Detalles
det_menu = tk.Menu(root, tearoff=0)
det_menu.add_command(label="Finalizar tarea", command=lambda: terminar_proceso(tree_detalles, pid_col_index=1))

def on_det_right_click(event):
    row = tree_detalles.identify_row(event.y)
    if row:
        tree_detalles.selection_set(row)
        det_menu.tk_popup(event.x_root, event.y_root)
        det_menu.grab_release()

tree_detalles.bind("<Button-3>", on_det_right_click)

# PESTAÑA SERVICIOS
frame_servicios = ttk.Frame(notebook)
notebook.add(frame_servicios, text="🛠 Servicios")

cols_s = ("Nombre", "Estado", "Descripción")
tree_serv = ttk.Treeview(frame_servicios, columns=cols_s, show="headings")
for col in cols_s:
    tree_serv.heading(col, text=col,
                      command=lambda c=col: sort_treeview(tree_serv, c, False, False))
    tree_serv.column(col, anchor="center")
tree_serv.pack(fill="both", expand=True)

frame_btn_serv = ttk.Frame(frame_servicios)
frame_btn_serv.pack(pady=5)

ttk.Button(frame_btn_serv, text="Iniciar",
           command=lambda: iniciar_servicio(tree_serv)).grid(row=0, column=0, padx=5)
ttk.Button(frame_btn_serv, text="Detener",
           command=lambda: detener_servicio(tree_serv)).grid(row=0, column=1, padx=5)
ttk.Button(frame_btn_serv, text="Reiniciar",
           command=lambda: reiniciar_servicio(tree_serv)).grid(row=0, column=2, padx=5)

# --------------------------------------------------
# ACTUALIZACIÓN PERIÓDICA
# --------------------------------------------------

services_counter = 0  # para actualizar servicios con menos frecuencia

def schedule_updates():
    global services_counter, last_snapshot, auto_update

    # actualizar snapshot solo si no está en pausa
    if auto_update:
        try:
            last_snapshot = obtener_procesos_snapshot()
        except Exception:
            last_snapshot = []

    snapshot = last_snapshot

    try:
        mostrar_procesos(tree_proc, snapshot, search_proc_mode, search_proc_query)
    except Exception:
        pass
    try:
        mostrar_usuarios(tree_user, snapshot)
    except Exception:
        pass
    try:
        mostrar_detalles(tree_detalles, snapshot, search_det_mode, search_det_query)
    except Exception:
        pass

    # actualizar barra CPU/RAM (siempre)
    try:
        cpu_total = psutil.cpu_percent(interval=None)
        ram_total = psutil.virtual_memory().percent
        lbl_status.config(text=f"CPU: {cpu_total:.1f}% | RAM: {ram_total:.1f}%")
    except Exception:
        pass

    # servicios solo cuando no está en pausa
    if auto_update:
        services_counter += 1
        # Actualizar servicios cada 5 ciclos (~10 s si el after es 2000 ms)
        if services_counter % 5 == 0:
            try:
                mostrar_servicios(tree_serv)
            except Exception:
                pass

    # refresco cada 2000 ms para dar aire a la UI
    root.after(2000, schedule_updates)

schedule_updates()
root.mainloop()
