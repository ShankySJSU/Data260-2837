from web_application.database import db_session_basede26, engine, Base
from web_application.domain.models_users import AuthUser
from web_application.auth import hash_password
import web_application.domain.models  # noqa: F401 - registers the other tables


def seed():
    Base.metadata.create_all(bind=engine)
    db = db_session_basede26()
    users = [
        ("reader1", "test123", "reader"),
        ("writer1", "test123", "writer"),
        ("mod1", "test123", "moderator"),
    ]
    for username, pw, role in users:
        if not db.query(AuthUser).filter_by(username=username).first():
            db.add(AuthUser(username=username, password_hash=hash_password(pw), role=role))
    db.commit()
    db.close()
    print("Users seeded successfully.")


if __name__ == "__main__":
    seed()