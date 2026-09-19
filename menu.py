"""
=====================================================================
 MENU.PY -- Punto de entrada único para usar en la Raspberry Pi
=====================================================================
Corre esto en vez de acordarte de comandos sueltos:
    python menu.py
"""
import sys
import subprocess
import getpass

import database
from werkzeug.security import check_password_hash


def registrar_persona():
    subprocess.run([sys.executable, "capture_dataset.py"])
    respuesta = input("\n¿Entrenar el modelo ahora con esta persona incluida? (s/n): ").strip().lower()
    if respuesta == "s":
        subprocess.run([sys.executable, "train_model.py"])


def entrar_cctv():
    print("\n=== Acceso al panel CCTV ===")
    username = input("Usuario: ").strip()
    password = getpass.getpass("Contraseña: ")

    user = database.get_user(username)
    if not user or not check_password_hash(user["password_hash"], password):
        print("Credenciales incorrectas. Acceso denegado.")
        return

    print(f"Acceso concedido ({user['role']}). Iniciando panel web en el puerto 8080...")
    print("Abre http://<ip-de-la-pi>:8080 desde el navegador. Ctrl+C aquí para detenerlo.")
    subprocess.run([sys.executable, "webapp/app.py"])


def main():
    database.init_db()
    while True:
        print("""
==============================
        FACESEC - MENÚ
==============================
1. Registrar persona nueva
2. Entrar al panel CCTV
3. Salir
""")
        opcion = input("Elige una opción: ").strip()
        if opcion == "1":
            registrar_persona()
        elif opcion == "2":
            entrar_cctv()
            break
        elif opcion == "3":
            print("Adiós.")
            break
        else:
            print("Opción inválida.")


if __name__ == "__main__":
    main()