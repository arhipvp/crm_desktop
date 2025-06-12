from __future__ import annotations

"""SQLAlchemy ORM models mirroring ``database/models.py``.
This minimal set defines only the Client model required for the new API.
"""

from sqlalchemy import Column, Integer, String, Boolean

from .sa import Base


class Client(Base):
    __tablename__ = "client"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    phone = Column(String)
    email = Column(String)
    is_company = Column(Boolean, default=False)
    note = Column(String)
    drive_folder_path = Column(String)
    drive_folder_link = Column(String)
    is_deleted = Column(Boolean, default=False)
