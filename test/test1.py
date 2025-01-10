import google.generativeai as genai

genai.configure(api_key="AIzaSyBB3wF0sqPCYfqxsjsJrtTABdi3dLkfnlw")

model = genai.GenerativeModel("gemini-2.0-flash-exp")
response = model.generate_content("ロシアの首都は？")
print(response.text)