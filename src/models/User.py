class User:
    def __init__(self, username: str, password: str):
        self.username = username
        self.password = password

    def login(self, username: str, password: str) -> bool:
        return self.username == username and self.password == password

    def __repr__(self):
        return f"User(username='{self.username}')"