from __future__ import annotations
from abc import ABC, abstractmethod
from storage.models import Article

class BaseSource(ABC):
    def __init__(self, name: str, topics: list[str]):
        self.name = name
        self.topics = topics

    @abstractmethod
    async def fetch(self) -> list[Article]:
        ...
