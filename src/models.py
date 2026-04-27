"""Pydantic models. Most fields are Optional because the upstream LL2 API
omits values for older or in-progress missions."""
from typing import Optional, List, Any
from pydantic import BaseModel, Field


class LaunchStatus(BaseModel):
    id: Optional[int] = None
    name: Optional[str] = None
    abbrev: Optional[str] = None
    description: Optional[str] = None


class Orbit(BaseModel):
    id: Optional[int] = None
    name: Optional[str] = None
    abbrev: Optional[str] = None


class Mission(BaseModel):
    id: Optional[int] = None
    name: Optional[str] = None
    description: Optional[str] = None
    type: Optional[str] = None
    orbit: Optional[Orbit] = None


class RocketConfig(BaseModel):
    id: Optional[int] = None
    name: Optional[str] = None
    family: Optional[str] = None
    full_name: Optional[str] = None
    variant: Optional[str] = None


class Rocket(BaseModel):
    id: Optional[int] = None
    configuration: Optional[RocketConfig] = None


class Agency(BaseModel):
    id: Optional[int] = None
    name: Optional[str] = None
    type: Optional[str] = None
    url: Optional[str] = None


class Location(BaseModel):
    id: Optional[int] = None
    name: Optional[str] = None
    country_code: Optional[str] = None


class Pad(BaseModel):
    id: Optional[int] = None
    name: Optional[str] = None
    latitude: Optional[str] = None
    longitude: Optional[str] = None
    location: Optional[Location] = None


class Launch(BaseModel):
    """One launch record from LL2."""
    id: str
    name: Optional[str] = None
    status: Optional[LaunchStatus] = None
    net: Optional[str] = None  # "no earlier than" - ISO 8601
    window_start: Optional[str] = None
    window_end: Optional[str] = None
    launch_service_provider: Optional[Agency] = None
    rocket: Optional[Rocket] = None
    mission: Optional[Mission] = None
    pad: Optional[Pad] = None


class JobRequest(BaseModel):
    """What POST /jobs accepts."""
    plot_type: str = Field(..., description="One of: success_rate_over_time, frequency_by_provider, outcomes_pie")
    provider: Optional[str] = Field(None, description="Filter by launch provider name (for outcomes_pie)")
    rocket_family: Optional[str] = Field(None, description="Filter by rocket family (for outcomes_pie)")
    start_year: Optional[int] = None
    end_year: Optional[int] = None


class Job(BaseModel):
    """What lives in the jobs db."""
    id: str
    status: str  # queued, in_progress, complete, failed
    plot_type: str
    provider: Optional[str] = None
    rocket_family: Optional[str] = None
    start_year: Optional[int] = None
    end_year: Optional[int] = None
    submitted_at: str
    completed_at: Optional[str] = None
    error: Optional[str] = None
