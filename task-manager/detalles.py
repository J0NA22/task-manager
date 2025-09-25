import psutil, platform

def mostrar_detalles():
    print("\n--- Información del Sistema ---")
    print("Sistema:", platform.system())
    print("Versión:", platform.version())
    print("Arquitectura:", platform.machine())
    print("CPU %:", psutil.cpu_percent(interval=1))
    print("Memoria RAM %:", psutil.virtual_memory().percent)
    print("Disco %:", psutil.disk_usage('/').percent)
    print("Red (bytes enviados/recibidos):", psutil.net_io_counters().bytes_sent, "/", psutil.net_io_counters().bytes_recv)
    print("-------------------------------\n")
    
    