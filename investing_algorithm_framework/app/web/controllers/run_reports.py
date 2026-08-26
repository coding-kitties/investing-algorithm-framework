import logging

from dependency_injector.wiring import inject, Provide
from fastapi import APIRouter, Depends, Request
from werkzeug.datastructures import MultiDict

from investing_algorithm_framework.app.web.responses import create_response
from investing_algorithm_framework.app.web.schemas import RunReportSerializer

logger = logging.getLogger("investing_algorithm_framework")

router = APIRouter()


@router.get("/api/run-reports")
@inject
def list_run_reports(
    request: Request,
    run_report_service=Depends(Provide["run_report_service"]),
):
    """
    List persisted run reports, most-recently-completed first.

    Supports pagination via ``?page=`` / ``?per_page=`` query params
    (defaults: page 1, 10 per page); also filterable by
    ``?algorithm_id=`` and ``?environment=``.
    """
    run_reports = run_report_service.get_all(
        MultiDict(request.query_params.multi_items())
    )
    return create_response(run_reports, RunReportSerializer())
