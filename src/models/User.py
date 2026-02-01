class User:
    def __init__(self, email: str, password: str, name: str = None):
        self.email = email
        self.password = password
        self.name = name

    def login(self, email: str, password: str) -> bool:
        return self.email == email and self.password == password

    def __repr__(self):
        return f"User(email='{self.email}', name='{self.name}')"
