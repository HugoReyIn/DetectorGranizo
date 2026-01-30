from models.User import User
from models.Field import Field
from models.Point import Point


class Main:
    def __init__(self):
        self.users = []
        self.fields = []
        self.current_user = None

    def register_user(self):
        username = input("Usuario: ")
        password = input("Contraseña: ")
        user = User(username, password)
        self.users.append(user)
        print("✅ Usuario registrado")

    def login(self):
        username = input("Usuario: ")
        password = input("Contraseña: ")

        for user in self.users:
            if user.login(username, password):
                self.current_user = user
                print(f"✅ Bienvenido {user.username}")
                return

        print("❌ Usuario o contraseña incorrectos")

    def create_field(self):
        if not self.current_user:
            print("❌ Debes iniciar sesión primero")
            return

        name = input("Nombre del campo: ")
        municipality = input("Municipio (deja vacío si no sabes): ")

        field = Field(name, municipality=municipality if municipality else None)

        while True:
            add = input("¿Añadir punto? (s/n): ").lower()
            if add != "s":
                break

            lat = float(input("Latitud: "))
            lon = float(input("Longitud: "))
            field.add_point(Point(lat, lon))

        self.fields.append(field)
        print("✅ Campo creado")
        print(field)

    def run(self):
        while True:
            print("\n--- MENÚ ---")
            print("1. Registrar usuario")
            print("2. Iniciar sesión")
            print("3. Crear campo")
            print("4. Salir")

            option = input("Elige una opción: ")

            if option == "1":
                self.register_user()
            elif option == "2":
                self.login()
            elif option == "3":
                self.create_field()
            elif option == "4":
                print("👋 Hasta luego")
                break
            else:
                print("❌ Opción no válida")


if __name__ == "__main__":
    app = Main()
    app.run()
