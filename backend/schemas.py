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
    details: Optional[str] = None
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


# AI Copilot Schemas
class ChatMessage(BaseModel):
    role: str = Field(..., description="Role of the sender: 'user' or 'assistant'")
    content: str = Field(..., description="Text content of the message")

class AIChatRequest(BaseModel):
    message: str = Field(..., description="Message/question sent to the Cyber Analyst Copilot")
    context_type: Optional[str] = Field("general", description="Context area: 'general', 'leaks', 'alerts'")
    history: Optional[List[ChatMessage]] = Field(default=None, description="Discussion history of the session")

class AIChatResponse(BaseModel):
    response: str
    suggested_actions: Optional[List[str]] = None


# AI Remediation Schemas
class RemediationRequest(BaseModel):
    code: str = Field(..., description="The vulnerable code snippet to analyze")
    language: str = Field(..., description="Programming language of the snippet (e.g. python, javascript, php)")
    vulnerability_description: Optional[str] = Field(None, description="Optional description of the vulnerability")

class RemediationResponse(BaseModel):
    explanation: str = Field(..., description="Explanation of the vulnerability and how to fix it")
    fixed_code: str = Field(..., description="The corrected, secure version of the code snippet")


# RSS Feed Schemas
class FeedCreate(BaseModel):
    name: str = Field(..., description="Nom du flux RSS (ex: BleepingComputer)")
    url: str = Field(..., description="URL absolue du flux RSS XML")

class FeedResponse(BaseModel):
    id: int
    name: str
    url: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True

class FeedUpdate(BaseModel):
    name: Optional[str] = None
    url: Optional[str] = None
    is_active: Optional[bool] = None

# Stats Schema
class TargetStats(BaseModel):
    total: int
    usernames: int
    emails: int
    domains: int

class SystemStatsResponse(BaseModel):
    targets: TargetStats
    leaks_count: int
    alerts_count: int
    scans_count: int

