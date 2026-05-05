import io
import re
from dataclasses import dataclass


@dataclass
class AppointmentRenderError(Exception):
    missing_placeholders: list[str]

    def __str__(self) -> str:
        return f"Unreplaced placeholders found: {', '.join(self.missing_placeholders)}"


def render_appointment_letter(template_body: str, context: dict) -> str:
    rendered = template_body
    for key, value in context.items():
        # Handle both {{key}} and {{ key }}
        pattern = re.compile(r"\{\{\s*" + re.escape(key) + r"\s*\}\}")
        rendered = pattern.sub(str(value), rendered)

    leftovers = re.findall(r"\{\{.*?\}\}", rendered)
    if leftovers:
        missing = [token.strip("{} ") for token in leftovers]
        raise AppointmentRenderError(missing)
    return rendered


def generate_pdf(content: str, appointment_number: str) -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    y = height - 50

    pdf.setTitle(appointment_number)
    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(50, y, f"Appointment Letter: {appointment_number}")
    y -= 25

    pdf.setFont("Helvetica", 10)
    for line in content.splitlines():
        if y < 60:
            pdf.showPage()
            pdf.setFont("Helvetica", 10)
            y = height - 50
        pdf.drawString(50, y, line[:120])
        y -= 15

    pdf.save()
    buffer.seek(0)
    return buffer.read()
