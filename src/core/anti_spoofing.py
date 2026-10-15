"""Security module for mock location, emulator, and debugger hook detection."""

import logging
from typing import Optional
from pydantic import BaseModel, Field
from geopy.distance import geodesic

from src.core.exceptions import GeoSpoofingException

logger = logging.getLogger(__name__)


class DeviceIntegrityHeaders(BaseModel):
    """Client device telemetry headers for location spoofing and tamper defense."""

    x_mock_location: bool = Field(default=False, description="Flag indicating system mock location provider enabled")
    x_is_emulator: bool = Field(default=False, description="Flag indicating execution within an emulator/simulator")
    x_hook_detected: bool = Field(default=False, description="Flag indicating Frida/Xposed/Substrate hooking frameworks detected")
    x_device_signature: Optional[str] = Field(default=None, description="Cryptographic hardware-backed attestation signature")


def is_mock_location_detected(
    headers: Optional[DeviceIntegrityHeaders] = None,
    payload_flags: Optional[dict] = None,
) -> bool:
    """Evaluates whether device telemetry flags show evidence of location spoofing or tampering."""
    if headers:
        if headers.x_mock_location or headers.x_is_emulator or headers.x_hook_detected:
            return True

    if payload_flags:
        if (
            payload_flags.get("is_mock", False)
            or payload_flags.get("mock_location", False)
            or payload_flags.get("emulator", False)
            or payload_flags.get("hook_detected", False)
        ):
            return True

    return False


class LocationProofValidator:
    """Validates real-world location proofs against geofences and spoofing risks."""

    @staticmethod
    def validate_and_compute_distance(
        user_lat: float,
        user_lon: float,
        target_lat: float,
        target_lon: float,
        max_radius_meters: float = 100.0,
        headers: Optional[DeviceIntegrityHeaders] = None,
        payload_flags: Optional[dict] = None,
    ) -> tuple[bool, float]:
        """Calculates distance between coordinates and enforces anti-spoofing checks.

        Returns: (within_geofence: bool, distance_in_meters: float)
        Raises: GeoSpoofingException if mock location or hooking is detected.
        """
        if is_mock_location_detected(headers, payload_flags):
            logger.warning(
                "Geo spoofing detected! Headers: %s, Flags: %s, user_coords: (%s, %s)",
                headers,
                payload_flags,
                user_lat,
                user_lon,
            )
            raise GeoSpoofingException()

        user_point = (user_lat, user_lon)
        target_point = (target_lat, target_lon)
        distance_meters = geodesic(user_point, target_point).meters

        within_geofence = distance_meters <= max_radius_meters
        return within_geofence, distance_meters
