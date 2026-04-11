"""
UserService.py
Application Service — orquesta la lógica de negocio relacionada con usuarios.
No sabe nada de HTTP; recibe y devuelve objetos de dominio o primitivos.

Seguridad de contraseñas:
  - Todas las contraseñas nuevas se hashean con bcrypt antes de persistir.
  - Al autenticar, si se detecta una contraseña en texto plano (usuarios
    previos a la migración), se rehashea y se guarda de forma transparente.
  - Instalar dependencia: pip install bcrypt
"""

import bcrypt

from daos.UserDAO import UserDAO
from models.User import User


# ──────────────────────────────────────────────
# HELPERS CRIPTOGRÁFICOS
# ──────────────────────────────────────────────
def _hash(plain: str) -> str:
    """Devuelve el hash bcrypt de una contraseña en texto plano."""
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt(rounds=12)).decode()


def _verify(plain: str, hashed: str) -> bool:
    """Comprueba si una contraseña en texto plano coincide con su hash bcrypt."""
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def _is_bcrypt(value: str) -> bool:
    """Detecta si un valor ya es un hash bcrypt (empieza por $2b$, $2a$ o $2y$)."""
    return value.startswith(("$2b$", "$2a$", "$2y$"))


class UserService:

    def __init__(self, user_dao: UserDAO):
        self._dao = user_dao

    # ──────────────────────────────────────────────
    # OBTENER POR ID
    # ──────────────────────────────────────────────
    def get_by_id(self, user_id: int) -> User | None:
        """Devuelve el User con ese id o None si no existe."""
        return self._dao.getUser(user_id)

    # ──────────────────────────────────────────────
    # AUTENTICACIÓN
    # ──────────────────────────────────────────────
    def authenticate(self, email: str, password: str) -> User | None:
        """
        Devuelve el User si las credenciales son correctas, None si no.

        Migración transparente: si la contraseña almacenada aún está en texto
        plano (usuarios anteriores a la adopción de bcrypt), se verifica por
        igualdad directa y, si coincide, se rehashea y persiste automáticamente.
        El usuario no nota nada.
        """
        user = self._dao.getUserByEmail(email)
        if not user:
            return None

        if _is_bcrypt(user.password):
            # Contraseña ya hasheada — verificación normal
            if not _verify(password, user.password):
                return None
        else:
            # Contraseña en texto plano (usuario pre-migración)
            if user.password != password:
                return None
            # Rehashear y persistir de forma transparente
            user.password = _hash(password)
            self._dao.updateUser(user)

        return user

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

        hashed   = _hash(password)
        new_user = User(name=name, email=email, password=hashed)
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
            # Verificar contraseña actual (compatible con texto plano y bcrypt)
            if _is_bcrypt(current_user.password):
                password_ok = _verify(current_password, current_user.password)
            else:
                password_ok = (current_password == current_user.password)

            if not password_ok:
                return current_user, "La contraseña actual no es correcta.", "error"
            if new_password != confirm_password:
                return current_user, "La nueva contraseña y su confirmación no coinciden.", "error"

            current_user.password = _hash(new_password)

        current_user.name  = name
        current_user.email = email
        self._dao.updateUser(current_user)

        return current_user, "Perfil actualizado correctamente.", "ok"