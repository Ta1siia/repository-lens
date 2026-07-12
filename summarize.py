import os
from google import genai
from dotenv import load_dotenv

load_dotenv()

def summarize_commits(messages):
    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    prompt = (
        "Here are recent commit messages for a file:\n"
        + "\n".join(f"- {m}" for m in messages)
        + "\n\nIn 2-3 sentences, describe clearly what has been happening in this file."
    )
    response = client.models.generate_content(
        model="gemini-3.5-flash",
        contents=prompt,
    )
    return response.text
