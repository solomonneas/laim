"""
LAIM - Lab Asset Inventory Manager
LibreNMS API Client
"""

import logging
import os
from typing import Optional

import httpx

from app.integrations.base import BaseAPIClient
from app.schemas import DeviceData

logger = logging.getLogger(__name__)


class LibreNMSClient(BaseAPIClient):
    """
    LibreNMS API client for device discovery.

    API Documentation: https://docs.librenms.org/API/

    Authentication: X-Auth-Token header
    Endpoints used:
        - GET /api/v0/devices - List all devices
        - GET /api/v0/devices/{hostname} - Device details
        - GET /api/v0/ports/{device_id} - Port/MAC info
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_token: Optional[str] = None,
        **kwargs,
    ):
        base_url = base_url or os.getenv("LIBRENMS_API_URL", "")
        super().__init__(base_url, **kwargs)

        self.api_token = api_token or os.getenv("LIBRENMS_API_TOKEN", "")

    def _get_auth_headers(self) -> dict:
        """Get authentication headers for API requests."""
        return {"X-Auth-Token": self.api_token}

    async def authenticate(self) -> bool:
        """
        Validate LibreNMS API token by making a test request.

        Returns:
            True if token is valid
        """
        if not self.base_url or not self.api_token:
            logger.warning("LibreNMS credentials not configured")
            return False

        try:
            # Use a lightweight endpoint to validate token
            response = await self.get(
                "/api/v0/system",
                headers=self._get_auth_headers(),
            )

            if response.status_code == 200:
                logger.info("LibreNMS authentication successful")
                return True

            logger.error(f"LibreNMS authentication failed: {response.status_code}")
            return False

        except Exception as e:
            logger.error(f"LibreNMS authentication error: {e}")
            return False

    async def test_connection(self) -> bool:
        """Test connection to LibreNMS API."""
        if not self.base_url:
            return False
        try:
            return await self.authenticate()
        except Exception:
            return False

    async def _list_devices(self) -> list[dict]:
        """
        List all devices from LibreNMS.

        Returns:
            List of device dictionaries from API
        """
        try:
            response = await self.get(
                "/api/v0/devices",
                headers=self._get_auth_headers(),
            )
            data = response.json()
            return data.get("devices", [])
        except httpx.HTTPStatusError as e:
            logger.error(f"Failed to list LibreNMS devices: {e}")
            return []

    async def _get_device_details(self, hostname: str) -> Optional[dict]:
        """
        Get detailed information for a specific device.

        Args:
            hostname: Device hostname

        Returns:
            Device details dictionary or None
        """
        try:
            response = await self.get(
                f"/api/v0/devices/{hostname}",
                headers=self._get_auth_headers(),
            )
            data = response.json()
            devices = data.get("devices", [])
            return devices[0] if devices else None
        except httpx.HTTPStatusError:
            return None

    async def _get_device_ports(self, device_id: int) -> list[dict]:
        """
        Get ports/interfaces for a device (includes MAC addresses).

        Args:
            device_id: LibreNMS device ID

        Returns:
            List of port dictionaries
        """
        try:
            response = await self.get(
                f"/api/v0/devices/{device_id}/ports",
                headers=self._get_auth_headers(),
            )
            data = response.json()
            return data.get("ports", [])
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

    def _parse_vendor_from_hardware(self, hardware: Optional[str]) -> Optional[str]:
        """
        Attempt to parse vendor from hardware string.

        Args:
            hardware: Hardware model string

        Returns:
            Vendor name if parseable
        """
        if not hardware:
            return None

        hardware_lower = hardware.lower()

        # Common vendor patterns
        vendors = {
            "cisco": ["cisco", "catalyst", "nexus", "asa", "meraki"],
            "juniper": ["juniper", "junos", "srx", "ex-", "qfx"],
            "aruba": ["aruba", "arubaos"],
            "hp": ["hp ", "hewlett", "procurve", "aruba"],
            "dell": ["dell", "force10", "powerconnect"],
            "ubiquiti": ["ubiquiti", "unifi", "edgeswitch", "edgerouter"],
            "fortinet": ["fortinet", "fortigate", "fortios"],
            "palo alto": ["palo alto", "pan-os"],
            "arista": ["arista", "eos"],
            "mikrotik": ["mikrotik", "routeros"],
            "netgear": ["netgear"],
            "tp-link": ["tp-link", "tplink"],
            "vmware": ["vmware", "esxi"],
            "linux": ["linux", "ubuntu", "centos", "debian", "rhel"],
            "windows": ["windows", "microsoft"],
        }

        for vendor, patterns in vendors.items():
            for pattern in patterns:
                if pattern in hardware_lower:
                    return vendor.title()

        return None

    def _transform_device(self, device: dict, ports: list[dict]) -> DeviceData:
        """
        Transform LibreNMS device data to unified DeviceData schema.

        Args:
            device: Raw device data from LibreNMS
            ports: List of port data from LibreNMS

        Returns:
            DeviceData object
        """
        # Get first MAC address from ports if available
        mac_address = None
        if ports:
            for port in ports:
                mac = port.get("ifPhysAddress")
                if mac:
                    mac_address = self._normalize_mac(mac)
                    if mac_address:
                        break

        # Parse vendor from hardware if not directly available
        hardware = device.get("hardware")
        vendor = device.get("vendor") or self._parse_vendor_from_hardware(hardware)

        return DeviceData(
            hostname=device.get("hostname") or device.get("sysName"),
            serial_number=device.get("serial"),
            mac_address=mac_address,
            ip_address=device.get("ip"),
            model=hardware,
            vendor=vendor,
            firmware_version=device.get("version"),
            location=device.get("location"),
            source="librenms",
            source_id=str(device.get("device_id")),
        )

    async def get_devices(self) -> list[DeviceData]:
        """
        Fetch all devices from LibreNMS and transform to unified schema.

        Returns:
            List of DeviceData objects
        """
        if not await self.authenticate():
            logger.error("Cannot fetch devices: authentication failed")
            return []

        devices = await self._list_devices()
        logger.info(f"Found {len(devices)} devices in LibreNMS")

        result = []
        for device in devices:
            device_id = device.get("device_id")
            if not device_id:
                continue

            # Fetch port information for MAC addresses
            ports = await self._get_device_ports(device_id)

            device_data = self._transform_device(device, ports)
            result.append(device_data)

        logger.info(f"Transformed {len(result)} LibreNMS devices")
        return result
