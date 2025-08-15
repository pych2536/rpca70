from app import app, db

print("--- Starting Database Initialization ---")
try:
    with app.app_context():
        print("Creating all database tables...")
        db.create_all()
    print("--- Database Initialization Successful ---")
except Exception as e:
    print(f"--- AN ERROR OCCURRED DURING INITIALIZATION: {e} ---")
