from typing import List, Dict
from app.models.user import RoleEnum

# Permission Constants
class Permission:
    # Admin
    USERS_MANAGE = "USERS_MANAGE"
    GLOBAL_CONFIG = "GLOBAL_CONFIG"
    AUDIT_VIEW = "AUDIT_VIEW"

    # Principal
    VACANCY_MANAGE = "VACANCY_MANAGE"
    AD_MANAGE = "AD_MANAGE"
    SELECTION_MANAGE = "SELECTION_MANAGE"
    APPOINTMENT_MANAGE = "APPOINTMENT_MANAGE"
    RATE_MANAGE = "RATE_MANAGE"
    ATTENDANCE_VERIFY = "ATTENDANCE_VERIFY"

    # Candidate
    PROFILE_MANAGE = "PROFILE_MANAGE"
    JOB_APPLY = "JOB_APPLY"
    APPOINTMENT_ACCEPT = "APPOINTMENT_ACCEPT"

    # Faculty
    ATTENDANCE_LOG = "ATTENDANCE_LOG"
    BILL_VIEW = "BILL_VIEW"

    # Higher Levels
    BILL_APPROVE_RO = "BILL_APPROVE_RO"
    BILL_APPROVE_DIR = "BILL_APPROVE_DIR"
    BILL_APPROVE_TRE = "BILL_APPROVE_TRE"

# Role to Permission Mapping
ROLE_PERMISSIONS: Dict[RoleEnum, List[str]] = {
    RoleEnum.ADMIN: [
        Permission.USERS_MANAGE,
        Permission.GLOBAL_CONFIG,
        Permission.AUDIT_VIEW,
    ],
    RoleEnum.PRINCIPAL: [
        Permission.VACANCY_MANAGE,
        Permission.AD_MANAGE,
        Permission.SELECTION_MANAGE,
        Permission.APPOINTMENT_MANAGE,
        Permission.RATE_MANAGE,
        Permission.ATTENDANCE_VERIFY,
    ],
    RoleEnum.CANDIDATE: [
        Permission.PROFILE_MANAGE,
        Permission.JOB_APPLY,
        Permission.APPOINTMENT_ACCEPT,
    ],
    RoleEnum.FACULTY: [
        Permission.ATTENDANCE_LOG,
        Permission.BILL_VIEW,
    ],
    RoleEnum.RO: [
        Permission.BILL_APPROVE_RO,
    ],
    RoleEnum.DIRECTORATE: [
        Permission.BILL_APPROVE_DIR,
    ],
    RoleEnum.TREASURY: [
        Permission.BILL_APPROVE_TRE,
    ],
}

def get_permissions_for_role(role: RoleEnum) -> List[str]:
    return ROLE_PERMISSIONS.get(role, [])
