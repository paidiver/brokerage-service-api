"""Tests for the search model."""

from brokerage_service_api.models.search_model import Summary


def test_addition_override_for_summary() -> None:
    """Test that two Summary instances can be added."""
    instance_a = Summary(n_annotations=2, n_images=2, n_annotation_sets=1, n_image_sets=1)
    instance_b = Summary(n_annotations=4, n_images=4, n_annotation_sets=2, n_image_sets=2)

    expected_instance_after_addition = Summary(n_annotations=6, n_images=6, n_annotation_sets=3, n_image_sets=3)

    assert instance_a + instance_b == expected_instance_after_addition
