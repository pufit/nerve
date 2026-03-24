"""houseofagents API routes — status, pipeline CRUD, binary install."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from nerve.config import get_config
from nerve.gateway.auth import require_auth

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/api/houseofagents/status")
async def hoa_status(user: dict = Depends(require_auth)):
    """Check if houseofagents is enabled, installed, and its version."""
    config = get_config()
    enabled = config.houseofagents.enabled
    available = False
    version = None
    default_mode = config.houseofagents.default_mode
    default_agents = config.houseofagents.default_agents

    if enabled:
        from nerve.houseofagents import get_hoa_service
        try:
            svc = get_hoa_service()
            available = svc.is_available()
            if available:
                version = await svc.get_version()
        except RuntimeError:
            pass  # Service not initialised

    return {
        "enabled": enabled,
        "available": available,
        "version": version,
        "default_mode": default_mode,
        "default_agents": default_agents,
    }


@router.get("/api/houseofagents/pipelines")
async def list_pipelines(user: dict = Depends(require_auth)):
    config = get_config()
    if not config.houseofagents.enabled:
        raise HTTPException(400, "houseofagents is not enabled")
    from nerve.houseofagents.pipelines import PipelineManager
    pm = PipelineManager(config.houseofagents.pipelines_dir)
    return {"pipelines": pm.list_pipelines()}


@router.get("/api/houseofagents/pipelines/{pipeline_id}")
async def get_pipeline(pipeline_id: str, user: dict = Depends(require_auth)):
    config = get_config()
    if not config.houseofagents.enabled:
        raise HTTPException(400, "houseofagents is not enabled")
    from nerve.houseofagents.pipelines import PipelineManager
    pm = PipelineManager(config.houseofagents.pipelines_dir)
    pipeline = pm.get_pipeline(pipeline_id)
    if not pipeline:
        raise HTTPException(404, "Pipeline not found")
    return pipeline


class PipelineSaveRequest(BaseModel):
    content: str


@router.put("/api/houseofagents/pipelines/{pipeline_id}")
async def save_pipeline(
    pipeline_id: str,
    req: PipelineSaveRequest,
    user: dict = Depends(require_auth),
):
    config = get_config()
    if not config.houseofagents.enabled:
        raise HTTPException(400, "houseofagents is not enabled")
    from nerve.houseofagents.pipelines import PipelineManager
    pm = PipelineManager(config.houseofagents.pipelines_dir)
    path = pm.save_pipeline(pipeline_id, req.content)
    return {"id": pipeline_id, "path": str(path)}


@router.delete("/api/houseofagents/pipelines/{pipeline_id}")
async def delete_pipeline(pipeline_id: str, user: dict = Depends(require_auth)):
    config = get_config()
    if not config.houseofagents.enabled:
        raise HTTPException(400, "houseofagents is not enabled")
    from nerve.houseofagents.pipelines import PipelineManager
    pm = PipelineManager(config.houseofagents.pipelines_dir)
    if not pm.delete_pipeline(pipeline_id):
        raise HTTPException(404, "Pipeline not found")
    return {"deleted": True}


@router.post("/api/houseofagents/install")
async def install_binary(user: dict = Depends(require_auth)):
    """Trigger binary download/compilation."""
    config = get_config()
    if not config.houseofagents.enabled:
        raise HTTPException(400, "houseofagents is not enabled")
    from nerve.houseofagents import get_hoa_service
    svc = get_hoa_service()
    path = await svc.ensure_binary()
    version = await svc.get_version()
    return {"installed": True, "path": str(path), "version": version}
