from web_application.database import db_session_basede26
from web_application.domain.models_users import AuthUser
from web_application.auth import hash_password

def seed():
    db = db_session_basede26()

    users = [
        ("reader1", "test123", "reader"),
        ("writer1", "test123", "writer"),
        ("mod1", "test123", "moderator"),
    ]

    for username, pw, role in users:
        hashed = hash_password(pw)
        user = AuthUser(username=username, password_hash=hashed, role=role)
        db.add(user)

    db.commit()
    db.close()
    print("Users seeded successfully.")

if __name__ == "__main__":
    seed()