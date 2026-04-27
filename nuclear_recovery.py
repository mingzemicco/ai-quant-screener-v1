import os
import json
import time
from dotenv import load_dotenv
from database import get_session, CompanyAnalysis
from llm_service import LLMService

# Load environment variables
load_dotenv()

def run_nuclear_recovery():
    """
    Nuclear Option: Uses OpenAI LLM to infer founder status for all companies
    where data is still missing or unreliable.
    """
    print("🚀 Starting Nuclear Recovery with OpenAI...")
    
    llm = LLMService()
    session = get_session()
    
    # Target companies with missing or 'Could not determine' status
    companies = session.query(CompanyAnalysis).filter(
        (CompanyAnalysis.founder_details == 'Could not determine founder status') |
        (CompanyAnalysis.founder_source == 'none') |
        (CompanyAnalysis.founders == None)
    ).all()
    
    print(f"   Targeting {len(companies)} companies for LLM inference.")
    print("=" * 60)
    
    success_count = 0
    failure_count = 0
    
    for i, company in enumerate(companies):
        print(f"[{i+1}/{len(companies)}] Processing {company.symbol} ({company.company_name})...")
        
        prompt = f"""
For the company {company.company_name} (Symbol: {company.symbol}):
- Who are the founders?
- Who is the current CEO and the Chairman?
- Does the founder still have an operational role (CEO) or on the board (Chairman)?

Respond in STRICT JSON format with these exact keys:
{{
    "founders": ["Name 1", "Name 2"],
    "currentCEO": "Individual Name",
    "currentChairman": "Individual Name",
    "isFounderCEO": true/false,
    "isFounderChairman": true/false,
    "founderInfluence": "high" | "medium" | "none",
    "founderBonus": 0, 5, 10, or 15
}}

Scoring Guide for founderBonus:
- 15: Founder is BOTH CEO and Chairman.
- 10: Founder is CEO.
- 5: Founder is Chairman only.
- 0: Founder has no active leadership role.
"""
        
        try:
            result = llm.analyze_raw(prompt)
            
            if result and isinstance(result, dict) and "founders" in result:
                # Update company data
                company.founders = result.get("founders", [])
                company.current_ceo = result.get("currentCEO", "")
                company.current_chairman = result.get("currentChairman", "")
                company.is_founder_ceo = str(result.get("isFounderCEO", False)).lower()
                company.is_founder_chairman = str(result.get("isFounderChairman", False)).lower()
                company.founder_influence = result.get("founderInfluence", "none")
                company.founder_bonus = result.get("founderBonus", 0)
                company.founder_source = "llm_nuclear"
                
                # Create details string
                details = f"Inferred by AI: Founders {', '.join(company.founders)}."
                if company.is_founder_ceo == 'true':
                    details += f" Founder {company.current_ceo} is CEO."
                if company.is_founder_chairman == 'true':
                    details += f" Founder {company.current_chairman} is Chairman."
                company.founder_details = details
                
                session.commit()
                success_count += 1
                print(f"   ✅ Done: {company.symbol} | Bonus: +{company.founder_bonus}")
            else:
                print(f"   ❌ Failed to get valid JSON for {company.symbol}")
                failure_count += 1
                
        except Exception as e:
            print(f"   ❌ Error processing {company.symbol}: {e}")
            session.rollback()
            failure_count += 1
            
        # Avoid hitting rate limits too hard
        time.sleep(0.5)

    print("=" * 60)
    print(f"🎉 Nuclear Recovery Complete!")
    print(f"   Success: {success_count}")
    print(f"   Failure: {failure_count}")
    
    session.close()

if __name__ == "__main__":
    run_nuclear_recovery()
