# init_db.py
from app import app, db

print("Connecting to database and creating tables...")
with app.app_context():
    db.create_all()
print("Tables created successfully.")
