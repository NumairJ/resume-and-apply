import uuid
from typing import Any, Generic, TypeVar

from sqlalchemy import select
from sqlalchemy.orm import Session

from models.base import Base

ModelT = TypeVar("ModelT", bound=Base)


class BaseRepository(Generic[ModelT]):
    """CRUD shared by every aggregate.

    Nine aggregates each needing get/list/create/update/delete is the one place in
    this codebase where a generic base actually removes code rather than adding a
    layer. Subclasses add only the queries specific to their table.

    Repositories never commit. The caller owns the transaction boundary, which is what
    lets a service write several tables atomically and lets tests roll everything back.
    """

    model: type[ModelT]

    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, id: uuid.UUID) -> ModelT | None:
        return self.session.get(self.model, id)

    def list(self) -> list[ModelT]:
        return list(self.session.scalars(select(self.model)))

    def create(self, **values: Any) -> ModelT:
        instance = self.model(**values)
        self.session.add(instance)
        self.session.flush()
        return instance

    def update(self, instance: ModelT, **values: Any) -> ModelT:
        for field, value in values.items():
            setattr(instance, field, value)
        self.session.flush()
        return instance

    def delete(self, instance: ModelT) -> None:
        self.session.delete(instance)
        self.session.flush()
