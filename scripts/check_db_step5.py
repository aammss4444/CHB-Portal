import asyncio
from sqlalchemy import select
from app.db.session import AsyncSessionLocal
from app.models.selection_round import SelectionRound
from app.models.shortlisted_candidate import ShortlistedCandidate
from app.models.interview_marks import InterviewMarks

async def check():
    async with AsyncSessionLocal() as db:
        # Get last round
        round_obj = (await db.execute(select(SelectionRound).order_by(SelectionRound.created_at.desc()))).scalars().first()
        if not round_obj:
            print("No rounds found")
            return
        
        print(f"Round: {round_obj.id} ({round_obj.round_type}) Status: {round_obj.status}")
        
        scs = (await db.execute(select(ShortlistedCandidate).where(ShortlistedCandidate.round_id == round_obj.id))).scalars().all()
        print(f"Shortlisted Candidates ({len(scs)}):")
        for sc in scs:
            marks = (await db.execute(select(InterviewMarks).where(
                and_(InterviewMarks.round_id == round_obj.id, InterviewMarks.application_id == sc.application_id)
            ))).scalars().first()
            # Note: need and_ import
            print(f"  App: {sc.application_id} Present: {sc.is_present} Marks: {'YES' if marks else 'NO'}")

if __name__ == "__main__":
    from sqlalchemy import and_
    asyncio.run(check())
