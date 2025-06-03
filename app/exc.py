class AppError(RuntimeError):
    pass


class InternalError(AppError):
    def __init__(self, orig: Exception):
        self.orig = orig

    def __str__(self) -> str:
        return f"<{type(self.orig)}: '{str(self.orig)}'>"

    def __repr__(self) -> str:
        return str(self)


class NotFoundError(AppError):
    pass


class AlreadyExists(AppError):
    pass


class TokenExpired(AppError):
    pass


class Forbidden(AppError):
    pass


class Unauthorized(AppError):
    pass


class InvalidRequest(AppError):
    pass


def to_dict(message: str) -> dict[str, list]:
    return {
        'detail': [
            {
                'loc': ['', 0],
                'msg': message,
                'type': 'error',
            },
        ],
    }


__all__ = [
    "AppError",
    "InternalError",
    "NotFoundError",
    "AlreadyExists",
    "TokenExpired",
    "Forbidden",
    "Unauthorized",
    "InvalidRequest",
]