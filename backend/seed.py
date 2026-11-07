
import os
import argparse
import secrets
from uuid import uuid4

from sqlalchemy.orm import Session

from app.api_v1 import DEMO_ORGANISATION_NAME
from app.db import SessionLocal
from app.models import (
    AIUsageLog,
    Alert,
    Asset,
    AuditLog,
    ContentItem,
    ContentVersion,
    Comment,
    Fact,
    FactUsage,
    Finding,
    FindingDecision,
    GuidelineDoc,
    Organisation,
    ReviewEvent,
    Rule,
    RuleClarification,
    Term,
    User,
)
from app.review.embeddings import create_embedder, term_embedding_text
from app.security import get_password_hash


DEMO_USERS = {
    "creator": "creator@demo.brandwright.app",
    "reviewer": "reviewer@demo.brandwright.app",
    "admin": "admin@demo.brandwright.app",
}


def _one(db: Session, model, **filters):
    return db.query(model).filter_by(**filters).first()


def _get_or_add(db: Session, model, lookup: dict, values: dict):
    record = _one(db, model, **lookup)
    if record is None:
        record = model(**values)
        db.add(record)
        db.flush()
    return record


def _ensure_demo_users(
    db: Session, organisation: Organisation
) -> dict[str, User]:

    users = {}

    admin_password = os.getenv("DEMO_ADMIN_PASSWORD")

    if admin_password and len(admin_password) < 12:
        raise ValueError(
            "DEMO_ADMIN_PASSWORD must contain at least 12 characters."
        )

    for role, email in DEMO_USERS.items():

        user = _one(db, User, email=email)

        if user is None:

            if role == "admin" and admin_password:
                password = admin_password
            else:
                password = secrets.token_urlsafe(32)

            user = User(
                email=email,
                hashed_password=get_password_hash(password),
                role=role,
                organisation_id=organisation.id,
            )

            db.add(user)
            db.flush()

            del password

        elif user.organisation_id != organisation.id:

            raise RuntimeError(
                f"The reserved demo login email is already in use: {email}"
            )

        else:

            if user.role != role:
                user.role = role

            # Update Admin password only when configured in Render.
            if role == "admin" and admin_password:
                user.hashed_password = get_password_hash(
                    admin_password
                )

        users[role] = user

    return users


def _ensure_knowledge(db: Session, organisation: Organisation):

    embedder = create_embedder()

    guideline = _get_or_add(
        db,
        GuidelineDoc,
        {
            "organisation_id": organisation.id,
            "title": "Brandwright approved messaging",
        },
        {
            "organisation_id": organisation.id,
            "title": "Brandwright approved messaging",
        },
    )

    rule_specs = [
        {
            "clause_number": "BW-01",
            "text": "Use the official product name Brandwright in public-facing content.",
            "category": "terminology",
            "type": "required_disclaimer",
            "config": {"phrase": "Brandwright"},
        },
        {
            "clause_number": "BW-02",
            "text": "Do not use unsupported absolute superlatives such as absolute best.",
            "category": "claim",
            "type": "superlative",
            "config": {
                "terms": [
                    "absolute best",
                    "best ever",
                    "number one",
                ]
            },
        },
        {
            "clause_number": "BW-03",
            "text": "Do not make absolute reliability guarantees such as 100% unbreakable or zero errors.",
            "category": "claim",
            "type": "superlative",
            "config": {
                "terms": [
                    "100% unbreakable",
                    "zero errors",
                    "guarantees zero",
                ]
            },
        },
    ]

    rules = {}

    for spec in rule_specs:

        fields = {
            **spec,
            "organisation_id": organisation.id,
            "guideline_id": guideline.id,
            "channels": ["all"],
            "status": "approved",
            "embedding": embedder.embed(spec["text"]),
        }

        rule = _get_or_add(
            db,
            Rule,
            {
                "organisation_id": organisation.id,
                "clause_number": spec["clause_number"],
            },
            fields,
        )

        rules[spec["clause_number"]] = rule

    facts_data = [
        (
            "Brandwright helps teams review public-facing content against approved guidance.",
            "Product team",
            "https://demo.brandwright.app/facts/product",
        ),
        (
            "Brandwright provides recommendations for human review and does not publish content automatically.",
            "Governance team",
            "https://demo.brandwright.app/facts/human-review",
        ),
        (
            "Brandwright was founded in 2026.",
            "Company records",
            "https://demo.brandwright.app/facts/company",
        ),
    ]

    for text, owner, source_url in facts_data:

        _get_or_add(
            db,
            Fact,
            {
                "organisation_id": organisation.id,
                "source_url": source_url,
            },
            {
                "organisation_id": organisation.id,
                "text": text,
                "owner": owner,
                "source_url": source_url,
                "status": "approved",
                "embedding": embedder.embed(text),
            },
        )

    term_specs = [
        (
            "brand governance",
            "content censor",
            "Use constructive, people-first language.",
        ),
        (
            "Brandwright",
            "the absolute best",
            "Use the approved product name and avoid unsupported comparisons.",
        ),
    ]

    for preferred, banned, notes in term_specs:

        _get_or_add(
            db,
            Term,
            {
                "organisation_id": organisation.id,
                "preferred": preferred,
                "banned": banned,
            },
            {
                "organisation_id": organisation.id,
                "preferred": preferred,
                "banned": banned,
                "notes": notes,
                "embedding": embedder.embed(
                    term_embedding_text(preferred, banned, notes)
                ),
            },
        )

    return rules


def _add_sample_finding(
    db: Session,
    version: ContentVersion,
    rule: Rule,
    body: str,
    phrase: str,
    decision: tuple[str, str, User] | None = None,
) -> Finding:

    start = body.casefold().find(phrase.casefold())

    finding = Finding(
        id=uuid4(),
        content_version_id=version.id,
        span_start=max(start, 0),
        span_end=max(start, 0) + len(phrase),
        category=rule.category,
        severity="high",
        check_type="rule",
        status="violation",
        confidence=1.0,
        source_type="rule",
        source_id=rule.id,
        explanation=(
            f"This wording conflicts with approved guideline "
            f"{rule.clause_number}."
        ),
        suggestion_text=(
            "Use a factual description supported by approved sources."
        ),
        intent_preserved=True,
    )

    db.add(finding)
    db.flush()

    if decision:

        action, reason, user = decision

        db.add(
            FindingDecision(
                finding_id=finding.id,
                user_id=user.id,
                action=action,
                reason=reason,
            )
        )

    return finding


def _ensure_sample_submissions(
    db: Session,
    organisation: Organisation,
    users: dict[str, User],
    rules: dict[str, Rule],
):

    samples = [
        {
            "title": "Website product introduction",
            "status": "draft",
            "body": (
                "Introducing Brandwright, a clearer way to "
                "review content before publication."
            ),
            "intent": "Introduce Brandwright to prospective customers.",
            "findings": [],
        },
        {
            "title": "Quarterly launch announcement",
            "status": "in_review",
            "body": (
                "Introducing Brandwright, the absolute best "
                "compliance tool for growing teams."
            ),
            "intent": "Announce the product to growing teams.",
            "findings": [
                ("BW-02", "absolute best", None)
            ],
        },
        {
            "title": "Product page reliability claim",
            "status": "changes_requested",
            "body": (
                "Brandwright is 100% unbreakable and "
                "guarantees zero errors."
            ),
            "intent": "Explain how Brandwright supports review teams.",
            "findings": [
                (
                    "BW-03",
                    "100% unbreakable",
                    (
                        "dismiss",
                        "Please replace with a measurable, approved statement.",
                        users["creator"],
                    ),
                ),
                ("BW-03", "guarantees zero", None),
            ],
        },
        {
            "title": "Customer newsletter",
            "status": "approved",
            "body": (
                "Brandwright helps teams review public-facing "
                "content against approved guidance."
            ),
            "intent": "Describe the approved Brandwright workflow.",
            "findings": [],
        },
    ]

    for sample in samples:

        content = _one(
            db,
            ContentItem,
            organisation_id=organisation.id,
            title=sample["title"],
        )

        if content is not None:
            continue

        content = ContentItem(
            organisation_id=organisation.id,
            creator_id=users["creator"].id,
            title=sample["title"],
            current_version_no=1,
            status=sample["status"],
        )

        db.add(content)
        db.flush()

        version = ContentVersion(
            content_id=content.id,
            version_no=1,
            body=sample["body"],
            intent=sample["intent"],
            channel="Website",
            status=sample["status"],
            review_job_status=(
                "completed"
                if sample["status"] in {
                    "approved",
                    "changes_requested",
                }
                else None
            ),
            review_stage=(
                "completed"
                if sample["status"] in {
                    "approved",
                    "changes_requested",
                }
                else None
            ),
        )

        db.add(version)
        db.flush()

        for clause_number, phrase, decision in sample["findings"]:

            _add_sample_finding(
                db,
                version,
                rules[clause_number],
                sample["body"],
                phrase,
                decision,
            )


def seed_demo_data(db: Session) -> None:

    organisation = _get_or_add(
        db,
        Organisation,
        {"name": DEMO_ORGANISATION_NAME},
        {"name": DEMO_ORGANISATION_NAME},
    )

    users = _ensure_demo_users(db, organisation)

    rules = _ensure_knowledge(db, organisation)

    _ensure_sample_submissions(
        db,
        organisation,
        users,
        rules,
    )


def reset_demo_data(db: Session) -> None:

    organisation = _one(
        db,
        Organisation,
        name=DEMO_ORGANISATION_NAME,
    )

    if organisation is None:
        seed_demo_data(db)
        return

    content_items = db.query(ContentItem).filter(
        ContentItem.organisation_id == organisation.id
    ).all()

    content_ids = [item.id for item in content_items]

    versions = db.query(ContentVersion).filter(
        ContentVersion.content_id.in_(content_ids)
    ).all() if content_ids else []

    version_ids = [version.id for version in versions]

    findings = db.query(Finding).filter(
        Finding.content_version_id.in_(version_ids)
    ).all() if version_ids else []

    finding_ids = [finding.id for finding in findings]

    db.query(AIUsageLog).filter(
        AIUsageLog.organisation_id == organisation.id
    ).delete(synchronize_session=False)

    if finding_ids:

        db.query(FindingDecision).filter(
            FindingDecision.finding_id.in_(finding_ids)
        ).delete(synchronize_session=False)

        db.query(Finding).filter(
            Finding.id.in_(finding_ids)
        ).delete(synchronize_session=False)

    if version_ids:

        db.query(FactUsage).filter(
            FactUsage.content_version_id.in_(version_ids)
        ).delete(synchronize_session=False)

        db.query(ReviewEvent).filter(
            ReviewEvent.content_version_id.in_(version_ids)
        ).delete(synchronize_session=False)

        db.query(ContentVersion).filter(
            ContentVersion.id.in_(version_ids)
        ).delete(synchronize_session=False)

    if content_ids:

        db.query(Comment).filter(
            Comment.content_id.in_(content_ids)
        ).delete(synchronize_session=False)

        db.query(ContentItem).filter(
            ContentItem.id.in_(content_ids)
        ).delete(synchronize_session=False)

    rule_ids = [
        rule.id
        for rule in db.query(Rule).filter(
            Rule.organisation_id == organisation.id
        ).all()
    ]

    if rule_ids:

        db.query(RuleClarification).filter(
            RuleClarification.rule_id.in_(rule_ids)
        ).delete(synchronize_session=False)

    db.query(AuditLog).filter(
        AuditLog.organisation_id == organisation.id
    ).delete(synchronize_session=False)

    db.query(Alert).filter(
        Alert.organisation_id == organisation.id
    ).delete(synchronize_session=False)

    db.query(Asset).filter(
        Asset.organisation_id == organisation.id
    ).delete(synchronize_session=False)

    db.query(Term).filter(
        Term.organisation_id == organisation.id
    ).delete(synchronize_session=False)

    db.query(Rule).filter(
        Rule.organisation_id == organisation.id
    ).delete(synchronize_session=False)

    db.query(Fact).filter(
        Fact.organisation_id == organisation.id
    ).delete(synchronize_session=False)

    db.query(GuidelineDoc).filter(
        GuidelineDoc.organisation_id == organisation.id
    ).delete(synchronize_session=False)

    db.query(User).filter(
        User.organisation_id == organisation.id,
        User.email.notin_(tuple(DEMO_USERS.values())),
    ).delete(synchronize_session=False)

    seed_demo_data(db)


def run_command(command: str) -> None:

    db = SessionLocal()

    try:

        if command == "reset-demo-data":
            reset_demo_data(db)
        else:
            seed_demo_data(db)

        db.commit()

    except Exception:

        db.rollback()
        raise

    finally:

        db.close()


if __name__ == "__main__":

    parser = argparse.ArgumentParser(
        description="Create or reset fictional Brandwright demo data."
    )

    parser.add_argument(
        "command",
        nargs="?",
        choices=(
            "seed-demo-data",
            "reset-demo-data",
        ),
        default="seed-demo-data",
    )

    run_command(parser.parse_args().command)
