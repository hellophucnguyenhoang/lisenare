from fastapi import APIRouter, HTTPException, status

from services import fsrs_service
from shared_schemas.fsrs import FSRSOptimizeRequest, FSRSOptimizeResponse

router = APIRouter(prefix="/fsrs", tags=["FSRS"])


@router.post("/optimize", response_model=FSRSOptimizeResponse)
def optimize_fsrs(request: FSRSOptimizeRequest) -> FSRSOptimizeResponse:
    try:
        optimal_params, optimal_retention = fsrs_service.optimize_parameters(
            request.review_logs
        )
        return FSRSOptimizeResponse(
            optimal_params=optimal_params,
            optimal_retention=optimal_retention,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Optimization failed: {e}",
        )
