from typing import get_args

import pytest

from app.content.loader import ContentError
from app.content.rubrics import get_rubric
from app.llm.outputs import LLMDimension


def test_v1_has_seven_llm_dimensions_with_three_anchors() -> None:
    rubric = get_rubric("v1")

    assert rubric.version == "v1"
    assert {d.key for d in rubric.dimensions} == set(get_args(LLMDimension))
    for dimension in rubric.dimensions:
        assert {a.score for a in dimension.anchors} == {1, 3, 5}


def test_unknown_version_raises() -> None:
    with pytest.raises(ContentError):
        get_rubric("v99")
