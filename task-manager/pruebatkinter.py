import psutil
import tkinter as tk
from tkinter import ttk

def mostrar_procesos():
    for row in tree.get_children():
        tree.delete(row)

    for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
        try:
            info = proc.info
            tree.insert("", "end", values=(info['pid'], info['name'], info['cpu_percent'], info['memory_percent']))
        except psutil.NoSuchProcess:
            continue

# Ventana principal
root = tk.Tk()
root.title("Simulador de Administrador de Tareas")

# Tabla de procesos
cols = ("PID", "Nombre", "CPU %", "RAM %")
tree = ttk.Treeview(root, columns=cols, show="headings")
for col in cols:
    tree.heading(col, text=col)
    tree.column(col, width=100)
tree.pack(fill="both", expand=True)

# Botón para actualizar
btn = tk.Button(root, text="Actualizar Procesos", command=mostrar_procesos)
btn.pack(pady=10)

root.mainloop()
