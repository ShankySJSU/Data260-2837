import secrets
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from .domain.models import SessionToken, User

SESSION_DURATION_MINUTES = 30

def create_session(db: Session, user_id: int):
    token = secrets.token_hex(32)
    expires = datetime.utcnow() + timedelta(minutes=SESSION_DURATION_MINUTES)

    obj = SessionToken(id=token, user_id=user_id, expires_at=expires)
    db.add(obj)
    db.commit()
    return token

def validate_session(db: Session, token: str):
    session = db.query(SessionToken).filter(SessionToken.id == token).first()
    if session and session.expires_at > datetime.utcnow():
        return session.user_id
    return None

def delete_session(db: Session, token: str):
    session = db.query(SessionToken).filter(SessionToken.id == token).first()
    if session:
        db.delete(session)
        db.commit()