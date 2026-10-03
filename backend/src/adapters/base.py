"""Abstract base interfaces for external system adapters."""
from abc import ABC, abstractmethod
from typing import Any, Optional


class BaseBookingAdapter(ABC):
    """Abstract interface for booking system integration."""

    @abstractmethod
    async def get_reservation(self, reservation_id: str) -> Optional[dict[str, Any]]:
        """Retrieve a single reservation by ID."""

    @abstractmethod
    async def list_reservations(
        self,
        property_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """List reservations with optional filters."""

    @abstractmethod
    async def get_property(self, property_id: str) -> Optional[dict[str, Any]]:
        """Retrieve a property by ID."""

    @abstractmethod
    async def list_properties(self, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
        """List all properties."""

    @abstractmethod
    async def get_room_types(self, property_id: str) -> list[dict[str, Any]]:
        """List room types for a given property."""


class BaseCustomerDataAdapter(ABC):
    """Abstract interface for customer/guest data integration."""

    @abstractmethod
    async def get_guest_profile(self, guest_id: str) -> Optional[dict[str, Any]]:
        """Retrieve a guest profile by ID."""

    @abstractmethod
    async def verify_age(self, guest_id: str, minimum_age: int) -> dict[str, Any]:
        """Verify whether a guest meets a minimum age requirement."""

    @abstractmethod
    async def search_guests(
        self,
        query: str,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Search guest profiles by name or email."""


class BaseRiskEngineAdapter(ABC):
    """Abstract interface for external risk scoring engine."""

    @abstractmethod
    async def score_booking(
        self,
        reservation_id: str,
        guest_id: str,
        property_id: str,
        context: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """Compute a risk score for a booking."""

    @abstractmethod
    async def score_restriction_match(
        self,
        restriction_id: str,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """Score how well a context matches a restriction rule."""

    @abstractmethod
    async def get_risk_factors(self, entity_type: str, entity_id: str) -> list[dict[str, Any]]:
        """Retrieve contributing risk factors for an entity."""
