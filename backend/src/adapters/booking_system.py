"""Mocked booking system adapter with realistic reservation/property data."""
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
import uuid

from .base import BaseBookingAdapter

# ── Static mock data ──────────────────────────────────────────────────────────

_PROPERTIES: list[dict[str, Any]] = [
    {
        "id": "prop-001",
        "name": "Azure Palms Resort & Spa",
        "type": "resort",
        "address": "1 Ocean Drive, Miami Beach, FL 33139",
        "star_rating": 5,
        "adults_only": True,
        "min_guest_age": 18,
        "total_rooms": 240,
        "amenities": ["spa", "pool", "casino", "beach_access"],
        "is_active": True,
    },
    {
        "id": "prop-002",
        "name": "Mountain Pines Family Lodge",
        "type": "lodge",
        "address": "45 Summit Trail, Aspen, CO 81611",
        "star_rating": 4,
        "adults_only": False,
        "min_guest_age": 0,
        "total_rooms": 80,
        "amenities": ["ski_access", "pool", "kids_club", "restaurant"],
        "is_active": True,
    },
    {
        "id": "prop-003",
        "name": "The Grand Metropolitan Hotel",
        "type": "hotel",
        "address": "500 Park Avenue, New York, NY 10022",
        "star_rating": 5,
        "adults_only": False,
        "min_guest_age": 0,
        "total_rooms": 450,
        "amenities": ["concierge", "spa", "rooftop_bar", "fitness_center"],
        "is_active": True,
    },
    {
        "id": "prop-004",
        "name": "Sunset Cove Boutique Inn",
        "type": "boutique",
        "address": "22 Harbour Lane, Key West, FL 33040",
        "star_rating": 3,
        "adults_only": True,
        "min_guest_age": 21,
        "total_rooms": 30,
        "amenities": ["pool", "bar", "beach_access"],
        "is_active": True,
    },
]

_ROOM_TYPES: dict[str, list[dict[str, Any]]] = {
    "prop-001": [
        {"id": "rt-001-std", "name": "Ocean View Standard", "capacity": 2, "rate_per_night": 450.0, "adults_only": True},
        {"id": "rt-001-ste", "name": "Penthouse Suite", "capacity": 4, "rate_per_night": 1200.0, "adults_only": True},
    ],
    "prop-002": [
        {"id": "rt-002-fam", "name": "Family Chalet", "capacity": 6, "rate_per_night": 380.0, "adults_only": False},
        {"id": "rt-002-std", "name": "Standard Double", "capacity": 2, "rate_per_night": 220.0, "adults_only": False},
    ],
    "prop-003": [
        {"id": "rt-003-dlx", "name": "Deluxe King", "capacity": 2, "rate_per_night": 650.0, "adults_only": False},
        {"id": "rt-003-ste", "name": "Executive Suite", "capacity": 3, "rate_per_night": 1500.0, "adults_only": False},
        {"id": "rt-003-std", "name": "Classic Twin", "capacity": 2, "rate_per_night": 420.0, "adults_only": False},
    ],
    "prop-004": [
        {"id": "rt-004-std", "name": "Garden Room", "capacity": 2, "rate_per_night": 280.0, "adults_only": True},
        {"id": "rt-004-ste", "name": "Harbour Suite", "capacity": 2, "rate_per_night": 520.0, "adults_only": True},
    ],
}

_now = datetime.now(timezone.utc)

_RESERVATIONS: list[dict[str, Any]] = [
    {
        "id": "res-001",
        "property_id": "prop-001",
        "room_type_id": "rt-001-std",
        "guest_id": "guest-001",
        "check_in": (_now + timedelta(days=14)).isoformat(),
        "check_out": (_now + timedelta(days=18)).isoformat(),
        "num_guests": 2,
        "total_amount": 1800.0,
        "status": "confirmed",
        "special_requests": "Late check-in requested",
        "created_at": (_now - timedelta(days=3)).isoformat(),
    },
    {
        "id": "res-002",
        "property_id": "prop-002",
        "room_type_id": "rt-002-fam",
        "guest_id": "guest-002",
        "check_in": (_now + timedelta(days=30)).isoformat(),
        "check_out": (_now + timedelta(days=37)).isoformat(),
        "num_guests": 4,
        "total_amount": 2660.0,
        "status": "confirmed",
        "special_requests": "Crib required for infant",
        "created_at": (_now - timedelta(days=10)).isoformat(),
    },
    {
        "id": "res-003",
        "property_id": "prop-003",
        "room_type_id": "rt-003-dlx",
        "guest_id": "guest-003",
        "check_in": (_now + timedelta(days=7)).isoformat(),
        "check_out": (_now + timedelta(days=10)).isoformat(),
        "num_guests": 2,
        "total_amount": 1950.0,
        "status": "pending",
        "special_requests": None,
        "created_at": (_now - timedelta(days=1)).isoformat(),
    },
    {
        "id": "res-004",
        "property_id": "prop-004",
        "room_type_id": "rt-004-ste",
        "guest_id": "guest-004",
        "check_in": (_now + timedelta(days=60)).isoformat(),
        "check_out": (_now + timedelta(days=65)).isoformat(),
        "num_guests": 2,
        "total_amount": 2600.0,
        "status": "flagged",
        "special_requests": "Anniversary celebration",
        "created_at": (_now - timedelta(days=5)).isoformat(),
    },
    {
        "id": "res-005",
        "property_id": "prop-001",
        "room_type_id": "rt-001-ste",
        "guest_id": "guest-005",
        "check_in": (_now - timedelta(days=2)).isoformat(),
        "check_out": (_now + timedelta(days=3)).isoformat(),
        "num_guests": 2,
        "total_amount": 6000.0,
        "status": "checked_in",
        "special_requests": "Champagne on arrival",
        "created_at": (_now - timedelta(days=20)).isoformat(),
    },
]


class MockBookingSystemAdapter(BaseBookingAdapter):
    """In-memory mock implementation of the booking system adapter."""

    async def get_reservation(self, reservation_id: str) -> Optional[dict[str, Any]]:
        return next((r for r in _RESERVATIONS if r["id"] == reservation_id), None)

    async def list_reservations(
        self,
        property_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        results = _RESERVATIONS
        if property_id:
            results = [r for r in results if r["property_id"] == property_id]
        if status:
            results = [r for r in results if r["status"] == status]
        return results[offset : offset + limit]

    async def get_property(self, property_id: str) -> Optional[dict[str, Any]]:
        return next((p for p in _PROPERTIES if p["id"] == property_id), None)

    async def list_properties(self, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
        return _PROPERTIES[offset : offset + limit]

    async def get_room_types(self, property_id: str) -> list[dict[str, Any]]:
        return _ROOM_TYPES.get(property_id, [])
