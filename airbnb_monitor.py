#!/usr/bin/env python3
"""
Airbnb Monitor - Orlando 2027
Busca casas para 2 semanas: semana 1 (5 pessoas) e semana 2 (7 pessoas)
Salva historico em data/airbnb_historico.json
"""
import time, json, datetime, os, re
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

DATA_FILE = os.path.join(os.path.dirname(__file__), "data", "airbnb_historico.json")

# === CONFIGURACAO DAS BUSCAS ===
BUSCAS = [
    {
        "id": "semana1_5pax",
        "label": "Semana 1 - 5 pessoas",
        "emoji": "🏠",
        "checkin":  "2027-02-15",
        "checkout": "2027-02-22",
        "adultos": 5,
        "url": (
            "https://www.airbnb.com.br/s/Orlando--Florida--Estados-Unidos/homes"
            "?checkin=2027-02-15&checkout=2027-02-22"
            "&adults=5&children=0&infants=0&pets=0"
            "&room_types%5B%5D=Entire+home%2Fapt"
            "&min_bedrooms=3"
            "&price_min=100&price_max=600"
            "&sort=PRICE_RATE_ASC"
        )
    },
    {
        "id": "semana2_7pax",
        "label": "Semana 2 - 7 pessoas",
        "emoji": "🏡",
        "checkin":  "2027-02-22",
        "checkout": "2027-02-27",
        "adultos": 7,
        "url": (
            "https://www.airbnb.com.br/s/Orlando--Florida--Estados-Unidos/homes"
            "?checkin=2027-02-22&checkout=2027-02-27"
            "&adults=7&children=0&infants=0&pets=0"
            "&room_types%5B%5D=Entire+home%2Fapt"
            "&min_bedrooms=4"
            "&price_min=100&price_max=700"
            "&sort=PRICE_RATE_ASC"
        )
    },
]

TIMEOUT = 20  # segundos aguardando a pagina carregar

def criar_driver():
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--lang=pt-BR,pt")
    options.add_argument(
        "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    driver = webdriver.Chrome(options=options)
    driver.execute_script("Object.defineProperty(navigator,'webdriver',{get:()=>undefined})")
    return driver

def extrair_preco_brl(texto):
    """Extrai preco em BRL do texto do card."""
    # Tenta "R$ X.XXX por noite" ou "R$ X.XXX / noite"
    match = re.search(r"R\$\s?([\d]{1,3}(?:[.,][\d]{3})*)", texto)
    if match:
        valor_str = match.group(1).replace(".", "").replace(",", "")
        try:
            valor = int(valor_str)
            if 100 <= valor <= 5000:
                return valor
        except:
            pass
    return None

def buscar_airbnb(busca):
    """Faz o scraping de uma busca e retorna lista de precos encontrados."""
    driver = criar_driver()
    resultado = {
        "id": busca["id"],
        "label": busca["label"],
        "adultos": busca["adultos"],
        "checkin": busca["checkin"],
        "checkout": busca["checkout"],
        "precos": [],
        "minimo": None,
        "mediana": None,
        "media": None,
        "maximo": None,
        "total_listagens": 0,
        "status": "erro"
    }

    try:
        print(f"\n{busca['emoji']} [{busca['label']}] Abrindo Airbnb...")
        driver.get(busca["url"])
        print(f"  ⏳ Aguardando {TIMEOUT}s para carregar...")
        time.sleep(TIMEOUT)

        # Seletores possiveis para cards de preco
        seletores = [
            "span._tyxjp1",       # preco por noite (formato atual)
            "span.a8jt5op",       # preco alternativo
            "div._1jo4hgw",       # wrapper de preco
            "span[data-testid='price-and-discounted-price']",
        ]

        precos_encontrados = []
        for seletor in seletores:
            elementos = driver.find_elements(By.CSS_SELECTOR, seletor)
            for el in elementos:
                texto = el.text.strip()
                preco = extrair_preco_brl(texto)
                if preco:
                    precos_encontrados.append(preco)
            if precos_encontrados:
                break

        # Fallback: pega texto de todos os cards e extrai precos
        if not precos_encontrados:
            print("  🔄 Tentando fallback geral...")
            cards = driver.find_elements(By.CSS_SELECTOR, "div[data-testid='card-container']")
            if not cards:
                cards = driver.find_elements(By.CSS_SELECTOR, "div.c4mnd7m")
            for card in cards:
                preco = extrair_preco_brl(card.text)
                if preco:
                    precos_encontrados.append(preco)

        if precos_encontrados:
            precos_ordenados = sorted(set(precos_encontrados))
            n = len(precos_ordenados)
            resultado["precos"] = precos_ordenados[:20]  # salva ate 20 precos
            resultado["minimo"] = precos_ordenados[0]
            resultado["maximo"] = precos_ordenados[-1]
            resultado["media"] = int(sum(precos_ordenados) / n)
            resultado["mediana"] = precos_ordenados[n // 2]
            resultado["total_listagens"] = n
            resultado["status"] = "ok"
            print(f"  ✅ {n} precos encontrados | Min: R${resultado['minimo']} | Med: R${resultado['mediana']} | Max: R${resultado['maximo']}")
        else:
            resultado["status"] = "sem_dados"
            print(f"  ⚠️  Nenhum preco extraido.")

    except Exception as e:
        resultado["erro"] = str(e)
        print(f"  ❌ Erro: {e}")
    finally:
        driver.quit()

    return resultado

def salvar_historico(registros):
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
    historico = []
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                historico = json.load(f)
        except:
            pass
    historico.append(registros)
    historico = historico[-500:]
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(historico, f, indent=2, ensure_ascii=False)
    print(f"\n📝 Historico salvo: {len(historico)} registros em {DATA_FILE}")

if __name__ == "__main__":
    print("=" * 55)
    print("🏠 AIRBNB MONITOR - ORLANDO 2027")
    print("=" * 55)

    timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
    resultados_buscas = []

    for busca in BUSCAS:
        res = buscar_airbnb(busca)
        resultados_buscas.append(res)
        time.sleep(5)  # pausa entre buscas para nao ser bloqueado

    registro = {
        "timestamp": timestamp,
        "buscas": resultados_buscas,
        "status": "ok" if any(r["status"] == "ok" for r in resultados_buscas) else "erro"
    }

    print("\n" + "=" * 55)
    print(json.dumps(registro, indent=2, ensure_ascii=False))

    if registro["status"] == "ok":
        salvar_historico(registro)
    else:
        print("\n⚠️  Nenhum dado coletado. Historico nao modificado.")
