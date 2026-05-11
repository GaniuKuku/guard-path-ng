from app.db.database import SessionLocal
from app.db.models import User
import sys

def promote_user(email: str, new_role: str):
    db = SessionLocal()
    user = db.query(User).filter(User.email == email).first()
    
    if not user:
        print(f"❌ User {email} not found.")
        return
        
    user.role = new_role
    db.commit()
    print(f"✅ Success: {email} is now an {new_role}!")
    db.close()

if __name__ == "__main__":
    # This lets you run the script from the terminal with arguments
    if len(sys.argv) != 3:
        print("Usage: python promote.py <email> <role>")
    else:
        promote_user(sys.argv[1], sys.argv[2])
