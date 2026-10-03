"""Mocked customer data adapter with guest profiles and age verification."""
from datetime import date, datetime, timedelta, timezone
from typing import Any, Optional

from .base import BaseCustomerDataAdapter

# ── Static mock guest data ────────────────────────────────────────────────────

_now = datetime.now(timezone.utc)

_GUESTS: list[dict[str, Any]] = [
    {
        "id": "guest-001",
        "first_name": "Sarah",
        "last_name": "Chen",
        "email": "sarah.chen@example.com",
        "phone": "+1-305-555-0101",
        "date_of_birth": "1988-04-15",
        "age": 36,
        "nationality": "US",
        "passport_number": "US123456789",
        "loyalty_tier": "platinum",
        "total_stays": 47,
        "is_verified": True,
        "flags": [],
        "created_at": (_now - timedelta(days=730)).isoformat(),
    },
    {
        "id": "guest-002",
        "first_name": "Marcus",
        "last_name": "Okonkwo",
        "email": "m.okonkwo@example.com",
        "phone": "+1-212-555-0202",
        "date_of_birth": "1975-11-22",
        "age": 48,
        "nationality": "NG",
        "passport_number": "NG987654321",
        "loyalty_tier": "gold",
        "total_stays": 23,
        "is_verified": True,
        "flags": [],
        "created_at": (_now - timedelta(days=1095)).isoformat(),
    },
    {
        "id": "guest-003",
        "first_name": "Elena",
        "last_name": "Vasquez",
        "email": "elena.v@example.com",
        "phone": "+34-91-555-0303",
        "date_of_birth": "1995-07-08",
        "age": 29,
        "nationality": "ES",
        "passport_number": "ES456789012",
        "loyalty_tier": "silver",
        "total_stays": 8,
        "is_verified": True,
        "flags": ["payment_dispute_2023"],
        "created_at": (_now - timedelta(days=365)).isoformat(),
    },
    {
        "id": "guest-004",
        "first_name": "James",
        "last_name": "Whitfield",
        "email": "j.whitfield@example.com",
        "phone": "+1-702-555-0404",
        "date_of_birth": "2001-03-19",
        "age": 23,
        "nationality": "US",
        "passport_number": "US789012345",
        "loyalty_tier": "standard",
        "total_stays": 3,
        "is_verified": False,
        "flags": ["age_verification_pending"],
        "created_at": (_now - timedelta(days=90)).isoformat(),
    },
    {
        "id": "guest-005",
        "first_name": "Priya",
        "last_name": "Nair",
        "email": "priya.nair@example.com",
        "phone": "+91-98-555-0505",
        "date_of_birth": "1982-09-30",
        "age": 41,
        "nationality": "IN",
        "passport_number": "IN234567890",
        "loyalty_tier": "platinum",
        "total_stays": 62,
        "is_verified": True,
        "flags": [],
        "created_at": (_now - timedelta(days=1825)).isoformat(),
    },
    {
        "id": "guest-006",
        "first_name": "Thomas",
        "last_name": "Bergmann",
        "email": "t.bergmann@example.com",
        "phone": "+49-30-555-0606",
        "date_of_birth": "1990-12-05",
        "age": 33,
        "nationality": "DE",
        "passport_number": "DE345678901",
        "loyalty_tier": "gold",
        "total_stays": 15,
        "is_verified": True,
        "flags": [],
        "created_at": (_now - timedelta(days=548)).isoformat(),
    },
]


class MockCustomerDataAdapter(BaseCustomerDataAdapter):
    """In-memory mock implementation of the customer data adapter."""

    async def get_guest_profile(self, guest_id: str) -> Optional[dict[str, Any]]:
        return next((g for g in _GUESTS if g["id"] == guest_id), None)

    async def verify_age(self, guest_id: str, minimum_age: int) -> dict[str, Any]:
        guest = next((g for g in _GUESTS if g["id"] == guest_id), None)
        if guest is None:
            return {
                "guest_id": guest_id,
                "verified": False,
                "reason": "Guest not found",
                "minimum_age": minimum_age,
                "actual_age": None,
            }
        actual_age = guest["age"]
        meets_requirement = actual_age >= minimum_age
        return {
            "guest_id": guest_id,
            "verified": meets_requirement and guest["is_verified"],
            "meets_age_requirement": meets_requirement,
            "minimum_age": minimum_age,
            "actual_age": actual_age,
            "identity_verified": guest["is_verified"],
            "reason": None if meets_requirement else f"Guest age {actual_age} is below minimum {minimum_age}",
        }

    async def search_guests(self, query: str, limit: int = 20) -> list[dict[str, Any]]:
        query_lower = query.lower()
        results = [
            g for g in _GUESTS
            if query_lower in g["first_name"].lower()
            or query_lower in g["last_name"].lower()
            or query_lower in g["email"].lower()
        ]
        return results[:limit]
