import os
from sqlalchemy.orm import Session
from app.db import SessionLocal, engine, Base
from app.models import Organisation, User, Rule, Fact, Term
from app.security import get_password_hash

def seed_database():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    
    if db.query(Organisation).first():
        print("Database already seeded.")
        db.close()
        return

    org = Organisation(name="Inkloom AI Org")
    db.add(org)
    db.commit()
    db.refresh(org)

    roles = ["creator", "manager", "reviewer", "admin"]
    for role in roles:
        user = User(
            email=f"{role}@brandwright.test",
            hashed_password=get_password_hash("password123"),
            role=role,
            organisation_id=org.id
        )
        db.add(user)

    rule1 = Rule(
        organisation_id=org.id,
        clause_number="R1.1",
        text="All external public facing content must explicitly state our official product name Brandwright.",
        category="messaging",
        status="approved"
    )
    rule2 = Rule(
        organisation_id=org.id,
        clause_number="R2.4",
        text="Do not use absolute superlatives such as 'the absolute best' or '100% unbreakable' without disclaimers.",
        category="claim",
        status="approved"
    )
    db.add_all([rule1, rule2])

    fact1 = Fact(
        organisation_id=org.id,
        text="Brandwright was founded in 2026.",
        owner="Compliance Team",
        source_url="https://brandwright.internal/facts/founded",
        status="approved"
    )
    fact2 = Fact(
        organisation_id=org.id,
        text="Brandwright processing engine latency is strictly below 150 milliseconds.",
        owner="Engineering Lead",
        source_url="https://brandwright.internal/facts/latency",
        status="approved"
    )
    db.add_all([fact1, fact2])

    term1 = Term(
        organisation_id=org.id,
        preferred="pre-publication brand governance",
        banned="content censor",
        notes="Maintain empowering, constructive tone."
    )
    db.add(term1)

    db.commit()
    db.close()
    print("Database seeding completed successfully for Inkloom AI Org.")

if __name__ == "__main__":
    seed_database()
