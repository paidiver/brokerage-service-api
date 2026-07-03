"""Code to call the upstream annotations API's and compile the results."""

import asyncio
import re
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from itertools import batched
from typing import Any
from urllib.parse import parse_qs

from fastapi import Request

from brokerage_service_api.models.search_model import Result, ResultMetadata, Results, SearchResults, Summary
from brokerage_service_api.schemas.source import SourceConfig
from brokerage_service_api.schemas.upstream import AnnotationSearchParams, AnnotationSearchRequest
from brokerage_service_api.upstream.annotations import AnnotationApiClient
from brokerage_service_api.utilities.source import get_source_registry


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

    def order_results(self) -> None:
        """Perform an in-place sort of the internal _results list."""
        # If no order_by is passed, return with no action taken.
        if self.params.order_by is None:
            return

        # Retrieve the ordering key and check if it matches the available ordering.
        order_by_key = self.params.order_by

        if order_by_key == "label_aphia_id":
            self._results.sort(key=lambda result: result.label_aphia_id)
        if order_by_key == "annotation_creation_datetime":
            self._results.sort(key=lambda result: result.annotation_creation_datetime)
        if order_by_key == "label_name":
            self._results.sort(key=lambda result: result.label_name)

    def _make_request(self) -> None:
        """Make request to the upstream API and store the results in the class if available."""
        upstream_params = self._build_upstream_params(self.params)

        response = asyncio.run(self._request_annotations(source=self.source, params=upstream_params))
        if not getattr(response, "ok", False):
            error_message = getattr(getattr(response, "error", None), "message", None)
            if error_message is None:
                error_message = str(getattr(response, "error", ""))
            print("Something went wrong", error_message)
            return

        data = getattr(response, "data", None)
        if data is None:
            return

        results = getattr(data, "results", None)
        if results is None:
            return

        summary = getattr(results, "summary", None)
        if summary is not None:
            self._summary = Summary(**summary.model_dump())

        annotations = getattr(results, "annotations", None)
        if annotations is not None:
            self._results = [
                self._construct_result_from_annotation(result, source=self.source.name) for result in annotations
            ]
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
            page=params.page,
            page_size=params.page_size,
            calculate_summary=params.calculate_summary,
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
            return_image_annotation_name_info=params.return_image_annotation_name_info,
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
    def summary(self) -> Summary | None:
        """Return the fetched summary or None."""
        return self._summary


def construct_prev_and_next_response_fields(request_url: str, maximum_allowed_page: int) -> tuple[str | None]:
    """Use the incoming URL to construct the 'prev' and 'next' fields in the response.

    'prev' will stay as None if any the following conditions are met:
        - page is 1
        - An error is raised whilst parsing for the page value

    'prev' will change if the current page is > 1.

    -----------------
    'next_' will stay as None if the following conditions are met:
        - An error is raised whilst parsing for the page value

    'next_' will stay as the current value if it is the maximum allowed value. For example if the
    user is on page 2, and this is the last page, then 2 will be returned.

    'next_' will update by +1 if allowable. For example is there are 4 batches of results, and the user is on
    page 3, then 4 will be returned.

    """
    # Define the 'prev' and 'next' as None, unless further logic dictates they need to be changed.
    prev, next_ = None, None
    request_fields = parse_qs(request_url)
    minimum_page_value = 2

    try:
        current_page_value = int(request_fields["page"][0])
    except KeyError:
        # If no page is set in the query, assume page 1.
        current_page_value = 1
    except Exception:
        return prev, next_

    if current_page_value >= minimum_page_value:
        prev = str(current_page_value - 1)
    elif current_page_value == 1:
        prev = None

    # If the current page is the maximum allowable page, then set to that.
    if current_page_value == maximum_allowed_page:
        next_ = str(current_page_value)

    # If the current page is less than the maxium allowable, increment by 1.
    elif current_page_value < maximum_allowed_page:
        next_ = str(current_page_value + 1)

    return prev, next_


def construct_previous_and_next_urls(
    incoming_url: str, previous_value: str | None, next_value: str | None
) -> str | None:
    """Use the incoming URL, and the potential previous/next values to form the new URLS.

    Args:
        incoming_url: the incoming URL.
        previous_value: If a string, make a new url with the value.
        next_value: If a string, make a new url with the value

    Returns:
    Either a url, or None.
    """
    previous_url = re.sub("&page=\\d+", f"&page={previous_value}", incoming_url) if previous_value is not None else None

    if next_value is not None:
        if "&page=" in incoming_url:
            next_url = re.sub(r"&page=\d+", f"&page={next_value}", incoming_url)
        else:
            next_url = incoming_url + f"&page={next_value}"
    else:
        next_url = None

    return previous_url, next_url


def results_with_pagination_applied(
    count: int, all_results: Results, page_size: int, page_number: int | None, request: Request
) -> Results:
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
    # Prepare the result metadata using all the results.
    source_count = Counter(result.source for result in all_results.annotations)
    result_metadata = ResultMetadata.construct_result_metadata_with_generic_sources(raw_data=source_count)

    # Batch the annotations into the required size (100 is the default).
    batched_annotations = list(batched(all_results.annotations, n=page_size))

    # Fetch the values needed for the previous and next URL's.
    prev_field, next_field = construct_prev_and_next_response_fields(
        request_url=str(request.url), maximum_allowed_page=len(batched_annotations)
    )

    # Use the values from the previous function calls to now build the previous and next URL's.
    previous_url, next_url = construct_previous_and_next_urls(
        incoming_url=str(request.url), previous_value=prev_field, next_value=next_field
    )

    # If no page number is passed, then just return the first page of results.
    # This is the default path, so the user will just see 100 results or less.
    if page_number is None:
        return SearchResults(
            previous=previous_url,
            next=next_url,
            count=count,  #
            results=Results(summary=all_results.summary, annotations=batched_annotations[0]),
            result_metadata=result_metadata,
        )

    # If the user passes a page number, return that specific batch or raise an error if not applicable.
    try:
        specified_annotation_batch = batched_annotations[page_number - 1]
    except IndexError:
        raise InvalidPageNumberError from None

    paginated_results = Results(summary=all_results.summary, annotations=specified_annotation_batch)
    return SearchResults(
        previous=previous_url, next=next_url, count=count, results=paginated_results, result_metadata=result_metadata
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

    # Setup instances of the API Fetcher according to what sources we have.
    api_fetchers = [AnnotationsAPIFetcher(source=source, params=params) for source in sources_to_pull_results_from]

    # Make the requests to the sources.
    with ThreadPoolExecutor() as executor:
        executor.map(lambda w: w._make_request(), api_fetchers)

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

    all_results = Results(summary=sum(all_summaries) if all_summaries else None, annotations=all_annotations)

    # Perform any pagination that is required
    return results_with_pagination_applied(
        count=len(all_annotations),
        all_results=all_results,
        page_size=params.page_size,
        page_number=params.page,
        request=request,
    )
