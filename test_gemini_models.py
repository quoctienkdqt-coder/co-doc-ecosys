import sys
sys.stdout.reconfigure(encoding='utf-8')
from google import genai

c = genai.Client(api_key="AIzaSyDummyTestKeyForVerificationOnly12345")
try:
    resp = c.models.generate_content(model="gemini-3.8-flash", contents="hello")
    print("Response:", resp)
except Exception as e:
    print("Caught error:", type(e), e)
