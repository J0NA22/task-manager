import psutil
from tabulate import tabulate

def mostrar_usuarios():
    usuarios = psutil.users()
    data = []
    for u in usuarios:
        data.append([u.name, u.host, u.terminal, u.started])
    print(tabulate(data, headers=["Usuario", "Host", "Terminal", "Inicio"], tablefmt="fancy_grid"))
