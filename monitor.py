#!/usr/bin/env python3
import time, json, datetime, sys, os, re
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By

LOG_FILE        = os.path.join(os.path.dirname(__file__), "data", "historico.json")
TIMEOUT_KAYAK   = 30
NUM_ADULTOS     = 2

# Busca 1: Menor preço geral (1 ou 2 paradas, ordenado por melhor voo)
URL_MENOR_PRECO = (
    "https://www.kayak.com.br/flights/CWB-MCO/2027-02-15/2027-02-27/"
    "2adults?sort=bestflight_a&fs=stops=1,2"
)

# Busca 2: Melhor custo-benefício (máximo 1 parada, ordenado por preço)
URL_MELHOR_ROTA = (
    "https://www.kayak.com.br/flights/CWB-MCO/2027-02-15/2027-02-27/"
    "2adults?sort=price_a&fs=stops=1"
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

def extrair_detalhes_card(card):
    """Extrai companhia, horários e duração do primeiro card de voo."""
    linhas_card = [l for l in card.text.split('\n') if l.strip()]

    cia = "—"
    for i, l in enumerate(linhas_card):
        if "R$" in l:
            if i > 0: cia = linhas_card[i-1]
            break

    horarios = [l for l in linhas_card if "–" in l and ":" in l]
    duracoes = [l for l in linhas_card if "h" in l and ("min" in l or "m" in l) and "Escala" not in l]

    ida   = f"🛫 Ida: {horarios[0]} ({duracoes[0]})"   if len(horarios)>0 and len(duracoes)>0 else ""
    volta = f"🛬 Volta: {horarios[1]} ({duracoes[1]})" if len(horarios)>1 and len(duracoes)>1 else ""

    return f"✈️ {cia} | {ida} | {volta}"

def buscar(url, label):
    """Abre a URL no Kayak e retorna os dados do primeiro resultado."""
    driver = criar_driver()
    dados = {"preco_casal": None, "detalhes_voo": None, "status": "erro"}
    try:
        print(f"🌐 [{label}] Abrindo Kayak...")
        driver.get(url)
        print(f"⏳ Aguardando {TIMEOUT_KAYAK}s...")
        time.sleep(TIMEOUT_KAYAK)

        cards = driver.find_elements(By.CSS_SELECTOR, "div.nrc6-wrapper")
        if not cards:
            cards = driver.find_elements(By.CSS_SELECTOR, "div.inner-wrapper")

        if cards:
            dados["detalhes_voo"] = extrair_detalhes_card(cards[0])

        body = driver.find_element(By.TAG_NAME, "body").text
        precos_pessoa, _ = extrair_precos_kayak(body)

        if precos_pessoa:
            dados["preco_casal"] = min(precos_pessoa) * NUM_ADULTOS
            dados["status"] = "ok"
            print(f"✅ [{label}] R$ {dados['preco_casal']:,}")
        else:
            dados["status"] = "sem_preco"
            print(f"⚠️  [{label}] Nenhum preço encontrado.")
    except Exception as e:
        dados["erro"] = str(e)
        print(f"❌ [{label}] Erro: {e}")
    finally:
        driver.quit()
    return dados

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
    hist = hist[-500:]
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(hist, f, indent=2, ensure_ascii=False)
    print(f"📝 Histórico salvo com {len(hist)} registros.")

if __name__ == "__main__":
    print("Iniciando coleta dupla...")

    menor_preco  = buscar(URL_MENOR_PRECO, "Menor Preço")
    melhor_rota  = buscar(URL_MELHOR_ROTA, "Melhor Rota (1 parada)")

    registro = {
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "menor_preco": menor_preco,
        "melhor_rota": melhor_rota,
        "status": "ok" if menor_preco["status"] == "ok" or melhor_rota["status"] == "ok" else "erro",
    }

    print(json.dumps(registro, indent=2, ensure_ascii=False))

    if registro["status"] == "ok":
        salvar_historico(registro)
    else:
        print("Nenhum preço encontrado. Histórico não modificado.")
