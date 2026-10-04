"""Authenticated category CRUD endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status

from app.domain.entities import Category, User, require_id
from app.infrastructure.web.dependencies import get_category_repository, get_current_user
from app.interfaces.schemas.category import (
    CategoryCreateRequest,
    CategoryResponse,
    CategoryUpdateRequest,
)
from app.use_cases.interfaces.category_repository import CategoryRepositoryInterface

router = APIRouter(prefix="/categories", tags=["Categories"])


def _get_owned_category(
    category_id: int, user_id: int, repo: CategoryRepositoryInterface
) -> Category:
    category = repo.get_by_id_for_user(category_id, user_id)
    if category is None:
        raise HTTPException(status_code=404, detail="Category not found")
    return category


@router.post("/", response_model=CategoryResponse, status_code=status.HTTP_201_CREATED)
def create_category(
    payload: CategoryCreateRequest,
    current_user: User = Depends(get_current_user),
    repo: CategoryRepositoryInterface = Depends(get_category_repository),
) -> CategoryResponse:
    user_id = require_id(current_user.id)
    name = payload.name.strip()
    if repo.get_by_name_for_user(name, user_id):
        raise HTTPException(status_code=409, detail="A category with this name already exists")
    category = repo.create(Category(user_id=user_id, name=name, description=payload.description))
    return CategoryResponse.model_validate(category)


@router.get("/", response_model=list[CategoryResponse])
def list_categories(
    current_user: User = Depends(get_current_user),
    repo: CategoryRepositoryInterface = Depends(get_category_repository),
) -> list[CategoryResponse]:
    return [
        CategoryResponse.model_validate(item)
        for item in repo.list_by_user(require_id(current_user.id))
    ]


@router.get("/{id}", response_model=CategoryResponse)
def get_category_detail(
    id: int,
    current_user: User = Depends(get_current_user),
    repo: CategoryRepositoryInterface = Depends(get_category_repository),
) -> CategoryResponse:
    return CategoryResponse.model_validate(
        _get_owned_category(id, require_id(current_user.id), repo)
    )


@router.put("/{id}", response_model=CategoryResponse)
def update_category(
    id: int,
    payload: CategoryUpdateRequest,
    current_user: User = Depends(get_current_user),
    repo: CategoryRepositoryInterface = Depends(get_category_repository),
) -> CategoryResponse:
    user_id = require_id(current_user.id)
    category = _get_owned_category(id, user_id, repo)
    if payload.name is not None:
        name = payload.name.strip()
        duplicate = repo.get_by_name_for_user(name, user_id)
        if duplicate is not None and duplicate.id != category.id:
            raise HTTPException(status_code=409, detail="A category with this name already exists")
        category.name = name
    if payload.description is not None:
        category.description = payload.description
    return CategoryResponse.model_validate(repo.update(category))


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_category(
    id: int,
    current_user: User = Depends(get_current_user),
    repo: CategoryRepositoryInterface = Depends(get_category_repository),
) -> None:
    _get_owned_category(id, require_id(current_user.id), repo)
    repo.delete(id)
