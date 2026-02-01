import os
import json
from openai import OpenAI
import google.generativeai as genai

# Keys to test
QWEN_KEY = "sk-e57c05f824074986884f02e008f0d951"
GEMINI_KEY = "AIzaSyBHHC3_pSCBp02dAjd5uZjjscSGYTCakfM"

def test_qwen():
    print("-" * 30)
    print("Testing Qwen API...")
    try:
        client = OpenAI(
            api_key=QWEN_KEY,
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
        )
        response = client.chat.completions.create(
            model="qwen-plus",
            messages=[{'role': 'system', 'content': 'You are a helpful assistant.'},
                      {'role': 'user', 'content': 'Say "Qwen is working"'}],
            max_tokens=20
        )
        print("✅ Qwen Success!")
        print("Response:", response.choices[0].message.content)
    except Exception as e:
        print("❌ Qwen Failed")
        print("Error:", str(e))

def test_gemini():
    print("-" * 30)
    print("Testing Gemini API...")
    try:
        genai.configure(api_key=GEMINI_KEY)
        print("Listing available models...")
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                print(f" - {m.name}")
        
    except Exception as e:
        print("❌ Gemini Failed")
        print("Error:", str(e))

if __name__ == "__main__":
    test_qwen()
    test_gemini()
