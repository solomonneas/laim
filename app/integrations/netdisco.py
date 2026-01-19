"""
LAIM - Lab Asset Inventory Manager
Netdisco API Client
"""

import logging
import os
from typing import Optional

import httpx

from app.integrations.base import BaseAPIClient
from app.schemas import DeviceData

logger = logging.getLogger(__name__)


class NetdiscoClient(BaseAPIClient):
    """
    Netdisco API client for device discovery.

    API Documentation: https://github.com/netdisco/netdisco/wiki/API

    Authentication: POST /login with username/password returns API key
    Endpoints used:
        - GET /api/v1/search/device - List all devices
        - GET /api/v1/object/device/{ip} - Device details
        - GET /api/v1/object/device/{ip}/nodes - MAC addresses
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        **kwargs,
    ):
        base_url = base_url or os.getenv("NETDISCO_API_URL", "")
        super().__init__(base_url, **kwargs)

        self.username = username or os.getenv("NETDISCO_USERNAME", "")
        self.password = password or os.getenv("NETDISCO_PASSWORD", "")
        self._api_key: Optional[str] = None

    async def authenticate(self) -> bool:
        """
        Authenticate with Netdisco API via POST /login.

        Returns:
            True if authentication successful
        """
        if not self.base_url or not self.username or not self.password:
            logger.warning("Netdisco credentials not configured")
            return False

        try:
            client = await self._get_client()
            response = await client.post(
                "/login",
                data={"username": self.username, "password": self.password},
            )

            if response.status_code == 200:
                # Netdisco returns API key in response
                data = response.json()
                self._api_key = data.get("api_key") or data.get("key")
                if self._api_key:
                    logger.info("Netdisco authentication successful")
                    return True

            logger.error(f"Netdisco authentication failed: {response.status_code}")
            return False

        except Exception as e:
            logger.error(f"Netdisco authentication error: {e}")
            return False

    async def test_connection(self) -> bool:
        """Test connection to Netdisco API."""
        if not self.base_url:
            return False
        try:
            return await self.authenticate()
        except Exception:
            return False

    def _get_auth_headers(self) -> dict:
        """Get authentication headers for API requests."""
        if self._api_key:
            return {"Authorization": f"Bearer {self._api_key}"}
        return {}

    async def _search_devices(self) -> list[dict]:
        """
        Search for all devices in Netdisco.

        Returns:
            List of device dictionaries from API
        """
        try:
            response = await self.get(
                "/api/v1/search/device",
                headers=self._get_auth_headers(),
                params={"q": ""},  # Empty query returns all devices
            )
            data = response.json()
            return data if isinstance(data, list) else data.get("devices", [])
        except httpx.HTTPStatusError as e:
            logger.error(f"Failed to search Netdisco devices: {e}")
            return []

    async def _get_device_details(self, ip: str) -> Optional[dict]:
        """
        Get detailed information for a specific device.

        Args:
            ip: Device IP address (primary key in Netdisco)

        Returns:
            Device details dictionary or None
        """
        try:
            response = await self.get(
                f"/api/v1/object/device/{ip}",
                headers=self._get_auth_headers(),
            )
            return response.json()
        except httpx.HTTPStatusError:
            return None

    async def _get_device_nodes(self, ip: str) -> list[dict]:
        """
        Get MAC addresses (nodes) associated with a device.

        Args:
            ip: Device IP address

        Returns:
            List of node dictionaries containing MAC addresses
        """
        try:
            response = await self.get(
                f"/api/v1/object/device/{ip}/nodes",
                headers=self._get_auth_headers(),
            )
            data = response.json()
            return data if isinstance(data, list) else []
        except httpx.HTTPStatusError:
            return []

    def _normalize_mac(self, mac: Optional[str]) -> Optional[str]:
        """Normalize MAC address to XX:XX:XX:XX:XX:XX format."""
        if not mac:
            return None
        mac = mac.upper().replace("-", "").replace(":", "").replace(".", "")
        if len(mac) == 12:
            return ":".join([mac[i : i + 2] for i in range(0, 12, 2)])
        return None

    def _transform_device(self, device: dict, nodes: list[dict]) -> DeviceData:
        """
        Transform Netdisco device data to unified DeviceData schema.

        Args:
            device: Raw device data from Netdisco
            nodes: List of node/MAC data from Netdisco

        Returns:
            DeviceData object
        """
        # Get first MAC address from nodes if available
        mac_address = None
        if nodes:
            for node in nodes:
                mac = node.get("mac")
                if mac:
                    mac_address = self._normalize_mac(mac)
                    break

        return DeviceData(
            hostname=device.get("dns") or device.get("name"),
            serial_number=device.get("serial"),
            mac_address=mac_address,
            ip_address=device.get("ip"),
            model=device.get("model"),
            vendor=device.get("vendor"),
            firmware_version=device.get("os_ver"),
            location=device.get("location"),
            source="netdisco",
            source_id=device.get("ip"),  # IP is primary key in Netdisco
        )

    async def get_devices(self) -> list[DeviceData]:
        """
        Fetch all devices from Netdisco and transform to unified schema.

        Returns:
            List of DeviceData objects
        """
        if not await self.authenticate():
            logger.error("Cannot fetch devices: authentication failed")
            return []

        devices = await self._search_devices()
        logger.info(f"Found {len(devices)} devices in Netdisco")

        result = []
        for device in devices:
            ip = device.get("ip")
            if not ip:
                continue

            # Fetch additional details and MAC addresses
            details = await self._get_device_details(ip)
            if details:
                device.update(details)

            nodes = await self._get_device_nodes(ip)

            device_data = self._transform_device(device, nodes)
            result.append(device_data)

        logger.info(f"Transformed {len(result)} Netdisco devices")
        return result
