"""RoleMesh - AI tool discovery, routing, and execution."""

from .builder import SetupWizard, ToolProfile, discover_tools
from .router import RoleMeshRouter
from .dashboard import RoleMeshDashboard, DashboardData, HealthCheck, Color
from .executor import RoleMeshExecutor, ExecutionResult

__all__ = [
    "SetupWizard", "ToolProfile", "discover_tools",
    "RoleMeshRouter",
    "RoleMeshDashboard", "DashboardData", "HealthCheck", "Color",
    "RoleMeshExecutor", "ExecutionResult",
]
