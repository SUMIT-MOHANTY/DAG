#!/usr/bin/env python3
"""Seed script: populates the database with 15-25 realistic synthetic records."""
import asyncio
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Ensure backend package is importable
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.config.database import AsyncSessionLocal, engine
from backend.src.models.base import Base
from backend.src.models.user import User
from backend.src.models.policy import Policy
from backend.src.models.restriction import Restriction
from backend.src.models.evidence import Evidence
from backend.src.models.approval_request import ApprovalRequest
from backend.src.models.audit_log import AuditLog
from backend.src.models.conversation import Conversation, Message
from backend.src.core.security import hash_password

import backend.src.models  # noqa: F401 — register all models


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def past(days: int = 0, hours: int = 0) -> datetime:
    return utcnow() - timedelta(days=days, hours=hours)


def future(days: int = 0) -> datetime:
    return utcnow() + timedelta(days=days)


async def seed(session: AsyncSession) -> None:
    print("Seeding database...")

    # ── Users ─────────────────────────────────────────────────────────────────
    admin = User(
        id=str(uuid.uuid4()),
        email="admin@restrictioniq.com",
        hashed_password=hash_password("Admin@1234!"),
        role="admin",
        last_login=past(hours=2),
    )
    operator1 = User(
        id=str(uuid.uuid4()),
        email="dr.sarah.chen@restrictioniq.com",
        hashed_password=hash_password("Operator@1234!"),
        role="operator",
        last_login=past(hours=5),
    )
    operator2 = User(
        id=str(uuid.uuid4()),
        email="james.morrison@restrictioniq.com",
        hashed_password=hash_password("Operator@1234!"),
        role="operator",
        last_login=past(days=1),
    )
    session.add_all([admin, operator1, operator2])
    await session.flush()
    print(f"  Created {3} users")

    # ── Policies ──────────────────────────────────────────────────────────────
    policy_adult = Policy(
        id=str(uuid.uuid4()),
        name="Adult-Only Resort Policy",
        version="2.1",
        document_url="https://docs.restrictioniq.com/policies/adult-only-resort-v2.1.pdf",
        description="Governs age restrictions for adult-only resort properties. Minimum guest age is 18 years.",
        effective_from=past(days=365),
        effective_to=None,
    )
    policy_highvalue = Policy(
        id=str(uuid.uuid4()),
        name="High-Value Booking Compliance Policy",
        version="1.3",
        document_url="https://docs.restrictioniq.com/policies/high-value-booking-v1.3.pdf",
        description="Risk management rules for bookings exceeding $10,000 total value.",
        effective_from=past(days=180),
        effective_to=None,
    )
    policy_cancellation = Policy(
        id=str(uuid.uuid4()),
        name="Cancellation & Refund Policy",
        version="3.0",
        document_url="https://docs.restrictioniq.com/policies/cancellation-v3.0.pdf",
        description="Standard cancellation windows, refund eligibility, and penalty schedules.",
        effective_from=past(days=90),
        effective_to=None,
    )
    policy_sanctions = Policy(
        id=str(uuid.uuid4()),
        name="Sanctions & Prohibited Regions Policy",
        version="1.0",
        document_url="https://docs.restrictioniq.com/policies/sanctions-v1.0.pdf",
        description="Compliance with OFAC and international sanctions lists. Prohibits bookings from sanctioned regions.",
        effective_from=past(days=730),
        effective_to=None,
    )
    session.add_all([policy_adult, policy_highvalue, policy_cancellation, policy_sanctions])
    await session.flush()
    print(f"  Created {4} policies")

    # ── Restrictions ──────────────────────────────────────────────────────────
    r1 = Restriction(
        id=str(uuid.uuid4()),
        name="Minimum Age 18 — Adult Resort",
        description="All guests must be 18 years or older to book adult-only resort properties.",
        rule_type="age_minimum",
        parameters={"min_age": 18, "applies_to": "all_guests", "property_tags": ["adult-only"]},
        risk_level=3,
        source_policy_id=policy_adult.id,
        effective_from=past(days=365),
        effective_to=None,
    )
    r2 = Restriction(
        id=str(uuid.uuid4()),
        name="High-Risk Booking Flag",
        description="Bookings with risk score >= 4 require manual approval before confirmation.",
        rule_type="risk_threshold",
        parameters={"risk_score_threshold": 4, "action": "require_approval", "queue": "high_risk"},
        risk_level=5,
        source_policy_id=policy_highvalue.id,
        effective_from=past(days=180),
        effective_to=None,
    )
    r3 = Restriction(
        id=str(uuid.uuid4()),
        name="No-Refund Within 48 Hours",
        description="Bookings cancelled within 48 hours of check-in are non-refundable.",
        rule_type="cancellation_window",
        parameters={"hours_before_checkin": 48, "refund_percentage": 0},
        risk_level=2,
        source_policy_id=policy_cancellation.id,
        effective_from=past(days=90),
        effective_to=None,
    )
    r4 = Restriction(
        id=str(uuid.uuid4()),
        name="Sanctioned Country Block",
        description="Bookings originating from OFAC-sanctioned countries are automatically blocked.",
        rule_type="geo_block",
        parameters={"blocked_countries": ["KP", "IR", "SY", "CU"], "action": "hard_block"},
        risk_level=5,
        source_policy_id=policy_sanctions.id,
        effective_from=past(days=730),
        effective_to=None,
    )
    r5 = Restriction(
        id=str(uuid.uuid4()),
        name="Large Group Booking Approval",
        description="Group bookings of 10 or more rooms require manager approval.",
        rule_type="group_size_limit",
        parameters={"max_rooms_auto_approve": 9, "action": "require_approval"},
        risk_level=3,
        source_policy_id=policy_highvalue.id,
        effective_from=past(days=120),
        effective_to=None,
    )
    r6 = Restriction(
        id=str(uuid.uuid4()),
        name="Minimum Stay 3 Nights — Peak Season",
        description="During peak season (June–August), minimum stay is 3 nights.",
        rule_type="minimum_stay",
        parameters={"min_nights": 3, "season": "peak", "months": [6, 7, 8]},
        risk_level=1,
        source_policy_id=policy_cancellation.id,
        effective_from=past(days=60),
        effective_to=future(days=120),
    )
    r7 = Restriction(
        id=str(uuid.uuid4()),
        name="Credit Card Pre-Authorization Required",
        description="All bookings over $2,000 require credit card pre-authorization at time of booking.",
        rule_type="payment_preauth",
        parameters={"threshold_usd": 2000, "preauth_percentage": 25},
        risk_level=2,
        source_policy_id=policy_highvalue.id,
        effective_from=past(days=200),
        effective_to=None,
    )
    r8 = Restriction(
        id=str(uuid.uuid4()),
        name="Unaccompanied Minor Policy",
        description="Guests under 16 must be accompanied by an adult guardian at all times.",
        rule_type="age_guardian",
        parameters={"minor_age_threshold": 16, "requires_guardian": True},
        risk_level=4,
        source_policy_id=policy_adult.id,
        effective_from=past(days=400),
        effective_to=None,
    )
    all_restrictions = [r1, r2, r3, r4, r5, r6, r7, r8]
    session.add_all(all_restrictions)
    await session.flush()
    print(f"  Created {len(all_restrictions)} restrictions")

    # ── Evidence ──────────────────────────────────────────────────────────────
    ev1 = Evidence(
        id=str(uuid.uuid4()),
        restriction_id=r1.id,
        source_table="guest_profiles",
        source_record_id="guest-001",
        source_field="date_of_birth",
        evidence_value="2006-03-15",
        confidence_score=0.99,
        collected_at=past(days=5),
    )
    ev2 = Evidence(
        id=str(uuid.uuid4()),
        restriction_id=r2.id,
        source_table="bookings",
        source_record_id="booking-4821",
        source_field="total_value_usd",
        evidence_value="15750.00",
        confidence_score=0.95,
        collected_at=past(days=2),
    )
    ev3 = Evidence(
        id=str(uuid.uuid4()),
        restriction_id=r4.id,
        source_table="customer_profiles",
        source_record_id="cust-0093",
        source_field="billing_country",
        evidence_value="IR",
        confidence_score=0.87,
        collected_at=past(days=1),
    )
    ev4 = Evidence(
        id=str(uuid.uuid4()),
        restriction_id=r8.id,
        source_table="guest_profiles",
        source_record_id="guest-042",
        source_field="age_verified",
        evidence_value="14",
        confidence_score=0.72,
        collected_at=past(hours=12),
    )
    ev5 = Evidence(
        id=str(uuid.uuid4()),
        restriction_id=r5.id,
        source_table="bookings",
        source_record_id="booking-5103",
        source_field="room_count",
        evidence_value="12",
        confidence_score=1.0,
        collected_at=past(hours=6),
    )
    session.add_all([ev1, ev2, ev3, ev4, ev5])
    await session.flush()
    print(f"  Created {5} evidence records")

    # ── Approval Requests ─────────────────────────────────────────────────────
    ap1 = ApprovalRequest(
        id=str(uuid.uuid4()),
        restriction_query_id=r2.id,
        risk_score=4.8,
        confidence_score=0.95,
        queue_type="high_risk",
        priority="urgent",
        status="pending",
        assigned_to=None,
        decision_rationale=None,
        decided_at=None,
        context_data='{"booking_id": "booking-4821", "guest": "Marcus Webb", "amount": 15750}',
    )
    ap2 = ApprovalRequest(
        id=str(uuid.uuid4()),
        restriction_query_id=r8.id,
        risk_score=3.5,
        confidence_score=0.72,
        queue_type="low_confidence",
        priority="high",
        status="in_review",
        assigned_to=operator1.id,
        decision_rationale=None,
        decided_at=None,
        context_data='{"booking_id": "booking-4799", "guest": "Emily Hartwell", "minor_age": 14}',
    )
    ap3 = ApprovalRequest(
        id=str(uuid.uuid4()),
        restriction_query_id=r5.id,
        risk_score=3.0,
        confidence_score=1.0,
        queue_type="high_risk",
        priority="medium",
        status="approved",
        assigned_to=operator2.id,
        decision_rationale="Group booking verified as corporate retreat. All compliance checks passed.",
        decided_at=past(hours=3),
        context_data='{"booking_id": "booking-5103", "company": "Apex Consulting", "rooms": 12}',
    )
    ap4 = ApprovalRequest(
        id=str(uuid.uuid4()),
        restriction_query_id=r4.id,
        risk_score=5.0,
        confidence_score=0.87,
        queue_type="high_risk",
        priority="urgent",
        status="rejected",
        assigned_to=admin.id,
        decision_rationale="Booking origin confirmed as sanctioned country. Hard block applied per policy.",
        decided_at=past(hours=8),
        context_data='{"booking_id": "booking-4901", "country": "IR", "customer_id": "cust-0093"}',
    )
    ap5 = ApprovalRequest(
        id=str(uuid.uuid4()),
        restriction_query_id=r1.id,
        risk_score=2.5,
        confidence_score=0.65,
        queue_type="low_confidence",
        priority="medium",
        status="pending",
        assigned_to=None,
        decision_rationale=None,
        decided_at=None,
        context_data='{"booking_id": "booking-5210", "guest": "Alex Rivera", "dob_unverified": true}',
    )
    ap6 = ApprovalRequest(
        id=str(uuid.uuid4()),
        restriction_query_id=r7.id,
        risk_score=2.0,
        confidence_score=0.91,
        queue_type="high_risk",
        priority="low",
        status="escalated",
        assigned_to=operator1.id,
        decision_rationale=None,
        decided_at=None,
        context_data='{"booking_id": "booking-5301", "amount": 8500, "preauth_failed": true}',
    )
    session.add_all([ap1, ap2, ap3, ap4, ap5, ap6])
    await session.flush()
    print(f"  Created {6} approval requests")

    # ── Audit Logs ────────────────────────────────────────────────────────────
    audit_events = [
        AuditLog(
            id=str(uuid.uuid4()),
            event_type="user.login",
            user_id=admin.id,
            resource_type="user",
            resource_id=admin.id,
            changes={"action": "login", "method": "password"},
            ip_address="192.168.1.10",
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
        ),
        AuditLog(
            id=str(uuid.uuid4()),
            event_type="restriction.created",
            user_id=admin.id,
            resource_type="restriction",
            resource_id=r1.id,
            changes={"name": "Minimum Age 18 — Adult Resort", "risk_level": 3},
            ip_address="192.168.1.10",
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
        ),
        AuditLog(
            id=str(uuid.uuid4()),
            event_type="policy.updated",
            user_id=admin.id,
            resource_type="policy",
            resource_id=policy_adult.id,
            changes={"version": {"old": "2.0", "new": "2.1"}},
            ip_address="192.168.1.10",
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
        ),
        AuditLog(
            id=str(uuid.uuid4()),
            event_type="approval.assigned",
            user_id=admin.id,
            resource_type="approval_request",
            resource_id=ap2.id,
            changes={"assigned_to": operator1.id, "status": "in_review"},
            ip_address="192.168.1.10",
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
        ),
        AuditLog(
            id=str(uuid.uuid4()),
            event_type="approval.decided",
            user_id=operator2.id,
            resource_type="approval_request",
            resource_id=ap3.id,
            changes={"status": {"old": "in_review", "new": "approved"}, "rationale": "Corporate retreat verified"},
            ip_address="10.0.0.55",
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        ),
        AuditLog(
            id=str(uuid.uuid4()),
            event_type="approval.decided",
            user_id=admin.id,
            resource_type="approval_request",
            resource_id=ap4.id,
            changes={"status": {"old": "in_review", "new": "rejected"}, "reason": "Sanctioned country"},
            ip_address="192.168.1.10",
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
        ),
        AuditLog(
            id=str(uuid.uuid4()),
            event_type="user.login",
            user_id=operator1.id,
            resource_type="user",
            resource_id=operator1.id,
            changes={"action": "login"},
            ip_address="10.0.0.42",
            user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 17_0)",
        ),
        AuditLog(
            id=str(uuid.uuid4()),
            event_type="restriction.updated",
            user_id=operator1.id,
            resource_type="restriction",
            resource_id=r6.id,
            changes={"effective_to": {"old": None, "new": str(future(days=120))}},
            ip_address="10.0.0.42",
            user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 17_0)",
        ),
        AuditLog(
            id=str(uuid.uuid4()),
            event_type="evidence.collected",
            user_id=None,
            resource_type="evidence",
            resource_id=ev3.id,
            changes={"confidence_score": 0.87, "source": "customer_profiles"},
            ip_address="127.0.0.1",
            user_agent="RestrictionIQ-Agent/1.0",
        ),
        AuditLog(
            id=str(uuid.uuid4()),
            event_type="approval.escalated",
            user_id=operator1.id,
            resource_type="approval_request",
            resource_id=ap6.id,
            changes={"status": {"old": "in_review", "new": "escalated"}, "reason": "Pre-auth system unavailable"},
            ip_address="10.0.0.42",
            user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 17_0)",
        ),
        AuditLog(
            id=str(uuid.uuid4()),
            event_type="policy.created",
            user_id=admin.id,
            resource_type="policy",
            resource_id=policy_sanctions.id,
            changes={"name": "Sanctions & Prohibited Regions Policy", "version": "1.0"},
            ip_address="192.168.1.10",
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
        ),
        AuditLog(
            id=str(uuid.uuid4()),
            event_type="restriction.created",
            user_id=admin.id,
            resource_type="restriction",
            resource_id=r4.id,
            changes={"name": "Sanctioned Country Block", "risk_level": 5},
            ip_address="192.168.1.10",
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
        ),
        AuditLog(
            id=str(uuid.uuid4()),
            event_type="user.password_changed",
            user_id=operator2.id,
            resource_type="user",
            resource_id=operator2.id,
            changes={"action": "password_changed"},
            ip_address="172.16.0.8",
            user_agent="Mozilla/5.0 (X11; Linux x86_64)",
        ),
        AuditLog(
            id=str(uuid.uuid4()),
            event_type="approval.created",
            user_id=None,
            resource_type="approval_request",
            resource_id=ap1.id,
            changes={"queue_type": "high_risk", "priority": "urgent", "risk_score": 4.8},
            ip_address="127.0.0.1",
            user_agent="RestrictionIQ-Agent/1.0",
        ),
        AuditLog(
            id=str(uuid.uuid4()),
            event_type="system.health_check",
            user_id=None,
            resource_type="system",
            resource_id="health",
            changes={"status": "healthy", "db": "connected"},
            ip_address="10.0.0.1",
            user_agent="HealthProbe/1.0",
        ),
    ]
    session.add_all(audit_events)
    await session.flush()
    print(f"  Created {len(audit_events)} audit log entries")

    # ── Conversations & Messages ───────────────────────────────────────────────
    conv1 = Conversation(
        id=str(uuid.uuid4()),
        user_id=operator1.id,
        session_id=f"sess-{uuid.uuid4().hex[:12]}",
        status="completed",
        ended_at=past(hours=4),
    )
    conv2 = Conversation(
        id=str(uuid.uuid4()),
        user_id=operator2.id,
        session_id=f"sess-{uuid.uuid4().hex[:12]}",
        status="active",
        ended_at=None,
    )
    conv3 = Conversation(
        id=str(uuid.uuid4()),
        user_id=admin.id,
        session_id=f"sess-{uuid.uuid4().hex[:12]}",
        status="completed",
        ended_at=past(days=1),
    )
    session.add_all([conv1, conv2, conv3])
    await session.flush()

    messages = [
        # Conversation 1
        Message(
            id=str(uuid.uuid4()),
            conversation_id=conv1.id,
            role="user",
            content="What are the age restrictions for the Maldives resort property?",
            agent_plan=None,
        ),
        Message(
            id=str(uuid.uuid4()),
            conversation_id=conv1.id,
            role="assistant",
            content="The Maldives resort is classified as an adult-only property. Per the Adult-Only Resort Policy (v2.1), all guests must be 18 years or older. This restriction has a risk level of 3 and has been active since January 2024.",
            agent_plan={"steps": ["query_restrictions", "filter_by_property", "format_response"], "tools_used": ["restriction_lookup"]},
        ),
        Message(
            id=str(uuid.uuid4()),
            conversation_id=conv1.id,
            role="user",
            content="Is there an exception process for guests who are 17?",
        ),
        Message(
            id=str(uuid.uuid4()),
            conversation_id=conv1.id,
            role="assistant",
            content="There is no automatic exception for guests under 18 at adult-only properties. Any exception would require an approval request routed to the high-risk queue with urgent priority. I recommend escalating to Dr. Sarah Chen for review.",
            agent_plan={"steps": ["check_exceptions", "evaluate_risk", "recommend_action"], "tools_used": ["policy_lookup", "approval_workflow"]},
        ),
        # Conversation 2
        Message(
            id=str(uuid.uuid4()),
            conversation_id=conv2.id,
            role="user",
            content="Show me all pending approval requests with urgent priority.",
            agent_plan=None,
        ),
        Message(
            id=str(uuid.uuid4()),
            conversation_id=conv2.id,
            role="assistant",
            content="I found 2 urgent pending approval requests:\n1. Booking #4821 — High-Risk Booking Flag (risk score: 4.8, amount: $15,750)\n2. Booking #4901 — Sanctioned Country Block (risk score: 5.0, country: IR)\n\nWould you like me to open either of these for review?",
            agent_plan={"steps": ["query_approvals", "filter_urgent", "format_list"], "tools_used": ["approval_queue_lookup"]},
        ),
        # Conversation 3
        Message(
            id=str(uuid.uuid4()),
            conversation_id=conv3.id,
            role="user",
            content="Generate a compliance summary for the Sanctions policy.",
            agent_plan=None,
        ),
        Message(
            id=str(uuid.uuid4()),
            conversation_id=conv3.id,
            role="assistant",
            content="Sanctions & Prohibited Regions Policy (v1.0) Summary:\n- Status: Active since 2022\n- Restrictions enforced: 1 (Sanctioned Country Block, risk level 5)\n- Blocked countries: KP, IR, SY, CU\n- Recent enforcement: 1 booking rejected in last 24 hours\n- Evidence collected: 1 record (confidence: 87%)\n\nCompliance posture: STRONG",
            agent_plan={"steps": ["load_policy", "aggregate_restrictions", "fetch_recent_events", "generate_summary"], "tools_used": ["policy_lookup", "restriction_lookup", "audit_log_query"]},
        ),
    ]
    session.add_all(messages)
    await session.flush()
    print(f"  Created {3} conversations with {len(messages)} messages")

    await session.commit()
    print("\nSeed complete! Summary:")
    print("  Users: 3 (1 admin, 2 operators)")
    print("  Policies: 4")
    print("  Restrictions: 8")
    print("  Evidence: 5")
    print("  Approval Requests: 6")
    print("  Audit Logs: 15")
    print("  Conversations: 3 | Messages: 8")


async def main() -> None:
    # Ensure tables exist
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as session:
        await seed(session)

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
