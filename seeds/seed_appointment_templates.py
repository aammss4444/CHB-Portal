from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.models.appointment_template import AppointmentTemplate


EN_TEMPLATE = """Appointment Number: {{appointment_number}}
Date: {{issue_date}}

To,
{{candidate_name}}

Subject: Appointment as {{designation}}

You are hereby appointed as {{designation}} at {{institution_name}}, {{course_name}} for academic year {{academic_year}}.
Your joining date is {{joining_date}} and remuneration is {{salary_per_lecture}} per lecture.

Please report to the undersigned and complete formalities before joining.

Principal
{{principal_name}}
"""


MR_TEMPLATE = """नियुक्ती क्रमांक: {{appointment_number}}
दिनांक: {{issue_date}}

प्रति,
{{candidate_name}}

विषय: {{designation}} म्हणून नियुक्ती

आपली {{institution_name}}, {{course_name}} येथे शैक्षणिक वर्ष {{academic_year}} साठी {{designation}} म्हणून नियुक्ती करण्यात येत आहे.
आपली रुजू होण्याची तारीख {{joining_date}} असून मानधन प्रति व्याख्यान {{salary_per_lecture}} असेल.

कृपया निर्धारित तारखेपूर्वी आवश्यक कागदपत्रांसह हजर राहावे.

प्राचार्य
{{principal_name}}
"""


async def run() -> None:
    async with AsyncSessionLocal() as db:
        existing_en = (
            await db.execute(
                select(AppointmentTemplate).where(
                    AppointmentTemplate.name == "CHB_APPOINTMENT_V1",
                    AppointmentTemplate.language == "EN",
                )
            )
        ).scalars().first()
        if not existing_en:
            db.add(
                AppointmentTemplate(
                    name="CHB_APPOINTMENT_V1",
                    language="EN",
                    template_body=EN_TEMPLATE,
                    is_active=True,
                )
            )

        existing_mr = (
            await db.execute(
                select(AppointmentTemplate).where(
                    AppointmentTemplate.name == "CHB_APPOINTMENT_V1",
                    AppointmentTemplate.language == "MR",
                )
            )
        ).scalars().first()
        if not existing_mr:
            db.add(
                AppointmentTemplate(
                    name="CHB_APPOINTMENT_V1",
                    language="MR",
                    template_body=MR_TEMPLATE,
                    is_active=True,
                )
            )
        await db.commit()
        print("Appointment templates seeded")


if __name__ == "__main__":
    import asyncio

    asyncio.run(run())
