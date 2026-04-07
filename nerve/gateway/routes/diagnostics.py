"""Diagnostics and memorization sweep routes."""

from __future__ import annotations

import platform
import shutil
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from nerve.config import get_config
from nerve.gateway.auth import require_auth
from nerve.gateway.routes._deps import get_deps

router = APIRouter()


@router.get("/api/diagnostics")
async def diagnostics(user: dict = Depends(require_auth)):
    """System health and status information."""
    deps = get_deps()
    config = get_config()

    # Memory usage
    try:
        import resource
        mem_mb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
    except Exception:
        mem_mb = 0

    # Disk usage
    disk = shutil.disk_usage(str(config.workspace))

    # Cron logs (last 10)
    cron_logs = await deps.db.get_cron_logs(limit=10)

    # Source status — discover from registered runners + DB history
    sync_status = {}
    from nerve.gateway.server import _cron_service
    try:
        # Collect all known source names: registered runners + DB entries
        known_sources: set[str] = set()

        # From registered runners (includes sources that haven't run yet)
        if _cron_service and hasattr(_cron_service, "_source_runners"):
            for runner in _cron_service._source_runners:
                known_sources.add(runner.source.source_name)

        # From DB (includes sources that ran before but may no longer be configured)
        known_sources |= await deps.db.get_known_source_names()

        for source in sorted(known_sources):
            cursor = await deps.db.get_sync_cursor(source)
            last_run = await deps.db.get_last_source_run(source)
            sync_status[source] = {
                "cursor": cursor,
                "last_run": last_run.get("ran_at") if last_run else None,
                "records_fetched": last_run.get("records_fetched", 0) if last_run else 0,
                "records_processed": last_run.get("records_processed", 0) if last_run else 0,
                "error": last_run.get("error") if last_run else None,
            }
    except Exception:
        pass

    # Memorization sweep stats (from server.py global)
    from nerve.gateway.server import _memorize_stats

    # Count sessions needing memorization
    pending_count = 0
    try:
        pending = await deps.db.get_sessions_needing_memorization()
        pending_count = len(pending)
    except Exception:
        pass

    # Task / FTS health (async via DB method)
    tasks_health = await deps.db.get_task_health_stats()

    # Token usage analytics
    usage_data = {}
    try:
        usage_summary = await deps.db.get_usage_summary(days=7)
        cache_stats = await deps.db.get_cache_hit_rate(days=7)
        daily_usage = await deps.db.get_usage_by_period(days=7)
        source_usage = await deps.db.get_usage_by_source(days=7)

        # Add estimated cost to each daily entry
        from nerve.db.usage import estimate_cost_from_totals
        for day in daily_usage:
            day["est_cost_usd"] = round(estimate_cost_from_totals({
                "total_input": day.get("input_tokens", 0),
                "total_output": day.get("output_tokens", 0),
                "total_cache_read": day.get("cache_read", 0),
                "total_cache_creation": day.get("cache_creation", 0),
            }), 4)
        for src in source_usage:
            src["est_cost_usd"] = round(estimate_cost_from_totals({
                "total_input": src.get("input_tokens", 0),
                "total_output": src.get("output_tokens", 0),
                "total_cache_read": src.get("cache_read", 0),
                "total_cache_creation": src.get("cache_creation", 0),
            }), 4)

        usage_data = {
            "last_7d": usage_summary,
            "cache_hit_rate": cache_stats,
            "daily": daily_usage,
            "by_source": source_usage,
        }
    except Exception:
        pass

    return {
        "system": {
            "platform": platform.platform(),
            "python": platform.python_version(),
            "hostname": platform.node(),
            "memory_mb": round(mem_mb, 1),
            "disk_total_gb": round(disk.total / (1024**3), 1),
            "disk_free_gb": round(disk.free / (1024**3), 1),
        },
        "workspace": str(config.workspace),
        "sessions_count": len(await deps.engine.sessions.list_sessions()),
        "sync": sync_status,
        "recent_cron_logs": cron_logs,
        "tasks": tasks_health,
        "memorization": {
            **_memorize_stats,
            "sessions_pending": pending_count,
        },
        "usage": usage_data,
    }


@router.post("/api/memorization/sweep")
async def trigger_memorization_sweep(user: dict = Depends(require_auth)):
    """Manually trigger a memorization sweep."""
    deps = get_deps()
    if not deps.engine:
        raise HTTPException(status_code=503, detail="Engine not available")

    from nerve.gateway.server import _memorize_stats

    result = await deps.engine.run_memorization_sweep()
    _memorize_stats["last_run_at"] = datetime.now(timezone.utc).isoformat()
    _memorize_stats["last_result"] = result
    _memorize_stats["total_runs"] += 1
    return result
