from datetime import datetime, tzinfo

TIME_FORMAT = "%d.%m.%Y %H:%M"


def now_str(tz: tzinfo | None = None) -> str:
    """Return current timestamp as string in the common format."""
    return datetime.now(tz).strftime(TIME_FORMAT)

