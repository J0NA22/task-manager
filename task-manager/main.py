import tkinter as tk
from tkinter import ttk
import psutil, platform

# --- Procesos ---
def mostrar_procesos(tree):
    for row in tree.get_children():
        tree.delete(row)
    for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
        try:
            info = proc.info
            tree.insert("", "end", values=(info['pid'], info['name'], info['cpu_percent'], round(info['memory_percent'],2)))
        except psutil.NoSuchProcess:
            continue

# --- Usuarios ---
def mostrar_usuarios(tree):
    for row in tree.get_children():
        tree.delete(row)
    for u in psutil.users():
        tree.insert("", "end", values=(u.name, u.host, u.terminal, u.started))

# --- Detalles ---
def mostrar_detalles(frame):
    for widget in frame.winfo_children():
        widget.destroy()
    tk.Label(frame, text=f"Sistema: {platform.system()}").pack(anchor="w")
    tk.Label(frame, text=f"Versión: {platform.version()}").pack(anchor="w")
    tk.Label(frame, text=f"Arquitectura: {platform.machine()}").pack(anchor="w")
    tk.Label(frame, text=f"CPU %: {psutil.cpu_percent(interval=1)}").pack(anchor="w")
    tk.Label(frame, text=f"RAM %: {psutil.virtual_memory().percent}").pack(anchor="w")
    tk.Label(frame, text=f"Disco %: {psutil.disk_usage('/').percent}").pack(anchor="w")

# --- Servicios (solo Windows) ---
def mostrar_servicios(tree):
    for row in tree.get_children():
        tree.delete(row)
    for s in psutil.win_service_iter():
        try:
            info = s.as_dict()
            tree.insert("", "end", values=(info['name'], info['status'], info['display_name']))
        except Exception:
            continue

# --- Ventana principal ---
root = tk.Tk()
root.title("Simulador de Administrador de Tareas")
root.geometry("700x500")

notebook = ttk.Notebook(root)
notebook.pack(fill="both", expand=True)

# Tab Procesos
frame_procesos = ttk.Frame(notebook)
notebook.add(frame_procesos, text="Procesos")
cols = ("PID", "Nombre", "CPU %", "RAM %")
tree_proc = ttk.Treeview(frame_procesos, columns=cols, show="headings")
for col in cols:
    tree_proc.heading(col, text=col)
tree_proc.pack(fill="both", expand=True)
tk.Button(frame_procesos, text="Actualizar", command=lambda: mostrar_procesos(tree_proc)).pack()

# Tab Usuarios
frame_usuarios = ttk.Frame(notebook)
notebook.add(frame_usuarios, text="Usuarios")
cols_u = ("Usuario", "Host", "Terminal", "Inicio")
tree_user = ttk.Treeview(frame_usuarios, columns=cols_u, show="headings")
for col in cols_u:
    tree_user.heading(col, text=col)
tree_user.pack(fill="both", expand=True)
tk.Button(frame_usuarios, text="Actualizar", command=lambda: mostrar_usuarios(tree_user)).pack()

# Tab Detalles
frame_detalles = ttk.Frame(notebook)
notebook.add(frame_detalles, text="Detalles")
tk.Button(frame_detalles, text="Mostrar Detalles", command=lambda: mostrar_detalles(frame_detalles)).pack()

# Tab Servicios
frame_servicios = ttk.Frame(notebook)
notebook.add(frame_servicios, text="Servicios")
cols_s = ("Nombre", "Estado", "Descripción")
tree_serv = ttk.Treeview(frame_servicios, columns=cols_s, show="headings")
for col in cols_s:
    tree_serv.heading(col, text=col)
tree_serv.pack(fill="both", expand=True)
tk.Button(frame_servicios, text="Actualizar", command=lambda: mostrar_servicios(tree_serv)).pack()

root.mainloop()
