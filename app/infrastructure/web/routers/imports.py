"""CSV/OFX upload, preview, and atomic confirmation endpoints."""

import json
from collections.abc import Sequence

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status

from app.domain.entities import User, require_id
from app.domain.exceptions import ImportNotFoundError, InvalidImportStateError
from app.domain.imports import ImportBatch, ImportItem
from app.infrastructure.web.dependencies import (
    get_current_user,
    get_import_statements_use_case,
)
from app.interfaces.schemas.imports import (
    ImportBatchResponse,
    ImportConfirmRequest,
    ImportItemResponse,
    ImportPreviewResponse,
)
from app.use_cases.imports import ImportStatementsUseCase

router = APIRouter(prefix="/imports", tags=["Imports"])


def _response(batch: ImportBatch, items: Sequence[ImportItem]) -> ImportPreviewResponse:
    return ImportPreviewResponse(
        batch=ImportBatchResponse.model_validate(batch),
        items=[ImportItemResponse.model_validate(item) for item in items],
    )


def _parse_options(value: str | None) -> dict[str, str] | None:
    if value is None:
        return None
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=422, detail="options must be valid JSON") from exc
    if not isinstance(parsed, dict) or not all(
        isinstance(key, str) and isinstance(item, str) for key, item in parsed.items()
    ):
        raise HTTPException(status_code=422, detail="options must be a string-to-string object")
    return parsed


@router.post("/", response_model=ImportPreviewResponse, status_code=status.HTTP_201_CREATED)
def upload_statement(
    wallet_id: int = Form(..., gt=0),
    file: UploadFile = File(...),
    options: str | None = Form(None),
    current_user: User = Depends(get_current_user),
    use_case: ImportStatementsUseCase = Depends(get_import_statements_use_case),
) -> ImportPreviewResponse:
    filename = file.filename or "statement"
    content = file.file.read(use_case.max_file_size_bytes + 1)
    try:
        batch, items = use_case.create_preview(
            user_id=require_id(current_user.id),
            wallet_id=wallet_id,
            filename=filename,
            content=content,
            timezone_name=current_user.timezone,
            options=_parse_options(options),
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _response(batch, items)


@router.get("/", response_model=list[ImportBatchResponse])
def list_imports(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    use_case: ImportStatementsUseCase = Depends(get_import_statements_use_case),
) -> list[ImportBatchResponse]:
    return [
        ImportBatchResponse.model_validate(batch)
        for batch in use_case.list_batches(
            user_id=require_id(current_user.id), limit=limit, offset=offset
        )
    ]


@router.get("/{batch_id}", response_model=ImportBatchResponse)
def get_import(
    batch_id: int,
    current_user: User = Depends(get_current_user),
    use_case: ImportStatementsUseCase = Depends(get_import_statements_use_case),
) -> ImportBatchResponse:
    try:
        batch, _ = use_case.get_preview(batch_id=batch_id, user_id=require_id(current_user.id))
    except ImportNotFoundError as exc:
        raise HTTPException(status_code=404, detail=exc.message) from exc
    return ImportBatchResponse.model_validate(batch)


@router.get("/{batch_id}/preview", response_model=ImportPreviewResponse)
def get_import_preview(
    batch_id: int,
    current_user: User = Depends(get_current_user),
    use_case: ImportStatementsUseCase = Depends(get_import_statements_use_case),
) -> ImportPreviewResponse:
    try:
        batch, items = use_case.get_preview(batch_id=batch_id, user_id=require_id(current_user.id))
    except ImportNotFoundError as exc:
        raise HTTPException(status_code=404, detail=exc.message) from exc
    return _response(batch, items)


@router.post("/{batch_id}/confirm", response_model=ImportPreviewResponse)
def confirm_import(
    batch_id: int,
    payload: ImportConfirmRequest,
    current_user: User = Depends(get_current_user),
    use_case: ImportStatementsUseCase = Depends(get_import_statements_use_case),
) -> ImportPreviewResponse:
    row_options = {row.row_number: (row.include, row.category_id) for row in payload.rows}
    try:
        batch, items = use_case.confirm(
            batch_id=batch_id,
            user_id=require_id(current_user.id),
            base_currency=current_user.base_currency,
            timezone_name=current_user.timezone,
            default_category_id=payload.default_category_id,
            row_options=row_options,
        )
    except ImportNotFoundError as exc:
        raise HTTPException(status_code=404, detail=exc.message) from exc
    except InvalidImportStateError as exc:
        raise HTTPException(status_code=409, detail=exc.message) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _response(batch, items)


@router.delete("/{batch_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_import(
    batch_id: int,
    current_user: User = Depends(get_current_user),
    use_case: ImportStatementsUseCase = Depends(get_import_statements_use_case),
) -> None:
    try:
        use_case.delete(batch_id=batch_id, user_id=require_id(current_user.id))
    except ImportNotFoundError as exc:
        raise HTTPException(status_code=404, detail=exc.message) from exc
    except InvalidImportStateError as exc:
        raise HTTPException(status_code=409, detail=exc.message) from exc
