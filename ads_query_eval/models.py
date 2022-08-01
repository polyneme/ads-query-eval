from typing import List

from pydantic import BaseModel


class Query(BaseModel):
    id: str
    query: str
    run_ids: List[str]


class QueryTopicReviews(BaseModel):
    query: str
    bibcodes: List[str]
