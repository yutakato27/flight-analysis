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
options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
driver = webdriver.Chrome(service=Service("/usr/lib/chromium-browser/chromedriver"), options=options)

url = "https://www.kayak.com.br/flights/CWB-MCO/2027-02-15/2027-02-27/2adults?sort=price_a&fs=stops=~1"
driver.get(url)
time.sleep(20)

cards = driver.find_elements(By.CSS_SELECTOR, "div.nrc6-wrapper")
if not cards:
    cards = driver.find_elements(By.CSS_SELECTOR, "div.inner-wrapper")

if cards:
    links = cards[0].find_elements(By.TAG_NAME, "a")
    print(f"Encontrados {len(links)} links no card.")
    for a in links:
        href = a.get_attribute('href')
        if href and ('/book/' in href or 'flights' in href):
            print("Link:", href)
driver.quit()
