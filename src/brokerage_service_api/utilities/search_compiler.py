"""Code to call the JNCC and BODC annotations API and compile the results."""
import requests as rq
from brokerage_service_api.models.search_model import Result, SearchResults

JNCC_ANNOTATIONS_API_ENDPOINT = "http://localhost:8019/api/annotations/search/"
BODC_ANNOTATIONS_API_ENDPOINT = "http://localhost:8018/api/annotations/search/"



def make_request():
    return {
  "count": 2,
  "next": "null",
  "previous": "null",
  "results": {
    "annotations": [
      {
        "creation_datetime": "2012-12-31T23:59:59Z",
        "uuid": "987ba073-fcca-4242-85c6-c8ae990a0480",
        "annotation_set_uuid": "36c33463-16fe-4ba4-bf1c-490a0b0c1653",
        "annotation_set_name": "Trial Data",
        "image_set_name": "Greater Haig Fras 2012 autonomous underwater vehicle image survey - mosaicked tiles used for quantifying benthic community and characterising seabed type",
        "image_set_uuid": "822731b4-a6b7-476f-887e-debf00bfa6ba",
        "image_filename": "M58_10441297_12987745240267.jpg",
        "image_handle": "https://dap.ceda.ac.uk/.../M58_10441297_12987745240267.jpg",
        "image_uuid": "1345c48a-d360-4d48-8737-2f94a1c9517b",
        "label_name": "porifera_03",
        "label_aphia_id": 558,
        "annotation_platform": "ImagePro",
        "annotation_creation_datetime": "2012-12-31T23:59:59Z",
        "annotation_shape": "single-pixel",
        "annotation_coordinates": [
          [1359, 2909]
        ],
        "annotation_dimension_pixels": 366.9346,
        "annotator_name": "Noelie Benoist"
      },
      {
        "creation_datetime": "2012-12-31T23:59:59Z",
        "uuid": "9a8b4e34-d318-482d-88d6-cc101da7c138",
        "annotation_set_uuid": "36c33463-16fe-4ba4-bf1c-490a0b0c1653",
        "annotation_set_name": "Trial Data",
        "image_set_name": "Greater Haig Fras 2012 autonomous underwater vehicle image survey - mosaicked tiles used for quantifying benthic community and characterising seabed type",
        "image_set_uuid": "822731b4-a6b7-476f-887e-debf00bfa6ba",
        "image_filename": "M58_10441297_12987744811443.jpg",
        "image_handle": "https://dap.ceda.ac.uk/.../M58_10441297_12987744811443.jpg",
        "image_uuid": "5fc8ac68-3c00-4885-8e61-eb1db7f278d4",
        "label_name": "anthozoa_34",
        "label_aphia_id": 1292,
        "annotation_platform": "ImagePro",
        "annotation_creation_datetime": "2012-12-31T23:59:59Z",
        "annotation_shape": "single-pixel",
        "annotation_coordinates": [
          [2163, 2096]
        ],
        "annotation_dimension_pixels": 43.01163,
        "annotator_name": "Noelie Benoist"
      }
    ]
  }
}

def fetch_results_from_bodc_annotations_api() -> list[Result]:
    """Call the BODC annotations api and return a list of results."""

    # try:
    #     bodc_response = rq.get(BODC_ANNOTATIONS_API_ENDPOINT)
    #     bodc_response.raise_for_status()
    # except Exception as exc: # TODO: Catch specific exceptions and log properly.
    #     print(f"Something went wrong calling the BODC annotations API {exc}.")
    #     return []
    
    # bodc_response_data = bodc_response.json().get("results")
    bodc_results = make_request().get("results").get("annotations")
    return [Result.construct_instance_from_raw_response(result, source="BODC") for result in bodc_results]
   

def fetch_results_from_jncc_annotations_api() -> list[Result]:
    """Call the JNCC annotations api and return a list of results."""
    # try:
    #     jncc_response = rq.get(JNCC_ANNOTATIONS_API_ENDPOINT)
    #     jncc_response.raise_for_status()
    # except Exception as exc: # TODO: Catch specific exceptions and log properly.
    #     print(f"Something went wrong calling the JNCC annotations API {exc}.")
    #     return []
    
    # jncc_response_data = jncc_response.json().get("results")
    bodc_results = make_request().get("results").get("annotations")
    return [Result.construct_instance_from_raw_response(result, source="JNCC") for result in bodc_results]


def fetch_combined_results_from_annotation_apis() -> SearchResults:
    """Call both annotations apis and return the combined results.
    
    Returns:
        SearchResults: An instance with the results built from both the BODC and JNCC API's.
    """

    return SearchResults(
        results=fetch_results_from_bodc_annotations_api() + fetch_results_from_jncc_annotations_api()
        )

