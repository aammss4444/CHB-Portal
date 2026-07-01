from __future__ import annotations

from datetime import date, datetime, time
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class TimetableSlotEntryRequest(BaseModel):
    slot_date: date  # Specific date for this slot
    slot_number: int = Field(..., ge=1, le=8)
    start_time: time
    end_time: time
    subject_name: str
    lecture_type: str
    class_name: Optional[str] = None


class TimetableSlotCreateRequest(BaseModel):
    faculty_credential_id: UUID
    academic_year: str
    slots: list[TimetableSlotEntryRequest]


class TimetableSlotUpdateRequest(BaseModel):
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    subject_name: Optional[str] = None
    lecture_type: Optional[str] = None
    class_name: Optional[str] = None
    is_active: Optional[bool] = None


class TimetableSlotResponse(BaseModel):
    id: UUID
    institution_id: int
    course_id: int
    faculty_credential_id: UUID
    academic_year: str
    slot_date: date  # Specific date for the slot (REQUIRED)
    day_of_week: Optional[str] = None  # Auto-calculated from slot_date
    slot_number: int
    start_time: time
    end_time: time
    subject_name: str
    lecture_type: str
    class_name: Optional[str] = None
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class CalendarEntryRequest(BaseModel):
    calendar_date: date
    day_type: str
    description: Optional[str] = None


class CalendarBulkUpsertRequest(BaseModel):
    institution_id: int
    academic_year: str
    entries: list[CalendarEntryRequest]


class CalendarEntryResponse(BaseModel):
    id: UUID
    institution_id: int
    academic_year: str
    calendar_date: date
    day_type: str
    description: Optional[str] = None
    is_holiday: bool
    is_exam: bool


class LectureLogCreateRequest(BaseModel):
    lecture_date: date
    slot_number: int = Field(..., ge=1, le=8)
    subject_name: str
    lecture_type: str
    class_name: Optional[str] = None
    topic_covered: str
    attendance_count: Optional[int] = None
    ai_attendance_count: Optional[int] = None
    manual_attendance_count: Optional[int] = None
    latitude: float
    longitude: float
    is_extra: bool = False
    is_substitute: bool = False
    substitute_for_faculty_id: Optional[UUID] = None


class LectureLogUpdateRequest(BaseModel):
    topic_covered: Optional[str] = None
    attendance_count: Optional[int] = None
    ai_attendance_count: Optional[int] = None
    manual_attendance_count: Optional[int] = None
    subject_name: Optional[str] = None
    lecture_type: Optional[str] = None
    class_name: Optional[str] = None


class LectureLogSubmitRequest(BaseModel):
    pass


class LectureLogVerifyRequest(BaseModel):
    action: str
    remarks: Optional[str] = None


class DailyAttendanceSummaryResponse(BaseModel):
    id: UUID
    faculty_credential_id: UUID
    institution_id: int
    course_id: int
    academic_year: str
    attendance_date: date
    scheduled_lectures: int
    conducted_lectures: int
    extra_lectures: int
    substitute_lectures: int
    total_billable_lectures: int
    is_present: bool
    is_holiday: bool
    is_locked: bool
    lock_reason: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class AnomalyFlagResponse(BaseModel):
    id: UUID
    anomaly_type: str
    severity: str
    description: str
    is_acknowledged: bool
    created_at: datetime


class LectureLogResponse(BaseModel):
    id: UUID
    faculty_credential_id: UUID
    timetable_slot_id: Optional[UUID] = None
    institution_id: int
    course_id: int
    academic_year: str
    lecture_date: date
    slot_number: int
    start_time: time
    end_time: time
    subject_name: str
    lecture_type: str
    class_name: Optional[str] = None
    topic_covered: str
    attendance_count: Optional[int] = None
    ai_attendance_count: Optional[int] = None
    manual_attendance_count: Optional[int] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    is_extra: bool
    is_substitute: bool
    substitute_for_faculty_id: Optional[UUID] = None
    log_status: str
    rejection_reason: Optional[str] = None
    submitted_at: Optional[datetime] = None
    verified_by: Optional[int] = None
    verified_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    timetable_slot: Optional[TimetableSlotResponse] = None
    anomaly_flags: list[AnomalyFlagResponse] = []
    daily_summary: Optional[DailyAttendanceSummaryResponse] = None


# STEP 8 GATE: feeds bill generation.
class MonthlyAttendanceSummaryResponse(BaseModel):
    total_scheduled: int
    total_conducted: int
    total_extra: int
    total_substitute: int
    total_billable: int
    present_days: int
    absent_days: int
    anomaly_count: int


class AnomalyLogReference(BaseModel):
    id: UUID
    lecture_date: date
    slot_number: int
    subject_name: str
    log_status: str


class AnomalyResponse(BaseModel):
    id: UUID
    faculty_credential_id: UUID
    lecture_log_id: Optional[UUID] = None
    summary_id: Optional[UUID] = None
    institution_id: int
    anomaly_type: str
    severity: str
    description: str
    is_acknowledged: bool
    acknowledged_by: Optional[int] = None
    acknowledged_at: Optional[datetime] = None
    acknowledgement_remarks: Optional[str] = None
    created_at: datetime
    lecture_log: Optional[AnomalyLogReference] = None


class AnomalyAcknowledgeRequest(BaseModel):
    remarks: str


class BulkSubmitRequest(BaseModel):
    log_ids: list[UUID]


class BulkSubmitFailure(BaseModel):
    log_id: UUID
    reason: str


class BulkSubmitResponse(BaseModel):
    success_count: int
    failed: list[BulkSubmitFailure]


class LectureLogInput(BaseModel):
    faculty_credential_id: UUID
    lecture_date: date
    calendar_date: date
    slot_number: int
    subject_name: str
    topic_covered: str
    attendance_count: Optional[int] = None
    ai_attendance_count: Optional[int] = None
    manual_attendance_count: Optional[int] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    class_name: Optional[str] = None
    created_at: datetime
    log_status: str = "DRAFT"
    period_locked: bool = False


class TimetableSlotInput(BaseModel):
    slot_date: date  # Specific date for the slot
    slot_number: int
    subject_name: str
    class_name: Optional[str] = None
    is_active: bool = True


class CalendarEntry(BaseModel):
    calendar_date: date
    day_type: str
    description: Optional[str] = None
