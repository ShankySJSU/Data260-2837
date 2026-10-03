import random
from sqlalchemy.orm import Session
from models import RestaurantInspection, InspectionRelated
from database import db_session_basede26, Base, engine

SEED = 2837
random.seed(SEED)

def run_seed():
    Base.metadata.create_all(bind=engine)
    db: Session = db_session_basede26()

    word_choices = ["Spicy", "Golden", "Urban", "Rustic", "Bar", "Garden", "Bistro", "Cafe", "Deli", "Grill"]
    # 1. Seed 5000 primary records
    inspections = []
    for i in range(5000):
        random_words = random.choice(word_choices)
        name = f"Restaurant_{random_words}_{i}"
        status = random.choice(["PASS", "FAIL", "WARNING"])
        obj = RestaurantInspection(name=name, status=status)
        db.add(obj)
        inspections.append(obj)

    db.commit()

    # 2. Seed 200 related rows
    for i in range(200):
        parent = inspections[random.randint(0, 4999)]
        related_text = f"Related details row {i}"
        related = InspectionRelated(inspection_id=parent.id, details=related_text)
        db.add(related)

    db.commit()
    db.close()
    print("Seeding completed.")

if __name__ == "__main__":
    run_seed()