from __future__ import annotations


async def notify_letter_issued(candidate, appointment) -> None:
    # TODO: integrate SMTP / SMS gateway for production
    print(f"[NOTIFY] Letter issued to {getattr(candidate, 'email', 'candidate')} for {appointment.appointment_number}")


async def notify_letter_approved(principal, appointment) -> None:
    # TODO: integrate SMTP / SMS gateway for production
    print(f"[NOTIFY] Letter approved for principal={getattr(principal, 'email', 'principal')} {appointment.appointment_number}")


async def notify_letter_rejected(principal, appointment, reason) -> None:
    # TODO: integrate SMTP / SMS gateway for production
    print(
        f"[NOTIFY] Letter rejected for principal={getattr(principal, 'email', 'principal')} "
        f"{appointment.appointment_number}. reason={reason}"
    )


async def send_credentials(candidate, username, temp_password) -> None:
    # TODO: integrate SMTP / SMS gateway for production
    print(
        f"[NOTIFY] Credentials issued to {getattr(candidate, 'email', 'candidate')}: "
        f"username={username}, temp_password={temp_password}"
    )


async def notify_waitlist_promotion(candidate, appointment) -> None:
    # TODO: integrate SMTP / SMS gateway for production
    print(
        f"[NOTIFY] Waitlist promotion prepared for {getattr(candidate, 'email', 'candidate')} "
        f"appointment={appointment.appointment_number}"
    )


async def notify_waitlist_unavailable(recipient, context: str) -> None:
    # TODO: integrate SMTP / SMS gateway for production
    print(
        f"[NOTIFY] Waitlist unavailable alert for {getattr(recipient, 'email', 'staff')}: {context}"
    )

async def send_password_reset_email(email: str, token: str) -> None:
    # TODO: integrate SMTP provider for production
    # Example production link: reset_link = f"https://chbportal.example.com/reset-password?token={token}"
    reset_link = f"http://localhost:5173/reset-password?token={token}"
    print(
        f"\n=======================================================\n"
        f"[NOTIFY] Password Reset Requested for {email}\n"
        f"Reset Link: {reset_link}\n"
        f"=======================================================\n"
    )
