from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Index, text
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from backend.database import Base

class Target(Base):
    __tablename__ = "targets"

    id = Column(Integer, primary_key=True, index=True)
    value = Column(String, nullable=False, index=True)
    type = Column(String, nullable=False, index=True)  # "username", "email", "domain"
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    scan_results = relationship("ScanResult", back_populates="target", cascade="all, delete-orphan")


class ScanResult(Base):
    __tablename__ = "scan_results"

    id = Column(Integer, primary_key=True, index=True)
    target_id = Column(Integer, ForeignKey("targets.id", ondelete="CASCADE"), nullable=False)
    platform = Column(String, nullable=False)
    url = Column(String, nullable=True)
    status = Column(String, nullable=False)  # "FOUND", "NOT_FOUND", "ERROR"
    response_code = Column(Integer, nullable=True)
    details = Column(String, nullable=True)
    checked_at = Column(DateTime(timezone=True), server_default=func.now())

    target = relationship("Target", back_populates="scan_results")


class Leak(Base):
    __tablename__ = "leaks"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, nullable=True)
    email = Column(String, nullable=True)
    password_hash = Column(String, nullable=True)
    source = Column(String, nullable=True, index=True)
    leak_date = Column(String, nullable=True)

    # Note: We will define indexes below the class definition to use advanced postgres parameters


# Define advanced indexes on leaks for sub-10ms queries on millions of rows
# 1. B-Tree Indexes for exact matches (fast mapping)
Index("idx_leaks_email_btree", Leak.email)
Index("idx_leaks_username_btree", Leak.username)

# 2. GIN Trigram Indexes for fast partial/fuzzy matches (e.g. searching email domains or substrings)
Index(
    "idx_leaks_email_gin",
    Leak.email,
    postgresql_using="gin",
    postgresql_ops={"email": "gin_trgm_ops"}
)
Index(
    "idx_leaks_username_gin",
    Leak.username,
    postgresql_using="gin",
    postgresql_ops={"username": "gin_trgm_ops"}
)


class Keyword(Base):
    __tablename__ = "keywords"

    id = Column(Integer, primary_key=True, index=True)
    value = Column(String, nullable=False, unique=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    alerts = relationship("Alert", back_populates="keyword", cascade="all, delete-orphan")


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, index=True)
    keyword_id = Column(Integer, ForeignKey("keywords.id", ondelete="CASCADE"), nullable=False)
    source_feed = Column(String, nullable=False)
    title = Column(String, nullable=False)
    url = Column(String, nullable=True)
    summary = Column(String, nullable=True)
    found_at = Column(DateTime(timezone=True), server_default=func.now())

    keyword = relationship("Keyword", back_populates="alerts")
