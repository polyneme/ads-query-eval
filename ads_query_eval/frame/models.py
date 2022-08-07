from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, AnyHttpUrl

Resource = AnyHttpUrl


class HasID(BaseModel):
    id: Resource = Field(..., alias="@id")


class Query(HasID):
    query_literal: str


class Operation(HasID):
    pass


class Retrieval(Operation):
    query: Resource
    retrieval_status: str
    completed_at: Optional[datetime]


class RetrievedItemsList(HasID):
    retrieval: Resource
    mrr: Optional[float]
