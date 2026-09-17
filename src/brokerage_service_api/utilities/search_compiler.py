"""Code to call the upstream annotations API's and compile the results."""

import asyncio
import logging
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from fastapi import HTTPException, Request

from brokerage_service_api.models.search_model import Result, Results, SearchMetadata, SearchResults, Summary
from brokerage_service_api.schemas.source import SourceConfig
from brokerage_service_api.schemas.upstream import AnnotationSearchParams, AnnotationSearchRequest, SearchResultInfo
from brokerage_service_api.upstream.annotations import AnnotationApiClient
from brokerage_service_api.utilities.source import get_source_registry

logger = logging.getLogger(__name__)


def merge_search_info(blocks: list[SearchResultInfo | None]) -> SearchResultInfo | None:
    """Merge available source Info in source order; the first entry wins for duplicate IDs."""
    available = [block for block in blocks if block is not None]
    if not available:
        return None
    image_sets = {}
    annotation_sets = {}
    aphia_ids = {}
    for block in available:
        for item in block.image_sets:
            image_sets.setdefault(item.uuid, item)
        for item in block.annotation_sets:
            annotation_sets.setdefault(item.uuid, item)
        for item in block.aphia_ids:
            aphia_ids.setdefault(item.aphia_id, item)
    return SearchResultInfo(
        image_sets=list(image_sets.values()),
        annotation_sets=list(annotation_sets.values()),
        aphia_ids=list(aphia_ids.values()),
    )


class InvalidPageNumberError(Exception):
    """Raised when a page number is requested that is too large."""


class AnnotationsAPIFetcher:
    """Methods to fetch from upstream API's and return data."""

    def __init__(self, source: SourceConfig, params: AnnotationSearchRequest):
        """Initialise the class and make an attempt to call the upstream API."""
        self.source: SourceConfig = source
        self.params: AnnotationSearchRequest = params
        self._results: list[Result] = []
        self._summary: Summary | None = None
        self._info: SearchResultInfo | None = None

    def order_results(self) -> None:
        """Perform an in-place sort of the internal _results list."""
        # If no order_by is passed, return with no action taken.
        if self.params.order_by is None:
            return

        # Retrieve the ordering key and check if it matches the available ordering.
        order_by_key = self.params.order_by

        if order_by_key == "label_aphia_id":
            self._results.sort(key=lambda result: (result.label_aphia_id is None, result.label_aphia_id))
        elif order_by_key == "annotation_creation_datetime":
            self._results.sort(key=lambda result: result.annotation_creation_datetime)
        elif order_by_key == "label_name":
            self._results.sort(key=lambda result: result.label_name)

    def _make_request(self) -> None:
        """Make request to the upstream API and store the results in the class if available."""
        upstream_params = self._build_upstream_params(self.params).model_copy(
            update={"disable_pagination": True, "page": None}
        )
        response = asyncio.run(self._request_annotations(source=self.source, params=upstream_params))
        if not response.ok or response.data is None:
            raise HTTPException(
                502, detail={"code": "upstream_failed", "message": "An annotation source failed. Please retry."}
            )
        data = response.data
        if not isinstance(data.results, list) or len(data.results) != data.count or data.next is not None:
            raise HTTPException(
                502,
                detail={
                    "code": "upstream_invalid",
                    "message": "An annotation source returned an incomplete collection.",
                },
            )
        if self.params.add_info:
            self._info = data.meta.info
        if data.meta.summary is not None:
            self._summary = Summary(**data.meta.summary.model_dump())
        self._results = [self._construct_result_from_annotation(row, self.source.name) for row in data.results]
        self.order_results()

    async def _request_annotations(self, source: SourceConfig, params: AnnotationSearchParams) -> Any:
        """Fetch annotations using the shared upstream client."""
        client = AnnotationApiClient(source)
        try:
            return await client.search_annotations(params)
        finally:
            await client.aclose()

    @staticmethod
    def _build_upstream_params(params: AnnotationSearchRequest) -> AnnotationSearchParams:
        """Convert the brokerage search request into upstream client parameters."""
        return AnnotationSearchParams(
            aphia_ids=params.aphia_ids,
            order_by=params.order_by,
            page=params.page,
            page_size=params.page_size,
            add_summary=params.add_summary,
            deployment=params.deployment,
            exclude_annotation_set=params.exclude_annotation_set,
            exclude_aphia_ids=params.exclude_aphia_ids,
            exclude_image_set=params.exclude_image_set,
            fauna_attraction=params.fauna_attraction,
            image_set_name=params.image_set_name,
            include_descendants=params.include_descendants,
            marine_zone=params.marine_zone,
            max_lat=params.max_lat,
            max_lon=params.max_lon,
            min_lat=params.min_lat,
            min_lon=params.min_lon,
            name_part=params.name_part,
            platform=params.platform,
            project=params.project,
            add_info=params.add_info,
        )

    @staticmethod
    def _construct_result_from_annotation(raw_response: Any, source: str) -> Result:
        """Build a brokerage Result from an upstream annotation object."""
        annotation_data = raw_response.model_dump() if hasattr(raw_response, "model_dump") else dict(raw_response)

        annotation_data["annotation_creation_datetime"] = annotation_data.pop("creation_datetime", None)
        return Result.construct_instance_from_raw_response(annotation_data, source=source)

    @property
    def results(self) -> list[Result]:
        """Return the fetched results or an empty list."""
        return self._results

    @property
    def info(self) -> SearchResultInfo | None:
        """Return the full-search filter information, when requested and available."""
        return self._info

    @property
    def summary(self) -> Summary | None:
        """Return the fetched summary or None."""
        return self._summary


def results_with_pagination_applied(
    count: int, all_results: Results, page_size: int, page_number: int | None, request: Request
) -> SearchResults:
    """Apply pagination to the results and return a subset.

    Args:
        count: The total count of all results.
        all_results: All the upstream results, to perform the pagination upon.
        page_size: The number of results on one page.
        page_number: The page number to return.
        request: The raw request object.

    Returns:
    A SearchResults object with a subset of the results, and the prev|next fields populated.
    """
    page = page_number or 1
    total_pages = (count + page_size - 1) // page_size
    if page < 1 or page > max(1, total_pages):
        raise InvalidPageNumberError
    start = (page - 1) * page_size
    return SearchResults(
        count=count,
        next=str(request.url.include_query_params(page=page + 1)) if page < total_pages else None,
        previous=str(request.url.include_query_params(page=page - 1)) if page > 1 else None,
        results=all_results.annotations[start : start + page_size],
        meta=SearchMetadata(
            summary=all_results.summary,
            info=all_results.info,
            source_counts=dict(Counter(row.source for row in all_results.annotations)),
        ),
    )


def fetch_combined_results_from_annotation_apis(params: AnnotationSearchRequest, request: Request) -> SearchResults:
    """Call both annotations apis and return the combined results.

    Args:
        params: A model with all the required params to send upstream to the BODC/JNCC API's.
        request: The raw request object.

    Returns:
        SearchResults: An instance with the results built from both the BODC and JNCC API's.
    """
    # Use the source registry to determine what sources to pull from.
    sources_to_pull_results_from = get_source_registry().list()
    if not sources_to_pull_results_from:
        raise HTTPException(503, detail={"code": "no_sources", "message": "No search sources are configured."})

    # Setup instances of the API Fetcher according to what sources we have.
    api_fetchers = [AnnotationsAPIFetcher(source=source, params=params) for source in sources_to_pull_results_from]

    # Make the requests to the sources.
    with ThreadPoolExecutor() as executor:
        list(executor.map(lambda w: w._make_request(), api_fetchers))

    # Aggregate all the annotations and summaries in a single place.
    all_annotations, all_summaries = [], []

    # For each source ->
    for fetcher in api_fetchers:
        # If it has a summary, add it to 'all_summaries'.
        if isinstance(fetcher.summary, Summary):
            all_summaries.append(fetcher.summary)

        # Go through all the results and add to 'all_annotations'.
        for result in fetcher.results:
            all_annotations.append(result)

    if params.order_by:
        all_annotations.sort(
            key=lambda row: (getattr(row, params.order_by) is None, getattr(row, params.order_by), row.source, row.uuid)
        )
    all_results = Results(
        summary=sum(all_summaries) if len(all_summaries) == len(api_fetchers) else None,
        info=merge_search_info([fetcher.info for fetcher in api_fetchers]) if params.add_info else None,
        annotations=all_annotations,
    )

    # Perform any pagination that is required
    response = results_with_pagination_applied(
        count=len(all_annotations),
        all_results=all_results,
        page_size=params.page_size,
        page_number=params.page,
        request=request,
    )

    response.meta.source_counts = {fetcher.source.name: len(fetcher.results) for fetcher in api_fetchers}
    return response
