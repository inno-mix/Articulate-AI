"""Shared Deepgram request options.

Every Deepgram request opts out of the Model Improvement Program (ADR-0016). Adapters pull their
shared options from here instead of repeating the flag, so it can't be forgotten on a new call.
"""

from typing import Any

MIP_OPT_OUT = True


def deepgram_request_options() -> dict[str, Any]:
    return {"mip_opt_out": MIP_OPT_OUT}
