from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.faults import faults, faults_enabled


def require_faults_enabled() -> None:
    if not faults_enabled():
        raise HTTPException(status_code=404, detail="Not Found")


router = APIRouter(
    prefix="/faults",
    tags=["faults"],
    dependencies=[Depends(require_faults_enabled)],
)


@router.get("")
def fault_status() -> dict:
    return faults.status()


@router.post("/cpu")
def start_cpu() -> dict:
    faults.start_cpu()
    return faults.status()


@router.delete("/cpu")
def stop_cpu() -> dict:
    faults.stop_cpu()
    return faults.status()


@router.post("/memory")
def start_memory() -> dict:
    faults.start_memory()
    return faults.status()


@router.delete("/memory")
def stop_memory() -> dict:
    faults.stop_memory()
    return faults.status()


@router.post("/latency")
def start_latency(delay_ms: int = Query(default=1000, ge=1, le=10_000)) -> dict:
    faults.start_latency(delay_ms)
    return faults.status()


@router.delete("/latency")
def stop_latency() -> dict:
    faults.stop_latency()
    return faults.status()


@router.post("/crash")
def crash() -> dict:
    faults.crash()
    return {"status": "crashing"}
