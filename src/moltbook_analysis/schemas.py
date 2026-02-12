from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class Agent(BaseModel):
    id: Optional[str] = None
    name: Optional[str] = None
    profile: Optional[str] = None
    url: Optional[str] = None
    created_at: Optional[str] = None
    raw: Dict[str, Any] = Field(default_factory=dict)


class Post(BaseModel):
    id: Optional[str] = None
    title: Optional[str] = None
    body: Optional[str] = None
    author_id: Optional[str] = None
    author_name: Optional[str] = None
    created_at: Optional[str] = None
    created_at_raw: Optional[str] = None
    updated_at: Optional[str] = None
    score: Optional[int] = None
    comment_count: Optional[int] = None
    views: Optional[int] = None
    submolt: Optional[str] = None
    url: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    source: Optional[str] = None
    filter: Optional[str] = None
    listing_rank: Optional[int] = None
    scrape_ts: Optional[str] = None
    raw: Dict[str, Any] = Field(default_factory=dict)


class Comment(BaseModel):
    id: Optional[str] = None
    post_id: Optional[str] = None
    parent_id: Optional[str] = None
    body: Optional[str] = None
    author_id: Optional[str] = None
    author_name: Optional[str] = None
    created_at: Optional[str] = None
    created_at_raw: Optional[str] = None
    score: Optional[int] = None
    depth: Optional[int] = None
    thread_path: Optional[str] = None
    scrape_ts: Optional[str] = None
    raw: Dict[str, Any] = Field(default_factory=dict)
