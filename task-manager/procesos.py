import psutil
from tabulate import tabulate

def mostrar_procesos():
    procesos = []
    for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
        try:
            procesos.append(proc.info)
        except psutil.NoSuchProcess:
            continue
    print(tabulate(procesos, headers="keys", tablefmt="fancy_grid"))
