"""
LAIM - Lab Asset Inventory Manager
Device Sync Service - Merge, dedupe, and upsert from multiple sources
"""

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import InventoryItem, SyncLog, SyncStatus, ItemType
from app.schemas import DeviceData
from app.integrations.netdisco import NetdiscoClient
from app.integrations.librenms import LibreNMSClient

logger = logging.getLogger(__name__)


# -----------------------------------------------------------------------------
# Device Type Auto-Detection
# -----------------------------------------------------------------------------
TYPE_PATTERNS: dict[ItemType, list[str]] = {
    ItemType.FIREWALL: [
        "firewall", "router", "isr", "asr", "cisco router", "juniper router",
        "mikrotik router", "edgerouter", "routeros", "vyos",
        "pfsense", "opnsense", "fortigate", "srx", "udm", "usg",
        "dream machine", "security gateway", "sonicwall",
        "asa", "fortinet", "sophos", "watchguard", "netgate",
        "pa-", "palo alto", "pa-3", "pa-4", "pa-5", "pa-7",
    ],
    ItemType.SWITCH: [
        "switch", "catalyst", "nexus", "arista", "juniper switch",
        "dell switch", "powerswitch", "procurve", "comware",
        "edgeswitch", "unifi switch", "usw-", "usw ", "meraki ms",
        "brocade", "icx", "fas", "s4048", "s5048", "z9100",
        "us-", "us-8", "us-16", "us-24", "us-48", "usl-",
        "cisco sg", "sg300", "sg500", "ws-c", "ws-c4506", "ws-c3",
        "ws-c2", "c9300", "c9200", "c3850", "c3750", "c2960",
    ],
    ItemType.WAP: [
        "wap", "wireless", "wifi", "access point", "aruba ap",
        "unifi ap", "uap-", "uap ", "iap-", "aironet", "meraki mr",
        "u6-", "u6 ", "u7-", "u7 ", "u-xg", "unifi 6", "unifi 7",
        "ubiquiti u6", "ubiquiti u7", "nanostation", "litebeam",
        "powerbeam", "nanobeam", "ubiquiti ap", "ac-pro", "ac-lite",
        "ac-lr", "ac-hd", "ac-shd", "flexhd", "nanohd",
    ],
    ItemType.SERVER: [
        "server", "poweredge", "proliant", "blade", "esxi", "vmware",
        "vcenter", "dell r", "hp dl", "supermicro", "rackmount",
        "hypervisor", "proxmox", "xenserver", "hyper-v",
    ],
    ItemType.DESKTOP: [
        "optiplex", "prodesk", "thinkcentre", "desktop", "workstation",
        "precision", "elitedesk", "compaq", "imac", "mac mini",
    ],
    ItemType.LAPTOP: [
        "latitude", "elitebook", "thinkpad", "laptop", "notebook",
        "macbook", "probook", "zbook", "inspiron", "xps",
        "surface", "chromebook", "pavilion",
    ],
    ItemType.SMART_TV: [
        "tv", "display", "samsung tv", "lg tv", "sony tv",
        "smart display", "signage", "monitor", "roku", "fire tv",
        "chromecast", "apple tv", "shield",
    ],
}


def detect_item_type(
    model: Optional[str] = None,
    vendor: Optional[str] = None,
    hostname: Optional[str] = None,
) -> ItemType:
    """
    Auto-detect item type from device information.

    Args:
        model: Device model string
        vendor: Device vendor string
        hostname: Device hostname

    Returns:
        Detected ItemType, defaults to SERVER
    """
    # Combine all fields for pattern matching
    search_text = " ".join(
        filter(None, [model, vendor, hostname])
    ).lower()

    if not search_text:
        return ItemType.SERVER

    for item_type, patterns in TYPE_PATTERNS.items():
        for pattern in patterns:
            if pattern in search_text:
                return item_type

    # Default to SERVER for network devices
    return ItemType.SERVER


def generate_asset_tag() -> str:
    """Generate a unique asset tag for auto-discovered devices."""
    short_uuid = uuid.uuid4().hex[:8].upper()
    return f"AUTO-{short_uuid}"


# -----------------------------------------------------------------------------
# Sync Result Dataclass
# -----------------------------------------------------------------------------
@dataclass
class SyncResult:
    """Result of a sync operation."""
    devices_found: int = 0
    created: int = 0
    updated: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)


# -----------------------------------------------------------------------------
# Device Sync Service
# -----------------------------------------------------------------------------
class DeviceSyncService:
    """
    Service for syncing devices from Netdisco and LibreNMS.

    Features:
        - Fetch from both sources
        - Merge with LibreNMS priority for conflicts
        - Deduplicate by serial_number or mac_address
        - Upsert to database
        - Log sync history
    """

    def __init__(
        self,
        db: AsyncSession,
        netdisco_client: Optional[NetdiscoClient] = None,
        librenms_client: Optional[LibreNMSClient] = None,
    ):
        self.db = db
        self.netdisco = netdisco_client or NetdiscoClient()
        self.librenms = librenms_client or LibreNMSClient()

    async def _create_sync_log(self, source: str) -> SyncLog:
        """Create a new sync log entry."""
        sync_log = SyncLog(
            source=source,
            status=SyncStatus.RUNNING,
        )
        self.db.add(sync_log)
        await self.db.commit()
        await self.db.refresh(sync_log)
        return sync_log

    async def _complete_sync_log(
        self,
        sync_log: SyncLog,
        result: SyncResult,
        status: SyncStatus = SyncStatus.COMPLETED,
    ):
        """Update sync log with completion data."""
        sync_log.completed_at = datetime.now(timezone.utc)
        sync_log.status = status
        sync_log.devices_found = result.devices_found
        sync_log.created = result.created
        sync_log.updated = result.updated
        sync_log.skipped = result.skipped
        sync_log.errors = result.errors if result.errors else None
        await self.db.commit()

    def _get_device_key(self, device: DeviceData) -> Optional[str]:
        """
        Get unique identifier key for a device.

        Priority:
        1. serial_number (if non-empty)
        2. mac_address (if non-empty)
        3. hostname + ip_address combination (fallback)
        """
        if device.serial_number and device.serial_number.strip():
            return f"serial:{device.serial_number.strip()}"
        if device.mac_address and device.mac_address.strip():
            return f"mac:{device.mac_address.strip()}"
        if device.hostname and device.ip_address:
            return f"host_ip:{device.hostname}:{device.ip_address}"
        return None

    def _merge_devices(
        self,
        netdisco_devices: list[DeviceData],
        librenms_devices: list[DeviceData],
    ) -> dict[str, DeviceData]:
        """
        Merge devices from both sources with LibreNMS priority.

        Args:
            netdisco_devices: Devices from Netdisco
            librenms_devices: Devices from LibreNMS

        Returns:
            Dictionary of unique devices keyed by identifier
        """
        merged: dict[str, DeviceData] = {}

        # First add Netdisco devices
        for device in netdisco_devices:
            key = self._get_device_key(device)
            if key:
                merged[key] = device

        # Then add/override with LibreNMS devices (higher priority)
        for device in librenms_devices:
            key = self._get_device_key(device)
            if key:
                if key in merged:
                    # Merge fields - LibreNMS takes priority for non-empty values
                    existing = merged[key]
                    merged[key] = DeviceData(
                        hostname=device.hostname or existing.hostname,
                        serial_number=device.serial_number or existing.serial_number,
                        mac_address=device.mac_address or existing.mac_address,
                        ip_address=device.ip_address or existing.ip_address,
                        model=device.model or existing.model,
                        vendor=device.vendor or existing.vendor,
                        firmware_version=device.firmware_version or existing.firmware_version,
                        location=device.location or existing.location,
                        source="merged",
                        source_id=device.source_id or existing.source_id,
                    )
                else:
                    merged[key] = device

        return merged

    async def _find_existing_item(self, device: DeviceData) -> Optional[InventoryItem]:
        """
        Find existing inventory item matching the device.

        Matches by:
        1. serial_number (exact match)
        2. mac_address (exact match)
        3. hostname + ip_address (fallback)
        """
        conditions = []

        if device.serial_number and device.serial_number.strip():
            conditions.append(InventoryItem.serial_number == device.serial_number.strip())

        if device.mac_address and device.mac_address.strip():
            conditions.append(InventoryItem.mac_address == device.mac_address.strip())

        if not conditions:
            return None

        result = await self.db.execute(
            select(InventoryItem).where(or_(*conditions))
        )
        return result.scalar_one_or_none()

    async def _upsert_device(self, device: DeviceData, result: SyncResult):
        """
        Insert or update a device in the inventory.

        Args:
            device: Device data to upsert
            result: SyncResult to update with counts
        """
        try:
            # Generate serial from available identifiers if not present
            serial = None
            if device.serial_number and device.serial_number.strip():
                serial = device.serial_number.strip()
            elif device.mac_address and device.mac_address.strip():
                serial = f"MAC-{device.mac_address.strip().replace(':', '')}"
            elif device.hostname and device.hostname.strip():
                serial = f"HOST-{device.hostname.strip()}"
            elif device.ip_address and device.ip_address.strip():
                serial = f"IP-{device.ip_address.strip()}"

            if not serial:
                result.skipped += 1
                logger.debug(f"Skipped device without identifiers: {device.hostname or device.ip_address}")
                return

            # Check for existing item by generated serial first
            existing_query = await self.db.execute(
                select(InventoryItem).where(InventoryItem.serial_number == serial)
            )
            existing = existing_query.scalar_one_or_none()

            # If not found by serial, try other identifiers
            if not existing:
                existing = await self._find_existing_item(device)

            if existing:
                # Skip existing items - don't overwrite manual edits
                result.skipped += 1
                logger.debug(f"Skipped existing device: {device.hostname or device.ip_address}")
            else:
                # Create new item
                item = InventoryItem(
                    hostname=device.hostname or device.ip_address or "Unknown",
                    serial_number=serial,
                    mac_address=device.mac_address,
                    asset_tag=generate_asset_tag(),
                    item_type=detect_item_type(device.model, device.vendor, device.hostname),
                    room_location="Synced",  # Default room for auto-discovered devices
                    ip_address=device.ip_address,
                    model=device.model,
                    vendor=device.vendor,
                    firmware_version=device.firmware_version,
                    source=device.source,
                    source_id=device.source_id,
                    last_synced_at=datetime.now(timezone.utc),
                )
                self.db.add(item)
                result.created += 1
                logger.debug(f"Created device: {device.hostname or device.ip_address}")

            # Flush after each device to catch duplicates early
            await self.db.flush()

        except Exception as e:
            await self.db.rollback()
            error_msg = f"Error processing {device.hostname or device.ip_address}: {str(e)}"
            result.errors.append(error_msg)
            logger.error(error_msg)

    async def sync_all(self) -> tuple[SyncLog, SyncResult]:
        """
        Sync devices from both Netdisco and LibreNMS.

        Returns:
            Tuple of (SyncLog, SyncResult)
        """
        sync_log = await self._create_sync_log("all")
        result = SyncResult()

        try:
            # Fetch from both sources
            logger.info("Fetching devices from Netdisco...")
            netdisco_devices = await self.netdisco.get_devices()

            logger.info("Fetching devices from LibreNMS...")
            librenms_devices = await self.librenms.get_devices()

            # Merge with deduplication
            merged = self._merge_devices(netdisco_devices, librenms_devices)
            result.devices_found = len(merged)
            logger.info(f"Merged {result.devices_found} unique devices")

            # Upsert each device
            for device in merged.values():
                await self._upsert_device(device, result)

            await self.db.commit()
            await self._complete_sync_log(sync_log, result, SyncStatus.COMPLETED)

        except Exception as e:
            error_msg = f"Sync failed: {str(e)}"
            result.errors.append(error_msg)
            logger.error(error_msg)
            await self._complete_sync_log(sync_log, result, SyncStatus.FAILED)

        finally:
            await self.netdisco.close()
            await self.librenms.close()

        return sync_log, result

    async def sync_netdisco_only(self) -> tuple[SyncLog, SyncResult]:
        """
        Sync devices from Netdisco only.

        Returns:
            Tuple of (SyncLog, SyncResult)
        """
        sync_log = await self._create_sync_log("netdisco")
        result = SyncResult()

        try:
            logger.info("Fetching devices from Netdisco...")
            devices = await self.netdisco.get_devices()
            result.devices_found = len(devices)

            for device in devices:
                await self._upsert_device(device, result)

            await self.db.commit()
            await self._complete_sync_log(sync_log, result, SyncStatus.COMPLETED)

        except Exception as e:
            error_msg = f"Netdisco sync failed: {str(e)}"
            result.errors.append(error_msg)
            logger.error(error_msg)
            await self._complete_sync_log(sync_log, result, SyncStatus.FAILED)

        finally:
            await self.netdisco.close()

        return sync_log, result

    async def sync_librenms_only(self) -> tuple[SyncLog, SyncResult]:
        """
        Sync devices from LibreNMS only.

        Returns:
            Tuple of (SyncLog, SyncResult)
        """
        sync_log = await self._create_sync_log("librenms")
        result = SyncResult()

        try:
            logger.info("Fetching devices from LibreNMS...")
            devices = await self.librenms.get_devices()
            result.devices_found = len(devices)

            for device in devices:
                await self._upsert_device(device, result)

            await self.db.commit()
            await self._complete_sync_log(sync_log, result, SyncStatus.COMPLETED)

        except Exception as e:
            error_msg = f"LibreNMS sync failed: {str(e)}"
            result.errors.append(error_msg)
            logger.error(error_msg)
            await self._complete_sync_log(sync_log, result, SyncStatus.FAILED)

        finally:
            await self.librenms.close()

        return sync_log, result
