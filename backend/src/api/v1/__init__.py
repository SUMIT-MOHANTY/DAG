"""API v1 router aggregation."""
from fastapi import APIRouter

router = APIRouter()

# Import and include sub-routers as they are implemented
try:
    from .auth import router as auth_router
    router.include_router(auth_router, prefix="/auth", tags=["auth"])
except ImportError:
    pass

try:
    from .restrictions import router as restrictions_router
    router.include_router(restrictions_router, prefix="/restrictions", tags=["restrictions"])
except ImportError:
    pass

try:
    from .policies import router as policies_router
    router.include_router(policies_router, prefix="/policies", tags=["policies"])
except ImportError:
    pass

try:
    from .approvals import router as approvals_router
    router.include_router(approvals_router, prefix="/approvals", tags=["approvals"])
except ImportError:
    pass

try:
    from .audit import router as audit_router
    router.include_router(audit_router, prefix="/audit", tags=["audit"])
except ImportError:
    pass
