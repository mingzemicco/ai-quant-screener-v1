import os
import json
from database import get_session, CompanyAnalysis, get_db_engine
from sqlalchemy import text

# Updated IGV Holdings list (approx 119 stocks)
IGV_SYMBOLS = [
    "ADBE", "ADSK", "AKAM", "ALRM", "AMPL", "ANSS", "APP", "APPS", "ASAN", "AUR", 
    "AYX", "AZPN", "BCOV", "BIGC", "BILL", "BL", "BLKB", "BOX", "BSY", "CDNS", 
    "CFLT", "CRM", "CRWD", "CSP", "DBX", "DDOG", "DOCU", "DOMO", "DT", "EA", 
    "ESTC", "EVBG", "FIVN", "FORG", "FTNT", "FTV", "GDDY", "GEN", "GH", "GIB", 
    "GLBE", "GWRE", "HCP", "HUBS", "INTU", "JAMF", "MANH", "MDB", "MNDY", "MSFT", 
    "MSTR", "NCNO", "NET", "NOW", "NTNX", "OKTA", "ORCL", "OTEX", "PANW", "PATH", 
    "PAYC", "PCTY", "PD", "PEGA", "PLTR", "PRO", "PTC", "PYPL", "QMCO", "QNST", 
    "QTWO", "RAMP", "RNG", "ROP", "RPD", "S", "SAP", "SHOP", "SKLZ", "SMAR", 
    "SNOW", "SNPS", "SPT", "SSNC", "STNE", "SWI", "TEAM", "TENB", "TTD", "TTWO", 
    "TWLO", "TYL", "U", "UPWK", "VEEV", "VRNS", "WDAY", "WIX", "WK", "YEXT", 
    "ZEN", "ZI", "ZS", "G", "SNOW", "TOST", "UPST", "FRSH", "DUOL", "CONX", 
    "KVYO", "KLAC", "TYL", "MSTR", "ESTC", "PATH", "IOT", "MBLY", "RUM", "ARM"
]

def update_database_with_igv():
    engine = get_db_engine()
    session = get_session()
    
    print("🛠 Step 1: Adding 'is_igv' column if missing...")
    try:
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE company_analysis ADD COLUMN IF NOT EXISTS is_igv VARCHAR DEFAULT 'false'"))
            conn.commit()
        print("   ✅ Column verified/added.")
    except Exception as e:
        print(f"   ⚠️ Could not add column (it might already exist): {e}")

    print(f"🛠 Step 2: Marking {len(IGV_SYMBOLS)} IGV tickers...")
    
    # Reset all first
    session.query(CompanyAnalysis).update({CompanyAnalysis.is_igv: "false"})
    session.commit()
    
    added_count = 0
    updated_count = 0
    
    for symbol in IGV_SYMBOLS:
        company = session.query(CompanyAnalysis).filter_by(symbol=symbol).first()
        if company:
            company.is_igv = "true"
            updated_count += 1
        else:
            # Create a stub for new companies
            new_company = CompanyAnalysis(
                symbol=symbol,
                company_name=f"{symbol} (IGV)",
                is_igv="true",
                founder_details="Awaiting analysis...",
                founder_source="none"
            )
            session.add(new_company)
            added_count += 1
            
    session.commit()
    print(f"   ✅ Task Complete!")
    print(f"      - Updated existing: {updated_count}")
    print(f"      - Added new stubs: {added_count}")
    
    session.close()

if __name__ == "__main__":
    update_database_with_igv()
