from __future__ import annotations

from fastapi import APIRouter

from src.api.schemas import ContractResponse
from src.state import ReviewStateModel

router = APIRouter(prefix="/api/v1/contracts", tags=["contracts"])


@router.get("/review-state", response_model=ContractResponse)
def review_state_contract() -> ContractResponse:
    """Expose the ReviewState runtime schema for teammates."""
    return ContractResponse(
        contract_name="ReviewState",
        contract_schema=ReviewStateModel.model_json_schema(),
    )
