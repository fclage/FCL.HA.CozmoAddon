"""HTTP client for the hacozmo companion."""

from __future__ import annotations

from typing import Any

import aiohttp

from .const import DEFAULT_URL


class CompanionError(Exception):
    """Companion returned an error or was unreachable."""


class CompanionAuthError(CompanionError):
    """Companion rejected the token."""


class CozmoCompanion:
    def __init__(
        self,
        session: aiohttp.ClientSession,
        url: str,
        token: str | None = None,
    ) -> None:
        self._session = session
        self._url = (url or DEFAULT_URL).rstrip("/")
        self._token = token or ""

    @property
    def url(self) -> str:
        return self._url

    def _headers(self, extra: dict[str, str] | None = None) -> dict[str, str]:
        headers = dict(extra or {})
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        return headers

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
        data: bytes | None = None,
        headers: dict[str, str] | None = None,
        timeout: float = 10,
    ) -> aiohttp.ClientResponse:
        try:
            resp = await self._session.request(
                method,
                f"{self._url}{path}",
                json=json_body,
                data=data,
                headers=self._headers(headers),
                timeout=aiohttp.ClientTimeout(total=timeout),
            )
        except aiohttp.ClientError as exc:
            raise CompanionError(f"Cannot reach companion at {self._url}") from exc
        if resp.status == 401:
            raise CompanionAuthError("Invalid companion token")
        if resp.status >= 400:
            text = await resp.text()
            raise CompanionError(f"{path} failed ({resp.status}): {text[:200]}")
        return resp

    async def health(self) -> dict[str, Any]:
        resp = await self._request("GET", "/v1/health", timeout=5)
        return await resp.json(content_type=None)

    async def status(self) -> dict[str, Any]:
        resp = await self._request("GET", "/v1/status")
        return await resp.json(content_type=None)

    async def anims(self) -> dict[str, Any]:
        resp = await self._request("GET", "/v1/anims")
        return await resp.json(content_type=None)

    async def camera_jpeg(self) -> bytes | None:
        try:
            resp = await self._request("GET", "/v1/camera.jpg", timeout=15)
        except CompanionError:
            return None
        if resp.content_type and "json" in resp.content_type:
            return None
        return await resp.read()

    async def command(self, cmd: str, **kwargs: Any) -> dict[str, Any]:
        body = {"cmd": cmd, **kwargs}
        resp = await self._request("POST", "/v1/command", json_body=body, timeout=15)
        return await resp.json(content_type=None)

    async def play_audio_bytes(self, payload: bytes, content_type: str = "audio/wav") -> None:
        await self._request(
            "POST",
            "/v1/audio",
            data=payload,
            headers={"Content-Type": content_type},
            timeout=60,
        )

    async def wifi_join(
        self,
        ssid: str | None = None,
        password: str | None = None,
        iface: str | None = None,
    ) -> None:
        body: dict[str, Any] = {}
        if ssid:
            body["ssid"] = ssid
        if password is not None:
            body["password"] = password
        if iface:
            body["iface"] = iface
        await self._request("POST", "/v1/wifi", json_body=body, timeout=50)
