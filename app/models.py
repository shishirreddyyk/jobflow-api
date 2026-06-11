"""Request and response schemas."""
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

TaskType = Literal["echo", "sleep", "compute"]


class JobCreate(BaseModel):
    task_type: TaskType = "echo"
    params: dict[str, Any] = Field(default_factory=dict)


class Job(BaseModel):
    id: str
    task_type: str
    status: str
    params: dict[str, Any] = Field(default_factory=dict)
    result: Optional[Any] = None
    error: Optional[str] = None
    created_at: float
    started_at: Optional[float] = None
    finished_at: Optional[float] = None
