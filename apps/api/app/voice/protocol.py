"""Voice WebSocket message shapes (voice-and-pronunciation.md §2.2-2.3, binding)."""

import json
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError

from app.domain.enums import VoiceInputMode
from app.schemas.session import MessageOut


class ProtocolError(Exception):
    """`raw` failed to parse as a known client message."""


class _ClientMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Start(_ClientMessage):
    type: Literal["start"] = "start"
    input_mode: VoiceInputMode


class PttDown(_ClientMessage):
    type: Literal["ptt_down"] = "ptt_down"


class PttUp(_ClientMessage):
    type: Literal["ptt_up"] = "ptt_up"


class CancelTurn(_ClientMessage):
    type: Literal["cancel_turn"] = "cancel_turn"


class Resume(_ClientMessage):
    type: Literal["resume"] = "resume"


class EndSession(_ClientMessage):
    type: Literal["end_session"] = "end_session"


class Ping(_ClientMessage):
    type: Literal["ping"] = "ping"


ClientMessage = Annotated[
    Start | PttDown | PttUp | CancelTurn | Resume | EndSession | Ping,
    Field(discriminator="type"),
]
_client_message_adapter: TypeAdapter[ClientMessage] = TypeAdapter(ClientMessage)


def parse_client_message(raw: str) -> ClientMessage:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ProtocolError("Not valid JSON.") from exc
    try:
        return _client_message_adapter.validate_python(data)
    except ValidationError as exc:
        raise ProtocolError(str(exc)) from exc


class _ServerEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Ready(_ServerEvent):
    type: Literal["ready"] = "ready"
    state: Literal["idle", "listening"]
    stt_model: str


class State(_ServerEvent):
    type: Literal["state"] = "state"
    value: Literal["idle", "listening", "thinking", "speaking"]


class Transcript(_ServerEvent):
    type: Literal["transcript"] = "transcript"
    text: str
    is_final: bool = False


class UserTurn(_ServerEvent):
    type: Literal["user_turn"] = "user_turn"
    message: MessageOut


class AssistantDelta(_ServerEvent):
    type: Literal["assistant_delta"] = "assistant_delta"
    text: str


class AssistantTurn(_ServerEvent):
    type: Literal["assistant_turn"] = "assistant_turn"
    message: MessageOut


class AudioEnd(_ServerEvent):
    type: Literal["audio_end"] = "audio_end"


class Limit(_ServerEvent):
    type: Literal["limit"] = "limit"
    reason: Literal["turn_too_long", "session_too_long", "turn_limit_reached", "daily_voice_limit"]


class Error(_ServerEvent):
    type: Literal["error"] = "error"
    code: str
    message: str
    fatal: bool


class SessionEnded(_ServerEvent):
    type: Literal["session_ended"] = "session_ended"
    status: Literal["ended", "abandoned"]
    report_status: Literal["pending"] | None


class Paused(_ServerEvent):
    type: Literal["paused"] = "paused"
    reason: Literal["no_speech"] = "no_speech"


class Pong(_ServerEvent):
    type: Literal["pong"] = "pong"


ServerEvent = (
    Ready
    | State
    | Transcript
    | UserTurn
    | AssistantDelta
    | AssistantTurn
    | AudioEnd
    | Limit
    | Error
    | Paused
    | SessionEnded
    | Pong
)
