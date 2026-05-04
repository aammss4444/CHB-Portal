from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from app.models.scoring_weight_config import ScoringWeightConfig
from datetime import date
from urllib.parse import quote_plus
import uuid

password = quote_plus("Amey@p4444")
DATABASE_URL = f"postgresql://postgres:{password}@localhost:5432/chb_portal"

engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)
session = Session()

def seed_default_weights():
    # Check if exists
    existing = session.execute(select(ScoringWeightConfig).where(ScoringWeightConfig.config_name == "DEFAULT")).scalars().first()
    if existing:
        print("Default weight config already exists.")
        return

    default_config = ScoringWeightConfig(
        id=uuid.uuid4(),
        config_name="DEFAULT",
        qualification_weight=40.0,
        experience_weight=10.0,
        interview_weight=50.0,
        publication_weight=0.0,
        reservation_weight=0.0,
        set_by_role="ADMIN",
        effective_from=date(2026, 1, 1),
        is_active=True
    )
    session.add(default_config)
    session.commit()
    print("Default weight config (Qual: 40%, Exp: 10%, Int: 50%) created successfully.")

if __name__ == "__main__":
    seed_default_weights()
