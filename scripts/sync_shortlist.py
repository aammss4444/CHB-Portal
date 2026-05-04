from sqlalchemy import create_engine, select, and_
from sqlalchemy.orm import sessionmaker
from app.models.application import Application, ApplicationStatus
from app.models.shortlisted_candidate import ShortlistedCandidate
import os

from urllib.parse import quote_plus
password = quote_plus("Amey@p4444")
DATABASE_URL = f"postgresql://postgres:{password}@localhost:5432/chb_portal"

engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)
session = Session()

def check_sync():
    # Find applications with SHORTLISTED status
    apps = session.execute(select(Application).where(Application.status == ApplicationStatus.SHORTLISTED.value)).scalars().all()
    print(f"Found {len(apps)} applications with status SHORTLISTED")
    
    for app in apps:
        sc = session.execute(select(ShortlistedCandidate).where(
            and_(ShortlistedCandidate.application_id == app.id, ShortlistedCandidate.advertisement_id == app.advertisement_id)
        )).scalars().first()
        
        if sc:
            print(f"App {app.application_number} is correctly synced.")
        else:
            print(f"App {app.application_number} is NOT synced. Syncing now...")
            session.add(ShortlistedCandidate(
                advertisement_id=app.advertisement_id,
                application_id=app.id,
                candidate_id=app.candidate_id,
                shortlisted_by=None, # System sync
                shortlist_remarks="System auto-sync for missing shortlist record"
            ))
    
    session.commit()
    print("Sync complete.")

if __name__ == "__main__":
    check_sync()
