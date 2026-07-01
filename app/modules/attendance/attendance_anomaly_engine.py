from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import List
from uuid import UUID

from app.core.config import settings
from app.modules.attendance.schemas import CalendarEntry, LectureLogInput, TimetableSlotInput


@dataclass
class AttendanceAnomaly:
    anomaly_type: str
    severity: str
    description: str


def _working_dates(recent_logs: List[LectureLogInput], calendar_entries: List[CalendarEntry]) -> dict[date, str]:
    holidays = {
        entry.calendar_date: entry.day_type
        for entry in calendar_entries
    }
    dates: dict[date, str] = {}
    for log in recent_logs:
        if log.lecture_date not in holidays:
            dates[log.lecture_date] = "WORKING"
        else:
            dates[log.lecture_date] = holidays[log.lecture_date]
    return dates


def run_attendance_anomaly_check(
    faculty_credential_id: UUID,
    lecture_log: LectureLogInput,
    recent_logs: List[LectureLogInput],
    timetable_slots: List[TimetableSlotInput],
    calendar_entries: List[CalendarEntry],
) -> List[AttendanceAnomaly]:
    """Evaluate deterministic attendance anomaly rules without any database access."""
    anomalies: list[AttendanceAnomaly] = []
    calendar_map = {entry.calendar_date: entry for entry in calendar_entries}
    same_day_logs = [log for log in recent_logs if log.lecture_date == lecture_log.lecture_date]

    holiday_entry = calendar_map.get(lecture_log.lecture_date)
    if holiday_entry and holiday_entry.day_type == "HOLIDAY":
        description = holiday_entry.description or "Holiday"
        anomalies.append(
            AttendanceAnomaly(
                anomaly_type="LECTURE_ON_HOLIDAY",
                severity="HIGH",
                description=f"Lecture logged on {lecture_log.lecture_date} which is marked as holiday: {description}",
            )
        )

    max_daily = settings.MAX_DAILY_LECTURES_POLICY
    if len(same_day_logs) > max_daily:
        anomalies.append(
            AttendanceAnomaly(
                anomaly_type="EXCESSIVE_DAILY_LECTURES",
                severity="HIGH",
                description=(
                    f"Faculty logged {len(same_day_logs)} lectures on {lecture_log.lecture_date}. "
                    f"Maximum allowed is {max_daily}."
                ),
            )
        )

    days_late = (lecture_log.created_at.date() - lecture_log.lecture_date).days
    if days_late > 3:
        anomalies.append(
            AttendanceAnomaly(
                anomaly_type="BACKDATED_LOG",
                severity="MEDIUM",
                description=f"Lecture on {lecture_log.lecture_date} was logged {days_late} days late.",
            )
        )

    expected_slot = next(
        (
            slot
            for slot in timetable_slots
            if slot.is_active
            and slot.slot_date == lecture_log.lecture_date
            and slot.slot_number == lecture_log.slot_number
        ),
        None,
    )
    if expected_slot and expected_slot.subject_name.strip() != lecture_log.subject_name.strip():
        anomalies.append(
            AttendanceAnomaly(
                anomaly_type="SUBJECT_MISMATCH",
                severity="MEDIUM",
                description=(
                    f"Logged subject '{lecture_log.subject_name}' differs from timetable "
                    f"'{expected_slot.subject_name}' for slot {lecture_log.slot_number} on {lecture_log.lecture_date}."
                ),
            )
        )

    normalized_topic = lecture_log.topic_covered.lower().strip()
    topic_count = sum(1 for log in recent_logs if log.topic_covered.lower().strip() == normalized_topic)
    if topic_count > 3:
        anomalies.append(
            AttendanceAnomaly(
                anomaly_type="DUPLICATE_TOPIC",
                severity="MEDIUM",
                description=(
                    f"Topic '{lecture_log.topic_covered}' has been logged {topic_count} times in the last 30 days."
                ),
            )
        )

    same_class_attendance = [
        log.attendance_count
        for log in recent_logs
        if log.class_name == lecture_log.class_name and log.attendance_count is not None
    ]
    if lecture_log.attendance_count is not None and same_class_attendance:
        average = sum(same_class_attendance) / len(same_class_attendance)
        if average > 0 and lecture_log.attendance_count > (average * 1.1):
            anomalies.append(
                AttendanceAnomaly(
                    anomaly_type="UNUSUAL_ATTENDANCE_COUNT",
                    severity="LOW",
                    description=(
                        f"Attendance count {lecture_log.attendance_count} is unusually high for class "
                        f"{lecture_log.class_name}. Recent average: {average:.1f}."
                    ),
                )
            )

    working_dates = sorted(
        day
        for day, day_type in _working_dates(recent_logs, calendar_entries).items()
        if day_type == "WORKING"
    )
    streak = 0
    previous: date | None = None
    for working_day in working_dates:
        count_for_day = sum(1 for log in recent_logs if log.lecture_date == working_day)
        if count_for_day >= max_daily:
            if previous and working_day == previous + timedelta(days=1):
                streak += 1
            else:
                streak = 1
            previous = working_day
        else:
            streak = 0
            previous = None
    if streak >= 15:
        anomalies.append(
            AttendanceAnomaly(
                anomaly_type="CONSISTENTLY_FULL_SCHEDULE",
                severity="LOW",
                description=(
                    f"Faculty has logged maximum lectures every day for {streak} days. Verify accuracy."
                ),
            )
        )

    if lecture_log.lecture_date < lecture_log.created_at.date():
        scheduled_slots = [
            slot for slot in timetable_slots if slot.is_active and slot.slot_date == lecture_log.lecture_date
        ]
        if scheduled_slots and len(same_day_logs) == 0:
            anomalies.append(
                AttendanceAnomaly(
                    anomaly_type="MISSING_LOGS",
                    severity="MEDIUM",
                    description=(
                        f"No lecture logs found for {len(scheduled_slots)} scheduled slots on {lecture_log.lecture_date}."
                    ),
                )
            )

    if lecture_log.period_locked:
        month_label = lecture_log.lecture_date.strftime("%B %Y")
        anomalies.append(
            AttendanceAnomaly(
                anomaly_type="LOG_AFTER_PERIOD_CLOSE",
                severity="HIGH",
                description=f"Attendance period for {month_label} is closed. Log cannot be accepted.",
            )
        )

    return anomalies
