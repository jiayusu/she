from __future__ import annotations

import json
import os
from typing import Any, AsyncIterator

from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosed


class GatewayWebSocketTransport:
    """WebSocket transport for the device-to-gateway v1 session contract."""

    def __init__(
        self,
        url: str,
        *,
        device_token: str | None = None,
        open_timeout: float = 10.0,
        close_timeout: float = 2.0,
    ) -> None:
        self.url = url
        self.device_token = device_token
        self.open_timeout = open_timeout
        self.close_timeout = close_timeout
        self._socket: Any | None = None

    async def connect(self) -> None:
        if self._socket is not None:
            return
        headers = None
        if self.device_token:
            headers = {"Authorization": f"Bearer {self.device_token}"}
        options: dict[str, Any] = {
            "open_timeout": self.open_timeout,
            "close_timeout": self.close_timeout,
            "max_size": 64 * 1024,
        }
        if headers:
            options["additional_headers"] = headers
        try:
            self._socket = await connect(self.url, **options)
        except TypeError as exc:
            if not headers or "additional_headers" not in str(exc):
                raise
            # websockets 13 called this argument extra_headers.
            options.pop("additional_headers")
            options["extra_headers"] = headers
            self._socket = await connect(self.url, **options)

    async def send_event(self, event: dict[str, Any]) -> None:
        socket = self._socket
        if socket is None:
            raise ConnectionError("gateway_not_connected")
        try:
            await socket.send(json.dumps(event, separators=(",", ":")))
        except ConnectionClosed as exc:
            raise ConnectionError("gateway_connection_closed") from exc

    async def commands(self) -> AsyncIterator[dict[str, Any]]:
        socket = self._socket
        if socket is None:
            raise ConnectionError("gateway_not_connected")
        try:
            async for raw in socket:
                try:
                    value = json.loads(raw)
                except (TypeError, json.JSONDecodeError) as exc:
                    raise ConnectionError("gateway_invalid_message") from exc
                if not isinstance(value, dict):
                    raise ConnectionError("gateway_invalid_message")
                # Accepted/duplicate responses are transport acknowledgements,
                # not device commands. Errors require a reconnect so the runtime
                # cannot continue on a session the gateway rejected.
                if "command_id" not in value:
                    if "error" in value:
                        raise ConnectionError("gateway_rejected_message")
                    continue
                yield value
        except ConnectionClosed as exc:
            raise ConnectionError("gateway_connection_closed") from exc

    async def close(self) -> None:
        socket, self._socket = self._socket, None
        if socket is not None:
            await socket.close()


def gateway_from_environment() -> GatewayWebSocketTransport:
    url = os.environ.get("SHE_GATEWAY_WS")
    if not url:
        raise RuntimeError("SHE_GATEWAY_WS is required")
    return GatewayWebSocketTransport(url, device_token=os.environ.get("SHE_DEVICE_TOKEN"))
