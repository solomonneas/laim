"""
LAIM - Lab Asset Inventory Manager
Base API Client with retry logic, rate limiting, and connection pooling
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Any, Optional

import httpx

from app.schemas import DeviceData

logger = logging.getLogger(__name__)


class BaseAPIClient(ABC):
    """
    Base async HTTP client with:
    - Connection pooling
    - Configurable retry logic (exponential backoff)
    - Rate limiting
    - Request/response logging
    - Timeout handling
    """

    def __init__(
        self,
        base_url: str,
        timeout: float = 30.0,
        max_retries: int = 3,
        rate_limit: float = 10.0,  # requests per second
        verify_ssl: bool = True,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self.rate_limit = rate_limit
        self.verify_ssl = verify_ssl
        self._client: Optional[httpx.AsyncClient] = None
        self._last_request_time: float = 0
        self._min_request_interval = 1.0 / rate_limit if rate_limit > 0 else 0

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the async HTTP client with connection pooling."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=httpx.Timeout(self.timeout),
                verify=self.verify_ssl,
                limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
            )
        return self._client

    async def close(self):
        """Close the HTTP client and release resources."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def _rate_limit_wait(self):
        """Wait if needed to respect rate limiting."""
        if self._min_request_interval > 0:
            now = asyncio.get_event_loop().time()
            elapsed = now - self._last_request_time
            if elapsed < self._min_request_interval:
                await asyncio.sleep(self._min_request_interval - elapsed)
            self._last_request_time = asyncio.get_event_loop().time()

    async def _request(
        self,
        method: str,
        endpoint: str,
        **kwargs,
    ) -> httpx.Response:
        """
        Make an HTTP request with retry logic and rate limiting.

        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint path
            **kwargs: Additional arguments passed to httpx request

        Returns:
            httpx.Response object

        Raises:
            httpx.HTTPError: If all retries fail
        """
        client = await self._get_client()
        last_exception: Optional[Exception] = None

        for attempt in range(self.max_retries):
            try:
                await self._rate_limit_wait()

                logger.debug(f"Request {method} {endpoint} (attempt {attempt + 1})")
                response = await client.request(method, endpoint, **kwargs)

                # Log response status
                logger.debug(f"Response: {response.status_code}")

                # Raise for HTTP errors (4xx, 5xx)
                response.raise_for_status()

                return response

            except httpx.HTTPStatusError as e:
                # Don't retry client errors (4xx) except rate limiting (429)
                if e.response.status_code == 429:
                    logger.warning(f"Rate limited, waiting before retry...")
                    wait_time = 2 ** attempt  # Exponential backoff
                    await asyncio.sleep(wait_time)
                    last_exception = e
                    continue
                elif 400 <= e.response.status_code < 500:
                    logger.error(f"Client error: {e.response.status_code} - {e.response.text}")
                    raise
                else:
                    # Retry server errors (5xx)
                    logger.warning(f"Server error {e.response.status_code}, retrying...")
                    wait_time = 2 ** attempt
                    await asyncio.sleep(wait_time)
                    last_exception = e

            except (httpx.ConnectError, httpx.TimeoutException) as e:
                logger.warning(f"Connection error on attempt {attempt + 1}: {e}")
                wait_time = 2 ** attempt
                await asyncio.sleep(wait_time)
                last_exception = e

            except Exception as e:
                logger.error(f"Unexpected error: {e}")
                last_exception = e
                break

        # All retries exhausted
        raise last_exception or Exception("Request failed after all retries")

    async def get(self, endpoint: str, **kwargs) -> httpx.Response:
        """Make a GET request."""
        return await self._request("GET", endpoint, **kwargs)

    async def post(self, endpoint: str, **kwargs) -> httpx.Response:
        """Make a POST request."""
        return await self._request("POST", endpoint, **kwargs)

    @abstractmethod
    async def authenticate(self) -> bool:
        """
        Authenticate with the API.

        Returns:
            True if authentication successful, False otherwise
        """
        pass

    @abstractmethod
    async def get_devices(self) -> list[DeviceData]:
        """
        Fetch all devices from the API.

        Returns:
            List of DeviceData objects
        """
        pass

    @abstractmethod
    async def test_connection(self) -> bool:
        """
        Test if the API is reachable and credentials are valid.

        Returns:
            True if connection successful, False otherwise
        """
        pass
