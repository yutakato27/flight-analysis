#!/usr/bin/env python3
import time, json, datetime, sys, os, re
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By

LOG_FILE        = os.path.join(os.path.dirname(__file__), "data", "historico.json")
TIMEOUT_KAYAK   = 30
NUM_ADULTOS     = 2

URL_KAYAK = (
    "https://www.kayak.com.br/flights/CWB-MCO/2027-02-15/2027-02-27/"
    "2adults?sort=price_a&fs=stops=~1"
)

def criar_driver():
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--lang=pt-BR,pt")
    options.add_argument(
        "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    driver = webdriver.Chrome(options=options)
    driver.execute_script("Object.defineProperty(navigator,'webdriver',{get:()=>undefined})")
    return driver

def extrair_precos_kayak(texto):
    padrao = r'R\$\s?([\d]{1,3}(?:\.\d{3})*)'
    matches = re.findall(padrao, texto)
    precos_pessoa = []
    for m in matches:
        limpo = m.replace(".", "")
        try:
            v = int(limpo)
            if 2_000 <= v <= 15_000:
                precos_pessoa.append(v)
        except Exception:
            pass
    precos_pessoa = sorted(set(precos_pessoa))
    totais_casal = [p * NUM_ADULTOS for p in precos_pessoa]
    return precos_pessoa, totais_casal

def buscar_kayak():
    driver = criar_driver()
    resultado = {
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "preco_minimo_pessoa": None,
        "preco_minimo_casal": None,
        "detalhes_voo": None,
        "status": "erro",
    }
    try:
        print(f"🌐 Abrindo Kayak...")
        driver.get(URL_KAYAK)
        print(f"⏳ Aguardando {TIMEOUT_KAYAK}s...")
        time.sleep(TIMEOUT_KAYAK)
        
        # Tenta pegar os cards de voos
        cards = driver.find_elements(By.CSS_SELECTOR, "div.nrc6-wrapper")
        if not cards:
            cards = driver.find_elements(By.CSS_SELECTOR, "div.inner-wrapper")
            
        if cards:
            # Pega detalhes do primeiro card (que é o mais barato devido ao sort=price_a)
            primeiro_card_texto = cards[0].text
            linhas_card = [l for l in primeiro_card_texto.split('\n') if l.strip()]
            
            # Tenta encontrar a cia aérea e as horas usando regex básica ou pegando o texto
            resultado["detalhes_voo"] = " | ".join(linhas_card[:10]) # Salva as primeiras linhas como resumo (horarios, cia, escalas)
            
        body = driver.find_element(By.TAG_NAME, "body").text
        precos_pessoa, totais_casal = extrair_precos_kayak(body)
        
        if totais_casal:
            resultado.update({
                "preco_minimo_pessoa": min(precos_pessoa),
                "preco_minimo_casal":  min(precos_pessoa) * NUM_ADULTOS,
                "status": "ok",
            })
        else:
            resultado["status"] = "sem_preco"
    except Exception as e:
        resultado["erro"] = str(e)
        print(f"❌ Erro: {e}")
    finally:
        driver.quit()
    return resultado

def salvar_historico(r):
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    hist = []
    if os.path.exists(LOG_FILE):
        try:
            with open(LOG_FILE, "r") as f:
                hist = json.load(f)
        except Exception:
            pass
    hist.append(r)
    hist = hist[-500:] # Manter ultimos 500
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(hist, f, indent=2, ensure_ascii=False)
    print(f"📝 Histórico salvo com {len(hist)} registros.")

if __name__ == "__main__":
    print("Iniciando coleta...")
    r = buscar_kayak()
    print(json.dumps(r, indent=2, ensure_ascii=False))
    if r.get("preco_minimo_casal"):
        salvar_historico(r)
    else:
        print("Nenhum preço encontrado. Histórico não modificado.")
