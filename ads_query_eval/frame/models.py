from datetime import datetime
from typing import List, Dict, Optional

from pydantic import BaseModel, Field, validator


class Query(BaseModel):
    id: str = Field(..., alias="@id")
    query_literal: str


class Operation(BaseModel):
    id: str = Field(..., alias="@id")
    done: bool = False
    done_at: Optional[datetime]
    status: str


class RetrievedItem(BaseModel):
    id: str = Field(..., alias="@id")
    retrieval: str
    ads_bibcode: str


class Retrieval(Operation):
    query: str
    s3_key: str
    items: List[str]


class RetrievedItemContent(BaseModel):
    citations: Dict[str, int] = Field(..., alias="[citations]")
    num_citations: Optional[int]
    num_references: Optional[int]
    abstract: str
    bibcode: str
    citation_count_norm: float
    doctype: str
    highlighting: Dict[str, List[str]]
    pubdate: str
    title: str
    author: List[str]

    @validator("title", pre=True, always=True)
    def title_as_str(cls, v):
        return "\n".join(v) if isinstance(v, list) else v

    @validator("num_citations", "num_references", always=True)
    def get_from_toplevel_field(cls, v, values, field):
        return v or values.get("citations")[field.name]


class ItemOfEvaluation(BaseModel):
    id: str = Field(..., alias="@id")
    evaluation: str
    retrieved_item: str
    evaluation_status: str
    relevance: str
    uncertainty: Optional[str]


class Evaluation(Operation):
    retrieval: str
    evaluator: str
    p_at_25: Optional[float]
    r_at_1000: Optional[float]


class User(BaseModel):
    id: str = Field(..., alias="@id")
    email_address: str
    username: str
