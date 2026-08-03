from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
import time

options = Options()
options.add_argument("--headless=new")
options.add_argument("--no-sandbox")
options.add_argument("--window-size=1920,1080")
options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
driver = webdriver.Chrome(service=Service("/usr/lib/chromium-browser/chromedriver"), options=options)

print("🔍 Testando Zupper...")
url = "https://www.zupper.com.br/passagens-aereas/resultados?origem=CWB&destino=MCO&dataIda=15/02/2027&dataVolta=27/02/2027&adultos=2"
driver.get(url)
time.sleep(25)
texto = driver.find_element(By.TAG_NAME, "body").text
linhas_rs = [l.strip() for l in texto.split('\n') if 'R$' in l and l.strip()]
print(f"Zupper retornou {len(linhas_rs)} linhas com R$.")
if linhas_rs:
    print(linhas_rs[:15])
driver.quit()
