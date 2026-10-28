import sys
sys.stdout.reconfigure(encoding='utf-8')

with open('gemini_extractor.py', 'r', encoding='utf-8') as f:
    code = f.read()

# Let's inspect the exact lines around extract_co_data_from_files
pos1 = code.find('def extract_co_data_from_files(')
pos2 = code.find('CO_ADVISOR_SYSTEM_PROMPT =')

print("extract_co_data_from_files start:", pos1, "end:", pos2)

pos3 = code.find('def ask_co_advisor(')
print("ask_co_advisor start:", pos3)
