from app.db.session import Base
from app.models.user import User, RoleEnum
from app.models.institution import Institution, Course  # Course replaces old Branch model
from app.models.intake import IntakeDefinition
from app.models.norm import Norm
from app.models.faculty_req import FacultyRequirement, RequirementAnomaly
from app.models.audit import AuditLog
from app.models.existing_faculty import ExistingFaculty
from app.models.faculty_qualification import FacultyQualification
from app.models.vacancy_assessment import VacancyAssessment
from app.models.vacancy_anomaly import VacancyAnomaly
from app.models.advertisement_template import AdvertisementTemplate
from app.models.advertisement import Advertisement, AdvertisementStatus, AdvertisementAction
from app.models.advertisement_audit import AdvertisementAudit
from app.models.published_advertisement import PublishedAdvertisement
from app.models.candidate import Candidate
from app.models.candidate_qualification import CandidateQualification
from app.models.candidate_experience import CandidateExperience
from app.models.application import Application, ApplicationStatus
from app.models.application_document import ApplicationDocument
from app.models.document_validation_log import DocumentValidationLog
from app.models.appointment_template import AppointmentTemplate
from app.models.appointment_letter import AppointmentLetter, AppointmentLetterStatus
from app.models.appointment_acceptance import AppointmentAcceptance
from app.models.faculty_credentials import FacultyCredentials
from app.models.appointment_audit import AppointmentAudit, AppointmentAuditAction
from app.models.timetable_slot import TimetableSlot, WeekDayEnum, TimetableLectureType
from app.models.lecture_log import LectureLog, LectureLogStatus, LectureLogType
from app.models.daily_attendance_summary import DailyAttendanceSummary
from app.models.attendance_anomaly import AttendanceAnomaly, AnomalySeverity
from app.models.academic_calendar import AcademicCalendar, CalendarDayType
from app.models.lecture_log_audit import LectureLogAudit, LectureLogAuditAction
from app.models.rate_master import RateMaster, CHBDesignation, RateLectureType
from app.models.chb_bill import CHBBill, BillStatus, BillApproverRole
from app.models.bill_line_item import BillLineItem, BillLineLectureType
from app.models.bill_approval import BillApproval, BillApprovalAction
from app.models.bill_audit import BillAudit, BillAuditAction
from app.models.payment_transaction import PaymentTransaction, PaymentMode, PaymentStatus

# Step 5 Models
from .scoring_weight_config import ScoringWeightConfig
from .selection_round import SelectionRound, SelectionRoundType, SelectionRoundStatus
from .shortlisted_candidate import ShortlistedCandidate
from .interview_marks import InterviewMarks
from .candidate_score import CandidateScore
from .selection_result import SelectionResult, SelectionResultStatus, FinalResultStatus

__all__ = [
    "Base",
    "User",
    "RoleEnum",
    "Institution",
    "Course",
    "Norm",
    "IntakeDefinition",
    "FacultyRequirement",
    "RequirementAnomaly",
    "AuditLog",
    "ExistingFaculty",
    "FacultyQualification",
    "VacancyAssessment",
    "VacancyAnomaly",
    "Advertisement",
    "AdvertisementStatus",
    "AdvertisementAction",
    "AdvertisementAudit",
    "PublishedAdvertisement",
    "Candidate",
    "Application",
    "ApplicationStatus",
    "ApplicationDocument",
    "DocumentValidationLog",
    "AppointmentTemplate",
    "AppointmentLetter",
    "AppointmentLetterStatus",
    "AppointmentAcceptance",
    "FacultyCredentials",
    "AppointmentAudit",
    "AppointmentAuditAction",
    "TimetableSlot",
    "WeekDayEnum",
    "TimetableLectureType",
    "LectureLog",
    "LectureLogStatus",
    "LectureLogType",
    "DailyAttendanceSummary",
    "AttendanceAnomaly",
    "AnomalySeverity",
    "AcademicCalendar",
    "CalendarDayType",
    "LectureLogAudit",
    "LectureLogAuditAction",
    "RateMaster",
    "CHBDesignation",
    "RateLectureType",
    "CHBBill",
    "BillStatus",
    "BillApproverRole",
    "BillLineItem",
    "BillLineLectureType",
    "BillApproval",
    "BillApprovalAction",
    "BillAudit",
    "BillAuditAction",
    "PaymentTransaction",
    "PaymentMode",
    "PaymentStatus",
    "CandidateQualification",
    "CandidateExperience",
    "ScoringWeightConfig",
    "SelectionRound",
    "SelectionRoundType",
    "SelectionRoundStatus",
    "ShortlistedCandidate",
    "InterviewMarks",
    "CandidateScore",
    "SelectionResult",
    "SelectionResultStatus",
    "FinalResultStatus",
]
from app.models.selection_ai_snapshot import SelectionAISnapshot
