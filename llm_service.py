import os
import json
import google.generativeai as genai
from openai import OpenAI
from dotenv import load_dotenv
from database import get_session, PromptConfig

# Charger les variables d'environnement depuis .env
load_dotenv()

# Configuration par défaut
DEFAULT_SYSTEM_PROMPT = """
You are an expert AI & Financial Analyst. Your goal is to evaluate a company's investment potential specifically regarding the Artificial Intelligence revolution.

Input Data:
- Company Name & Symbol
- Sector & Description
- Key Financials: P/E Ratio, Market Cap, ROE, Debt/Equity, EPS Growth

Your task is to analyze this data and generate a JSON response with the following fields:
1. `score` (0-100): An AI Impact Score.
   - High Score (>70): Company has a strong "Data Moat" (proprietary data), deep AI product integration, and reasonable valuation.
   - Low Score (<40): Company's business model is at risk of being automated by AI (e.g., BPO, basic coding, simple HR), or valuation is completely disconnected from reality without AI substance.
2. `recommendation` ("LONG", "SHORT", or "NEUTRAL").
3. `reasoning` (string): A concise, bold explanation of the rating. Use specific terms like "Data Moat", "Automation Risk", "AI Infrastructure", "P/E Bubble".

Rules:
- Be critical. Don't just follow the hype.
- If P/E is > 60, penalize heavily unless they are the "shovel sellers" (like NVIDIA).
- If the company is in a vulnerable sector (Call Centers, Basic IT Services), penalize heavily.
- Output strictly valid JSON.
"""

class LLMService:
    def __init__(self):
        self.provider = "openai"
        self.api_key = None
        self.client = None
        self.model = "gpt-4o"
        self.base_url = None
        
        # Priority 1: OpenAI
        openai_key = os.getenv('OPENAI_KEY') or os.getenv('OPENAI_API_KEY')
        if openai_key:
            self.provider = "openai"
            self.api_key = openai_key
            self.model = "gpt-4o"
            self.client = OpenAI(api_key=self.api_key)
        else:
            # Priority 2: Gemini
            gemini_key = os.getenv('GEMINI_API_KEY')
            if gemini_key:
                self.provider = "gemini"
                self.api_key = gemini_key
                genai.configure(api_key=self.api_key)
                self.model = "gemini-2.0-flash"
            else:
                # Priority 3: Qwen
                qwen_key = os.getenv('QWEN_API_KEY')
                if qwen_key:
                    self.provider = "openai" # Compatible mode
                    self.api_key = qwen_key
                    self.base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"
                    self.model = "qwen-plus"
                    self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)

    def get_current_prompt(self):
        session = get_session()
        try:
            config = session.query(PromptConfig).filter_by(id='default').first()
            if config and config.system_prompt:
                return config.system_prompt
            
            # If not in DB, init it
            if not config:
                new_config = PromptConfig(id='default', system_prompt=DEFAULT_SYSTEM_PROMPT)
                session.add(new_config)
                session.commit()
            
            return DEFAULT_SYSTEM_PROMPT
        finally:
            session.close()

    def update_prompt(self, new_prompt):
        session = get_session()
        try:
            config = session.query(PromptConfig).filter_by(id='default').first()
            if not config:
                config = PromptConfig(id='default', system_prompt=new_prompt)
                session.add(config)
            else:
                config.system_prompt = new_prompt
            session.commit()
            return True
        except Exception as e:
            print(f"Error updating prompt: {e}")
            return False
        finally:
            session.close()

    def analyze_company(self, company_data, system_prompt=None):
        if not self.api_key:
            return None

        if not system_prompt:
            system_prompt = self.get_current_prompt()

        user_content = f"""
        Analyze this company:
        Symbol: {company_data.get('Symbol')}
        Name: {company_data.get('Name')}
        Sector: {company_data.get('Sector')}
        Description: {company_data.get('Description')}
        
        Financials:
        - Price: ${company_data.get('Price')}
        - P/E Ratio: {company_data.get('PERatio')}
        - Market Cap: ${company_data.get('MarketCapitalization')}
        - ROE: {company_data.get('ReturnOnEquityTTM')}
        - EPS Growth (5Y): {company_data.get('EPSGrowthPast5Years')}
        - Debt/Equity: {company_data.get('DebtToEquityRatio')}
        
        Output JSON only.
        """

        try:
            for attempt in range(3):
                try:
                    if self.provider == "gemini":
                        # Google GenAI way
                        model = genai.GenerativeModel(
                            self.model,
                            system_instruction=system_prompt,
                            generation_config={"response_mime_type": "application/json"}
                        )
                        response = model.generate_content(user_content)
                        return json.loads(response.text)
                        
                    else:
                        # OpenAI / Qwen way
                        if not self.client:
                            return None
                            
                        response = self.client.chat.completions.create(
                            model=self.model,
                            messages=[
                                {"role": "system", "content": system_prompt},
                                {"role": "user", "content": user_content}
                            ],
                            response_format={"type": "json_object"}
                        )
                        content = response.choices[0].message.content
                        return json.loads(content)
                except Exception as e:
                    # Log specific error for each attempt
                    print(f"  ⚠️ Attempt {attempt + 1} failed for {company_data.get('Symbol')}: {str(e)}")
                    if "429" in str(e) and attempt < 2:
                        wait_time = (attempt + 1) * 10
                        print(f"  Got 429 result, retrying in {wait_time}s...")
                        import time
                        time.sleep(wait_time)
                        continue
                    raise e
                
        except Exception as e:
            print(f"  🔴 LLM Analysis CRITICAL failure for {company_data.get('Symbol')} ({self.provider}): {e}")
            return {
                "score": 50,
                "recommendation": "NEUTRAL",
                "reasoning": f"Analysis failed ({self.provider}): {str(e)}"
            }
