from database import get_session, CompanyAnalysis
import json
import os
from dotenv import load_dotenv

load_dotenv()

def check_count():
    session = get_session()
    count = session.query(CompanyAnalysis).count()
    
    # Also check how many are in sp500.json
    base_dir = os.path.dirname(os.path.abspath(__file__))
    json_path = os.path.join(base_dir, 'sp500.json')
    with open(json_path, 'r') as f:
        sp500_data = json.load(f)
    
    print(f"Database count: {count}")
    print(f"SP500 JSON count: {len(sp500_data)}")
    session.close()

if __name__ == "__main__":
    check_count()
