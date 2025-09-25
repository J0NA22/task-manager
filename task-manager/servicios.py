import psutil
from tabulate import tabulate

def mostrar_servicios():
    servicios = []
    for s in psutil.win_service_iter():
        try:
            info = s.as_dict()
            servicios.append([info['name'], info['status'], info['display_name']])
        except Exception:
            continue
    print(tabulate(servicios, headers=["Nombre", "Estado", "Descripción"], tablefmt="fancy_grid"))
