from pydantic import BaseModel, Field, EmailStr
from datetime import datetime
from typing import Optional, List

# Target Schemas
class TargetCreate(BaseModel):
    value: str = Field(..., description="Target value (username, email, or domain)")
    type: str = Field(..., description="Type of target: 'username', 'email', 'domain'")

class TargetResponse(BaseModel):
    id: int
    value: str
    type: str
    created_at: datetime

    class Config:
        from_attributes = True

# Scan Result Schemas
class ScanResultResponse(BaseModel):
    id: int
    target_id: int
    platform: str
    url: Optional[str] = None
    status: str
    response_code: Optional[int] = None
    checked_at: datetime

    class Config:
        from_attributes = True

# Task Status Schema
class TaskStatusResponse(BaseModel):
    task_id: str
    status: str
    result: Optional[dict] = None

# Leak Schemas
class LeakResponse(BaseModel):
    id: int
    username: Optional[str] = None
    email: Optional[str] = None
    source: Optional[str] = None
    leak_date: Optional[str] = None

    class Config:
        from_attributes = True

# Keyword Schemas
class KeywordCreate(BaseModel):
    value: str = Field(..., description="Keyword to watch (e.g., brand name, CVE, system component)")

class KeywordResponse(BaseModel):
    id: int
    value: str
    created_at: datetime

    class Config:
        from_attributes = True

# Alert Schemas
class AlertResponse(BaseModel):
    id: int
    keyword_id: int
    keyword_value: Optional[str] = None
    source_feed: str
    title: str
    url: Optional[str] = None
    summary: Optional[str] = None
    found_at: datetime

    class Config:
        from_attributes = True
