from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
import time

options = Options()
options.add_argument("--headless=new")
options.add_argument("--no-sandbox")
options.add_argument("--window-size=1920,1080")
options.add_argument("--disable-blink-features=AutomationControlled")
options.add_argument("--lang=pt-BR,pt")
options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
driver = webdriver.Chrome(service=Service("/usr/lib/chromium-browser/chromedriver"), options=options)

url = "https://www.kayak.com.br/flights/CWB-MCO/2027-02-15/2027-02-27/2adults?sort=price_a&fs=stops=~1"
driver.get(url)
time.sleep(25)

# Try to find the flight result blocks
elements = driver.find_elements(By.CSS_SELECTOR, "div.nrc6-wrapper")
if not elements:
    elements = driver.find_elements(By.CSS_SELECTOR, "div.inner-wrapper")

print(f"Found {len(elements)} results")
if elements:
    print("--- FIRST RESULT ---")
    print(elements[0].text)

driver.quit()
