from datetime import datetime

TIME_FORMAT = "%d.%m.%Y %H:%M"


def now_str() -> str:
    """Return current timestamp as string in the common format."""
    return datetime.now().strftime(TIME_FORMAT)

