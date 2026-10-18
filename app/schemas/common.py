import math
from typing import Generic, List, TypeVar
from pydantic import computed_field
from app.schemas.base import CamelCaseModel

T = TypeVar("T")


class PagedResult(CamelCaseModel, Generic[T]):
    items: List[T]
    page: int
    page_size: int
    total_count: int

    @computed_field
    @property
    def total_pages(self) -> int:
        return 0 if self.page_size == 0 else math.ceil(self.total_count / self.page_size)

