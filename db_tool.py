"""
=====================================================================
 DB_TOOL.PY -- Herramienta de administración de la base de datos
=====================================================================
Uso:
    python db_tool.py

ALTERNATIVA GRÁFICA (opcional): sudo apt install sqlitebrowser
"""
import getpass

import database


def print_table(rows, columns):
    if not rows:
        print("  (vacío)")
        return
    widths = [max(len(str(r.get(c, ""))) for r in rows + [dict.fromkeys(columns, "")]) for c in columns]
    header = " | ".join(c.ljust(w) for c, w in zip(columns, widths))
    print(" " + header)
    print(" " + "-" * len(header))
    for r in rows:
        line = " | ".join(str(r.get(c, "")).ljust(w) for c, w in zip(columns, widths))
        print(" " + line)


def ver_personas():
    print("\n=== PERSONAS REGISTRADAS (reconocimiento facial) ===")
    print_table(database.get_all_people(), ["id", "name", "role"])


def ver_usuarios():
    print("\n=== USUARIOS DEL PANEL WEB ===")
    print_table(database.get_all_users(), ["username", "role", "created_at"])


def ver_eventos():
    print("\n=== ÚLTIMOS EVENTOS DE RECONOCIMIENTO ===")
    print_table(
        database.get_all_events(limit=30),
        ["id", "person_name", "person_role", "camera_source", "start_time", "end_time"],
    )


def crear_usuario():
    username = input("Nuevo usuario: ").strip()
    password = getpass.getpass("Contraseña: ")
    role = input("Rol (admin/viewer) [viewer]: ").strip() or "viewer"
    database.add_user(username, password, role)
    print(f"Usuario '{username}' creado con rol '{role}'.")


def eliminar_usuario():
    ver_usuarios()
    username = input("\nUsuario a eliminar: ").strip()
    database.delete_user(username)
    print(f"Usuario '{username}' eliminado (si existía).")


def eliminar_persona():
    ver_personas()
    try:
        person_id = int(input("\nID de la persona a eliminar: ").strip())
    except ValueError:
        print("ID inválido.")
        return
    database.delete_person(person_id)
    print(f"Persona ID {person_id} eliminada de la base de datos.")
    print("Nota: sus fotos en data/dataset/ NO se borraron automáticamente.")
    print("Bórralas a mano si quieres, y vuelve a entrenar el modelo.")


def main():
    database.init_db()
    while True:
        print("""
==================================
   FACESEC -- ADMIN DE BASE DE DATOS
==================================
1. Ver personas registradas (reconocimiento)
2. Ver usuarios del panel web
3. Ver últimos eventos de reconocimiento
4. Crear usuario nuevo
5. Eliminar usuario
6. Eliminar persona (reconocimiento)
7. Salir
""")
        opcion = input("Elige una opción: ").strip()
        acciones = {
            "1": ver_personas, "2": ver_usuarios, "3": ver_eventos,
            "4": crear_usuario, "5": eliminar_usuario, "6": eliminar_persona,
        }
        if opcion == "7":
            print("Adiós.")
            break
        accion = acciones.get(opcion)
        if accion:
            accion()
        else:
            print("Opción inválida.")


if __name__ == "__main__":
    main()