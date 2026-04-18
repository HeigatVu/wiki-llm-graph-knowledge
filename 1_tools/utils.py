import os
import requests
import sys

from dotenv import load_dotenv
load_dotenv()

import google.generativeai as genai
import time

def _call_ollama(prompt: str, max_tokens: int) -> str:
    model = os.getenv("OLLAMA_MODEL", "llama3.2")
    try:
        response = requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {"num_predict": max_tokens}
            },
            timeout=120
        )
        response.raise_for_status()
        return response.json()["response"]
    except requests.exceptions.ConnectionError:
        print("Error: Ollama is not running. Start it with: ollama serve")
        sys.exit(1)

def _call_gemini(prompt: str, max_tokens: int) -> str:
    """Call LLM with prompt."""
    try:
        import google.generativeai as genai
    except ImportError:
        print("Error: google-generativeai not installed. Run: pip install google-generativeai")
        sys.exit(1)
        
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("Error: GEMINI_API_KEY not set in .env file")
        sys.exit(1)

    # Sleep 5-10 seconds to avoid hitting Requests Per Minute (RPM) limits
    time.sleep(10)

    genai.configure(api_key=api_key)
    model_name = os.getenv("LLM_MODEL", "gemini-3.1-flash-preview")
    model = genai.GenerativeModel(model_name)

    response = model.generate_content(
        prompt,
        generation_config=genai.types.GenerationConfig(max_output_tokens=max_tokens)
    )

    return response.text