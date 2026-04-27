"""
Founder-LED Company Detection Service
Uses a hybrid approach: Wikidata (structured) + Wikipedia (context) + LLM (fallback)
"""
import requests
import json
import time
import re
from typing import Dict, List, Optional, Tuple


class FounderService:
    """Service to detect if a company is founder-led (CEO/Chairman = Founder)"""

    WIKIDATA_SEARCH_URL = "https://www.wikidata.org/w/api.php"
    WIKIDATA_SPARQL_URL = "https://query.wikidata.org/sparql"
    WIKIPEDIA_API_URL = "https://en.wikipedia.org/w/api.php"
    WIKIPEDIA_SUMMARY_URL = "https://en.wikipedia.org/api/rest_v1/page/summary"
    USER_AGENT = "AIQuantScreener/1.0 (https://github.com/ai-quant-screener)"

    def __init__(self, llm_service=None):
        self.llm_service = llm_service
        self._cache = {}  # In-memory cache for Wikidata IDs

    # ─────────────────────────────────────────────
    # PUBLIC API
    # ─────────────────────────────────────────────

    def get_founder_status(self, ticker: str, company_name: str) -> Dict:
        """Main entry point: returns founder-led status for a company."""
        print(f"  🔍 Checking founder status for {ticker} ({company_name})...")

        # Step 1: Try Wikidata (structured, most reliable)
        result = self._try_wikidata(ticker, company_name)
        if result and result.get("founders"):
            result["source"] = "wikidata"
            result = self._calculate_score(result)
            print(f"  ✅ Wikidata: {ticker} | Founders: {result['founders']} | CEO: {result['currentCEO']} | Bonus: +{result['founderBonus']}")
            return result

        # Step 2: Try Wikipedia + Regex fallback
        print(f"  ⚠️ Wikidata incomplete for {ticker}, trying Wikipedia fallback...")
        result = self._try_wikipedia_fallback(ticker, company_name)
        if result and result.get("founders"):
            result = self._calculate_score(result)
            print(f"  ✅ Wiki Fallback: {ticker} | Founders: {result['founders']} | CEO: {result['currentCEO']} | Bonus: +{result['founderBonus']}")
            return result

        # Step 3: Final fallback — LLM only
        if self.llm_service:
            print(f"  ⚠️ Wikipedia failed for {ticker}, trying LLM only...")
            result = self._try_llm_only(ticker, company_name)
            if result:
                result = self._calculate_score(result)
                print(f"  ✅ LLM-only: {ticker} | Founders: {result['founders']} | CEO: {result['currentCEO']} | Bonus: +{result['founderBonus']}")
                return result

        # Nothing worked
        print(f"  ❌ Could not determine founder status for {ticker}")
        return self._empty_result()

    # ─────────────────────────────────────────────
    # WIKIDATA APPROACH
    # ─────────────────────────────────────────────

    _STRIP_SUFFIXES = [
        "Common Stock", "Class A", "Class B", "Class C",
        "Incorporated", "Corporation", "Holdings", "International",
        "Technologies", "Enterprises", "Solutions", "Services",
        "Inc.", "Inc", "Corp.", "Corp", "Co.", "Co",
        "Ltd.", "Ltd", "PLC", "plc", "LLC", "LP", "L.P.",
        "N.V.", "NV", "S.A.", "SE", "AG",
        "& Company", "& Co.", "& Co",
        "Group", "The",
    ]

    def _clean_company_name(self, raw_name: str) -> list:
        if not raw_name: return []
        name = raw_name.split(" - ")[0].strip()
        cleaned = name
        for suffix in self._STRIP_SUFFIXES:
            if cleaned.rstrip("., ").endswith(suffix):
                idx = cleaned.rstrip("., ").rfind(suffix)
                cleaned = cleaned[:idx].rstrip("., ")
        cleaned = cleaned.replace(".com", "").strip()
        if cleaned.startswith("The "): cleaned = cleaned[4:]
        variants = []
        if cleaned: variants.append(cleaned)
        if name not in variants: variants.append(name)
        return variants

    def _find_by_ticker(self, ticker: str) -> Optional[str]:
        query = f"""
        SELECT ?item WHERE {{
          ?item p:P414 [pq:P117 "{ticker}"].
        }} LIMIT 1
        """
        try:
            resp = requests.get(self.WIKIDATA_SPARQL_URL, params={"query": query, "format": "json"}, headers={"User-Agent": self.USER_AGENT}, timeout=10)
            if resp.status_code == 200:
                bindings = resp.json().get("results", {}).get("bindings", [])
                if bindings: return bindings[0]["item"]["value"].split("/")[-1]
        except: pass
        return None

    def _find_wikidata_id(self, company_name: str) -> Optional[str]:
        variants = self._clean_company_name(company_name)
        for search_name in variants:
            try:
                params = {"action": "wbsearchentities", "search": search_name, "language": "en", "format": "json", "limit": 3}
                resp = requests.get(self.WIKIDATA_SEARCH_URL, params=params, headers={"User-Agent": self.USER_AGENT}, timeout=10)
                if resp.status_code == 200:
                    results = resp.json().get("search", [])
                    if results: return results[0]["id"]
            except: pass
        return None

    def _query_wikidata_sparql(self, qid: str) -> Dict:
        query = f"""
        SELECT DISTINCT ?founderLabel ?ceoLabel ?chairLabel WHERE {{
          OPTIONAL {{
            {{ wd:{qid} wdt:P112 ?founder. }}
            UNION
            {{ ?founder wdt:P112 wd:{qid}. }}
            UNION
            {{ wd:{qid} wdt:P170 ?founder. }}
            UNION
            {{ wd:{qid} wdt:P127 ?founder. ?founder wdt:P31 wd:Q5. }}
          }}
          OPTIONAL {{
            wd:{qid} p:P169 ?ceoStmt. ?ceoStmt ps:P169 ?ceo.
            FILTER NOT EXISTS {{ ?ceoStmt pq:P582 ?endDate. }}
          }}
          OPTIONAL {{
            wd:{qid} p:P488 ?chairStmt. ?chairStmt ps:P488 ?chair.
            FILTER NOT EXISTS {{ ?chairStmt pq:P582 ?endDate2. }}
          }}
          SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
        }}
        """
        try:
            resp = requests.get(self.WIKIDATA_SPARQL_URL, params={"query": query, "format": "json"}, headers={"User-Agent": self.USER_AGENT}, timeout=15)
            if resp.status_code != 200: return {}
            data = resp.json()
            bindings = data.get("results", {}).get("bindings", [])
            founders, ceos, chairs = set(), set(), set()
            for b in bindings:
                if "founderLabel" in b: founders.add(b["founderLabel"]["value"])
                if "ceoLabel" in b: ceos.add(b["ceoLabel"]["value"])
                if "chairLabel" in b: chairs.add(b["chairLabel"]["value"])
            return {
                "founders": [f for f in founders if self._is_latin(f)],
                "currentCEO": list(ceos)[-1] if ceos else "",
                "currentChairman": list(chairs)[-1] if chairs else ""
            }
        except: return {}

    def _try_wikidata(self, ticker: str, company_name: str) -> Optional[Dict]:
        qid = self._find_by_ticker(ticker) or self._find_wikidata_id(company_name)
        if not qid: return None
        data = self._query_wikidata_sparql(qid)
        if not data or not data.get("founders"): return None
        
        f_norm = set(self._normalize_name(f) for f in data["founders"])
        ceo_n, chair_n = data.get("currentCEO", ""), data.get("currentChairman", "")
        is_ceo = self._normalize_name(ceo_n) in f_norm if ceo_n else False
        is_chair = self._normalize_name(chair_n) in f_norm if chair_n else False
        
        return {"isFounderCEO": is_ceo, "isFounderChairman": is_chair, "founders": data["founders"], "currentCEO": ceo_n, "currentChairman": chair_n}

    # ─────────────────────────────────────────────
    # WIKIPEDIA & REGEX FALLBACK
    # ─────────────────────────────────────────────

    def _regex_founder_fallback(self, text: str) -> List[str]:
        """Powerful Regex to extract names even with middle initials and suffixes."""
        # This version handles: 'Michael L. Riordan', 'Steve Jobs', 'X, Y, and Z'
        patterns = [
            r"(?:founded|created|started)\s+by\s+((?:[A-Z][a-zA-Z0-9.\-]+\s*){2,}(?:,\s*(?:[A-Z][a-zA-Z0-9.\-]+\s*){2,})*)",
            r"([A-Z][a-zA-Z0-9.\-]+\s*(?:[A-Z][a-zA-Z0-9.\-]+\s*)+)\s+(?:founded|co-founded)\s+",
            r"founders?\s+(?:are|is|include)\s+((?:[A-Z][a-zA-Z0-9.\-]+\s*){2,}(?:,\s*(?:[A-Z][a-zA-Z0-9.\-]+\s*){2,})*)",
        ]
        results = []
        import re
        for p in patterns:
            matches = re.finditer(p, text)
            for m in matches:
                # Capture group 1, split by 'and' or ','
                raw_names = re.split(r",\s*|\s+and\s+", m.group(1))
                for n in raw_names:
                    clean = n.strip().strip(",.")
                    # Must have at least 2 parts (First Last) and not containing common stop words
                    if len(clean.split()) >= 2 and not any(sw in clean for sw in ["American", "Multinational", "Technology", "Company", "Incorporated"]):
                        results.append(clean)
        return list(set(results))

    def _try_wikipedia_fallback(self, ticker: str, company_name: str) -> Optional[Dict]:
        """Search Wikipedia and use both Regex and LLM to parse the content."""
        variants = self._clean_company_name(company_name)
        search_query = variants[0] if variants else company_name
        
        try:
            # Step A: Search for actual title
            s_params = {"action": "query", "list": "search", "srsearch": search_query, "format": "json", "srlimit": 1}
            s_resp = requests.get(self.WIKIPEDIA_API_URL, params=s_params, headers={"User-Agent": self.USER_AGENT}, timeout=5)
            if s_resp.status_code != 200: return None
            
            s_results = s_resp.json().get("query", {}).get("search", [])
            best_title = s_results[0]["title"] if s_results else search_query
            
            # Step B: Get summary
            resp = requests.get(f"{self.WIKIPEDIA_SUMMARY_URL}/{best_title.replace(' ', '_')}", headers={"User-Agent": self.USER_AGENT}, timeout=5)
            if resp.status_code != 200: return None
            wiki_text = resp.json().get("extract", "")
            if not wiki_text: return None
            
            # Step C: Try Regex first (Fast)
            founders = self._regex_founder_fallback(wiki_text)
            
            # Step D: Use LLM to complement (if regex found nothing or few things)
            if self.llm_service:
                prompt = f"""Extract the current CEO and original founders for {company_name} from this Wikipedia summary:
                \"{wiki_text[:1500]}\"
                
                Respond in JSON: {{"founders": [], "currentCEO": "", "currentChairman": "", "isFounderCEO": bool, "isFounderChairman": bool}}
                """
                try:
                    res = self.llm_service.analyze_raw(prompt)
                    if res and isinstance(res, dict) and res.get("founders"):
                        res["source"] = "wikipedia+llm"
                        return res
                except: pass
            
            # Final Regex fallback if LLM failed
            if founders:
                return {"founders": founders, "currentCEO": "Extracted", "currentChairman": "", "isFounderCEO": False, "isFounderChairman": False, "source": "wikipedia+regex"}
        except: pass
        return None

    def _try_llm_only(self, ticker: str, company_name: str) -> Optional[Dict]:
        """Use the model's internal pre-trained knowledge as the final source of truth."""
        if not self.llm_service: return None
        prompt = f"""Use your internal knowledge to provide data for the S&P 500 company: {company_name} (Ticker: {ticker}).
        1. List all original founders.
        2. Identify the current CEO (as of 2024/2025).
        3. Identify the current Chairman of the Board.
        4. Check if any founder is still the current CEO or Chairman.
        
        Respond in strict JSON:
        {{
            "founders": ["Name 1", "Name 2"],
            "currentCEO": "Current Individual Name",
            "currentChairman": "Current Individual Name",
            "isFounderCEO": true/false,
            "isFounderChairman": true/false
        }}"""
        try:
            res = self.llm_service.analyze_raw(prompt)
            if res and isinstance(res, dict):
                res["source"] = "llm_only"
                return res
        except: pass
        return None

    # ─────────────────────────────────────────────
    # SCORING & HELPERS
    # ─────────────────────────────────────────────

    def _get_influence(self, result: Dict) -> Tuple[str, int]:
        if result.get("isFounderCEO") and result.get("isFounderChairman"): return "high", 15
        if result.get("isFounderCEO"): return "high", 10
        if result.get("isFounderChairman"): return "medium", 5
        return "none", 0

    def _calculate_score(self, result: Dict) -> Dict:
        infl, bonus = self._get_influence(result)
        result["founderInfluence"] = infl
        result["founderBonus"] = bonus
        if infl == "high": result["details"] = f"Founder {result.get('currentCEO','')} is CEO"
        elif infl == "medium": result["details"] = f"Founder {result.get('currentChairman','')} is Chairman"
        else: result["details"] = "Non-founder led"
        return result

    def _is_latin(self, text: str) -> bool:
        if not text or (text.startswith("Q") and text[1:].isdigit()): return False
        latin = sum(1 for c in text if ord(c) < 0x0250 or c in " .-'")
        return latin / len(text) > 0.7

    def _normalize_name(self, name: str) -> str:
        return name.strip().lower() if name else ""

    def _empty_result(self) -> Dict:
        return {"isFounderCEO": False, "isFounderChairman": False, "founderInfluence": "none", "founders": [], "currentCEO": "", "currentChairman": "", "founderBonus": 0, "source": "none", "details": "Unknown"}

def batch_update_founder_status(sp500_dict: Dict[str, str], llm_service=None) -> Dict[str, Dict]:
    service = FounderService(llm_service)
    results = {}
    for i, (ticker, sector_desc) in enumerate(sp500_dict.items()):
        name = sector_desc.split(" - ")[0].strip()
        try:
            results[ticker] = service.get_founder_status(ticker, name)
        except:
            results[ticker] = service._empty_result()
        time.sleep(0.4)
    return results

if __name__ == "__main__":
    service = FounderService()
    for t, n in [("AMZN", "Amazon"), ("META", "Meta"), ("NVDA", "NVIDIA")]:
        print(service.get_founder_status(t, n))
