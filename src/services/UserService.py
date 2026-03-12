"""
UserService.py
Application Service — orquesta la lógica de negocio relacionada con usuarios.
No sabe nada de HTTP; recibe y devuelve objetos de dominio o primitivos.
"""

from daos.UserDAO import UserDAO
from models.User import User


class UserService:

    def __init__(self, user_dao: UserDAO):
        self._dao = user_dao

    # ──────────────────────────────────────────────
    # AUTENTICACIÓN
    # ──────────────────────────────────────────────
    def authenticate(self, email: str, password: str) -> User | None:
        """Devuelve el User si las credenciales son correctas, None si no."""
        user = self._dao.getUserByEmail(email)
        if user and user.password == password:
            return user
        return None

    # ──────────────────────────────────────────────
    # REGISTRO
    # ──────────────────────────────────────────────
    def register(self, name: str, email: str, password: str) -> tuple[User | None, str | None]:
        """
        Registra un nuevo usuario.

        Returns:
            (user, None)       si el registro fue exitoso.
            (None, error_msg)  si el email ya existe.
        """
        if self._dao.getUserByEmail(email):
            return None, "Este email ya está registrado. Usa otro o inicia sesión."
        new_user = User(name=name, email=email, password=password)
        self._dao.insertUser(new_user)
        return new_user, None

    # ──────────────────────────────────────────────
    # ACTUALIZAR PERFIL
    # ──────────────────────────────────────────────
    def update_profile(
        self,
        current_user: User,
        name: str,
        email: str,
        current_password: str,
        new_password: str,
        confirm_password: str = "",
    ) -> tuple[User, str | None, str]:
        """
        Actualiza nombre, email y contraseña del usuario.

        Returns:
            (user, error_msg, msg_type)
            msg_type es "ok" | "error"
        """
        # Email duplicado con otra cuenta
        existing = self._dao.getUserByEmail(email)
        if existing and existing.id != current_user.id:
            return current_user, "Ese email ya está en uso por otra cuenta.", "error"

        # Cambio de contraseña
        if new_password:
            if current_password != current_user.password:
                return current_user, "La contraseña actual no es correcta.", "error"
            if new_password != confirm_password:
                return current_user, "La nueva contraseña y su confirmación no coinciden.", "error"
            current_user.password = new_password

        current_user.name  = name
        current_user.email = email
        self._dao.updateUser(current_user)

        return current_user, "Perfil actualizado correctamente.", "ok"