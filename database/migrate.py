"""Create database tables if they don't exist."""
from .init import init_from_env, ALL_MODELS
from .db import db


def main() -> None:
    init_from_env()
    db.create_tables(ALL_MODELS, safe=True)


if __name__ == "__main__":
    main()
