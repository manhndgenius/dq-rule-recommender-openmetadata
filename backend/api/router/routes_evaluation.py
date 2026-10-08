from fastapi import APIRouter, Query

from backend.config.settings import settings
from backend.evaluation.evaluation_service import evaluation_service
from backend.evaluation.golden_evaluator import golden_dataset_evaluator


router = APIRouter(prefix=settings.api_prefix, tags=["evaluation"])


@router.get("/evaluation/summary")
def get_evaluation_summary():
    """Chạy và trả về báo cáo benchmark chất lượng (Coverage, Safety, Latency) trên 18 bảng dataset y tế."""
    return evaluation_service.get_summary()


@router.get("/evaluation/golden-benchmark")
def get_golden_benchmark(force_refresh: bool = Query(False, description="Bắt buộc tính toán lại benchmark")):
    """
    Chạy bộ kiểm thử định lượng Golden Dataset Benchmark đối chiếu chuẩn Synthea Data Dictionary
    trên 3 bảng cốt lõi: patients, medications, observations.
    Tính toán chi tiết Precision, Recall, F1-Score, và Tỉ lệ bắt lỗi (Defect Detection Rate).
    """
    return golden_dataset_evaluator.run_benchmark(force_refresh=force_refresh)
