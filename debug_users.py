from database import get_session, User
from werkzeug.security import check_password_hash
import os
from dotenv import load_dotenv

load_dotenv()

def debug_users():
    session = get_session()
    users = session.query(User).all()
    print(f"Total users found: {len(users)}")
    
    test_password = "123456"
    for u in users:
        is_correct = check_password_hash(u.password_hash, test_password)
        print(f"User: {u.email} | Hash: {u.password_hash[:20]}... | Password '123456' check: {is_correct}")
    
    session.close()

if __name__ == "__main__":
    debug_users()
