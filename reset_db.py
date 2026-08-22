from app.core.database import engine, Base
from app.models import user, document, chat

print("Dropping all existing tables...")
Base.metadata.drop_all(bind=engine)

print("Creating fresh tables with the updated schema...")
Base.metadata.create_all(bind=engine)

print("Done! Database reset with the latest schema.")