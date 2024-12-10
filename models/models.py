import uuid
from sqlalchemy import (
    Column,
    String,
    Integer,
    Boolean,
    DateTime,
    create_engine,
)
from sqlalchemy.dialects.mssql import UNIQUEIDENTIFIER
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime


Base = declarative_base()

class DataDictionaries(Base):
    __tablename__ = "DataDictionaries"
    id = Column(UNIQUEIDENTIFIER, primary_key=True, default=uuid.uuid1)
    name = Column(String,nullable=False)
    is_published = Column(Boolean, default=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow())
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow())
    deleted_at = Column(DateTime, nullable=False)

    def save(self):
        self.updated_at = datetime.utcnow()
        super().save()

    class Settings:
        collection = "data_dictionaries"


class DataDictionaryTerms(Base):
    __tablename__ = "DataDictionaryTerms"
    id = Column(UNIQUEIDENTIFIER, primary_key=True, default=uuid.uuid1)
    dictionary = Column(String, nullable=False)
    dictionary_id = Column(UNIQUEIDENTIFIER, nullable=False)
    term = Column(String, nullable=False)
    data_type = Column(String, nullable=False)
    is_required = Column(Boolean, default=False)
    term_description = Column(String, nullable=True)
    expected_values = Column(String, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow())
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow())
    deleted_at = Column(DateTime, nullable=True)

    def save(self):
        self.updated_at = datetime.utcnow()
        super().save()

    class Settings:
        collection = "data_dictionary_terms"






class Facilities(Base):
    __tablename__ = "Facilities"
    id = Column(UNIQUEIDENTIFIER, primary_key=True, default=uuid.uuid1)
    facility_name = Column(UNIQUEIDENTIFIER, default=uuid.uuid1)
    site_code = Column(String, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow())
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow())

    def save(self):
        self.updated_at = datetime.utcnow()
        super().save()

    class Settings:
        collection = "facilities"


class Manifests(Base):
    __tablename__ = "Manifests"
    id = Column(UNIQUEIDENTIFIER, primary_key=True, default=uuid.uuid1)
    facility = Column(String, nullable=False)
    manifest_id = Column(UNIQUEIDENTIFIER, default=uuid.uuid1)
    usl_repository_name = Column(String, nullable=False)
    expected_count = Column(Integer)
    received_count = Column(Integer, nullable=True)
    source_system_name = Column(String, nullable=False)
    source_system_version = Column(String, nullable=False)
    opendive_version = Column(String, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow())
    session_id = Column(UNIQUEIDENTIFIER, default=uuid.uuid1)
    start = Column(DateTime, nullable=False, default=datetime.utcnow())
    end = Column(DateTime, nullable=True)
    status = Column(String)

    def save(self):
        self.created_at = datetime.utcnow()
        super().save()

    class Settings:
        collection = "manifests"
