from utils import isin_from_gemini

url = "https://www.fundslibrary.co.uk/FundsLibrary.DataRetrieval/Documents.aspx?type=packet_fund_unit_doc_kiid&docid=acdfa15e-3039-4cee-b646-4f1dfbd80d07&user=UOtATk2mJxvE8sviWIecLUXslUfWQxDzkL0VxE2QgKM%3d"
isin = isin_from_gemini(url)

print(isin)
