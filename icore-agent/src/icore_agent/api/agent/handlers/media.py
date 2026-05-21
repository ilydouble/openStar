"""Image and structured data attachment handlers."""

from pathlib import Path
from typing import Annotated

from fastapi import Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

from ....application.account import AccountService
from ....config import settings
from ....memory.attachment_store import attachments
from ...dependencies import get_account_service, get_current_user
from ..schemas.attachment import DataAttachResponse, ImageAttachResponse

_SUPPORTED_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif"}
_SUPPORTED_DATA_EXTS = {".csv", ".xlsx", ".xls"}


async def attach_image(
    file: Annotated[UploadFile, File(description="JPG, PNG, WEBP, BMP or GIF image")],
    session_id: Annotated[str, Form(description="Session ID to attach the image to")],
    user: dict = Depends(get_current_user),
    account_service: AccountService = Depends(get_account_service),
) -> ImageAttachResponse:
    """Upload an image and attach it to the session."""
    allowed, reason = account_service.check_quota(user["id"], "images")
    if not allowed:
        raise HTTPException(status_code=402, detail=reason)
    filename = file.filename or "image"
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in _SUPPORTED_IMAGE_EXTS:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported image type '{ext}'. Supported: {sorted(_SUPPORTED_IMAGE_EXTS)}",
        )
    data = await file.read()
    limit = settings.image_upload_max_mb * 1024 * 1024
    if len(data) > limit:
        raise HTTPException(
            status_code=413,
            detail=f"Image exceeds {settings.image_upload_max_mb} MB limit",
        )
    record = await attachments.add_image(session_id, filename, data)
    account_service.consume_quota(user["id"], "images")
    return ImageAttachResponse(
        filename=record["filename"],
        ref=record["ref"],
        size=record["size"],
    )


async def get_image(
    session_id: str,
    filename: str,
    user: dict = Depends(get_current_user),
):
    """Serve a session-scoped image from local storage."""
    _ = user
    if "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    path = Path(settings.image_save_dir) / session_id / filename
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="Image not found")
    return FileResponse(path)


async def attach_data(
    file: Annotated[UploadFile, File(description="CSV, XLSX or XLS file")],
    session_id: Annotated[str, Form(description="Session ID to attach the data file to")],
    user: dict = Depends(get_current_user),
    account_service: AccountService = Depends(get_account_service),
) -> DataAttachResponse:
    """Upload a CSV or Excel file to the session workspace for data analysis."""
    allowed, reason = account_service.check_quota(user["id"], "attachments")
    if not allowed:
        raise HTTPException(status_code=402, detail=reason)
    filename = file.filename or "data"
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in _SUPPORTED_DATA_EXTS:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported data type '{ext}'. Supported: {sorted(_SUPPORTED_DATA_EXTS)}",
        )
    data = await file.read()
    limit = settings.data_upload_max_mb * 1024 * 1024
    if len(data) > limit:
        raise HTTPException(
            status_code=413,
            detail=f"Data file exceeds {settings.data_upload_max_mb} MB limit",
        )
    record = await attachments.add_data(session_id, filename, data)
    account_service.consume_quota(user["id"], "attachments")
    return DataAttachResponse(
        filename=record["filename"],
        ref=record["ref"],
        size=record["size"],
        ext=record["ext"],
        row_count=record.get("row_count"),
        columns=record.get("columns") or [],
        preview_md=record.get("preview_md") or "",
        preview_error=record.get("preview_error") or "",
    )
