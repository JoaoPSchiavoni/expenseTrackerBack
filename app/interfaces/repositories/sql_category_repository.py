from sqlalchemy.orm import Session

from app.domain.entities import Category
from app.infrastructure.database.models import CategoryModel
from app.use_cases.interfaces.category_repository import CategoryRepositoryInterface


class SqlCategoryRepository(CategoryRepositoryInterface):
    def __init__(self, session: Session) -> None:
        self.session = session

    @staticmethod
    def _to_entity(model: CategoryModel) -> Category:
        return Category(
            id=model.id,
            user_id=model.user_id,
            name=model.name,
            description=model.description,
        )

    def create(self, category: Category) -> Category:
        model = CategoryModel(
            user_id=category.user_id,
            name=category.name,
            description=category.description,
        )
        self.session.add(model)
        self.session.flush()
        self.session.refresh(model)
        return self._to_entity(model)

    def get_by_id_for_user(self, category_id: int, user_id: int) -> Category | None:
        model = (
            self.session.query(CategoryModel)
            .filter(CategoryModel.id == category_id, CategoryModel.user_id == user_id)
            .first()
        )
        return self._to_entity(model) if model else None

    def get_by_name_for_user(self, name: str, user_id: int) -> Category | None:
        model = (
            self.session.query(CategoryModel)
            .filter(CategoryModel.user_id == user_id, CategoryModel.name.ilike(name))
            .first()
        )
        return self._to_entity(model) if model else None

    def list_by_user(self, user_id: int) -> list[Category]:
        models = (
            self.session.query(CategoryModel)
            .filter(CategoryModel.user_id == user_id)
            .order_by(CategoryModel.name)
            .all()
        )
        return [self._to_entity(model) for model in models]

    def update(self, category: Category) -> Category:
        model = self.session.get(CategoryModel, category.id)
        if model is None:
            raise ValueError("Category not found")
        model.name = category.name
        model.description = category.description
        self.session.flush()
        self.session.refresh(model)
        return self._to_entity(model)

    def delete(self, category_id: int) -> None:
        model = self.session.get(CategoryModel, category_id)
        if model is None:
            raise ValueError("Category not found")
        self.session.delete(model)
        self.session.flush()
