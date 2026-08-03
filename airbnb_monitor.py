#!/usr/bin/env python3
"""
Airbnb Monitor - Orlando 2027
Busca casas para 2 semanas: semana 1 (5 pessoas) e semana 2 (7 pessoas)
Salva historico em data/airbnb_historico.json
"""
import time, json, datetime, os, re, statistics
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

DATA_FILE = os.path.join(os.path.dirname(__file__), "data", "airbnb_historico.json")
DEBUG     = True   # salva HTML para inspecionar se algo der errado

# ======================================================
# CONFIGURACAO DAS BUSCAS
# Precos no Airbnb.com.br sao em BRL por noite
# Faixa esperada para casa em Orlando: R$ 400 a R$ 2.500/noite
# ======================================================
BUSCAS = [
    {
        "id":       "semana1_5pax",
        "label":    "Semana 1 - 5 pessoas",
        "emoji":    "🏠",
        "checkin":  "2027-02-15",
        "checkout": "2027-02-22",
        "adultos":  5,
        "noites":   7,
        # price_min/max em USD no filtro da URL (~R$400=~$72, ~R$2500=~$454)
        "url": (
            "https://www.airbnb.com.br/s/Orlando--Florida--Estados-Unidos/homes"
            "?checkin=2027-02-15&checkout=2027-02-22"
            "&adults=5&children=0&infants=0&pets=0"
            "&room_types%5B%5D=Entire+home%2Fapt"
            "&min_bedrooms=3"
            "&sort=PRICE_RATE_ASC"
        ),
    },
    {
        "id":       "semana2_7pax",
        "label":    "Semana 2 - 7 pessoas",
        "emoji":    "🏡",
        "checkin":  "2027-02-22",
        "checkout": "2027-02-27",
        "adultos":  7,
        "noites":   5,
        "url": (
            "https://www.airbnb.com.br/s/Orlando--Florida--Estados-Unidos/homes"
            "?checkin=2027-02-22&checkout=2027-02-27"
            "&adults=7&children=0&infants=0&pets=0"
            "&room_types%5B%5D=Entire+home%2Fapt"
            "&min_bedrooms=4"
            "&sort=PRICE_RATE_ASC"
        ),
    },
]

TIMEOUT          = 25   # segundos aguardando a pagina carregar
PRECO_MIN_BRL    = 300  # preco minimo plausivel por NOITE em BRL (~$55)
PRECO_MAX_BRL    = 4000 # preco maximo plausivel por NOITE em BRL (~$727)


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


def extrair_preco_noite(texto):
    """
    Extrai o preco POR NOITE do texto de um card do Airbnb.
    O Airbnb exibe algo como 'R$ 1.234 por noite' ou 'R$1.234 / noite'.
    Retorna int em BRL ou None.
    """
    # Padrão: R$ X.XXX por noite  /  R$X.XXX/noite  /  R$ X.XXX night
    padroes_noite = [
        r"R\$\s*([\d]{1,3}(?:[.,][\d]{3})*)\s*(?:por noite|/\s*noite|per night)",
        r"([\d]{1,3}(?:[.,][\d]{3})*)\s*(?:por noite|/\s*noite)",
    ]
    for pat in padroes_noite:
        m = re.search(pat, texto, re.IGNORECASE)
        if m:
            val = int(m.group(1).replace(".", "").replace(",", ""))
            if PRECO_MIN_BRL <= val <= PRECO_MAX_BRL:
                return val

    # Fallback generico: qualquer "R$ X.XXX" no intervalo plausivel
    for m in re.finditer(r"R\$\s*([\d]{1,3}(?:[.,][\d]{3})*)", texto):
        val = int(m.group(1).replace(".", "").replace(",", ""))
        if PRECO_MIN_BRL <= val <= PRECO_MAX_BRL:
            return val

    return None


def buscar_airbnb(busca):
    """Faz o scraping de uma busca e retorna estatísticas de precos."""
    driver = criar_driver()
    resultado = {
        "id":               busca["id"],
        "label":            busca["label"],
        "adultos":          busca["adultos"],
        "noites":           busca["noites"],
        "checkin":          busca["checkin"],
        "checkout":         busca["checkout"],
        "precos":           [],
        "minimo":           None,
        "mediana":          None,
        "media":            None,
        "maximo":           None,
        "total_listagens":  0,
        "status":           "erro",
    }

    try:
        print(f"\n{busca['emoji']} [{busca['label']}] Abrindo Airbnb...")
        driver.get(busca["url"])
        print(f"  ⏳ Aguardando {TIMEOUT}s...")
        time.sleep(TIMEOUT)

        # ---- Salvar HTML para debug ----
        if DEBUG:
            html_path = os.path.join(
                os.path.dirname(__file__), "data",
                f"debug_{busca['id']}.html"
            )
            with open(html_path, "w", encoding="utf-8") as f:
                f.write(driver.page_source)
            print(f"  💾 HTML salvo em {html_path}")

        # ---- Estrategia 1: aria-label nos cards (mais confiavel) ----
        precos = []
        els = driver.find_elements(By.CSS_SELECTOR, "[aria-label]")
        for el in els:
            label = el.get_attribute("aria-label") or ""
            if "R$" in label or "por noite" in label.lower():
                p = extrair_preco_noite(label)
                if p:
                    precos.append(p)

        # ---- Estrategia 2: spans de preco ----
        if len(precos) < 3:
            seletores = [
                "span._tyxjp1",
                "span[data-testid='price-and-discounted-price']",
                "div._1jo4hgw span",
                "span.a8jt5op",
            ]
            for sel in seletores:
                for el in driver.find_elements(By.CSS_SELECTOR, sel):
                    p = extrair_preco_noite(el.text)
                    if p:
                        precos.append(p)
                if len(precos) >= 3:
                    break

        # ---- Estrategia 3: texto completo dos cards ----
        if len(precos) < 3:
            print("  🔄 Fallback: lendo cards completos...")
            card_sels = [
                "div[data-testid='card-container']",
                "div[itemprop='itemListElement']",
                "div.c4mnd7m",
                "div[class*='g1tup9az']",
            ]
            for sel in card_sels:
                cards = driver.find_elements(By.CSS_SELECTOR, sel)
                for card in cards:
                    p = extrair_preco_noite(card.text)
                    if p:
                        precos.append(p)
                if len(precos) >= 3:
                    break

        # ---- Deduplicar e ordenar ----
        precos = sorted(set(precos))

        if precos:
            n = len(precos)
            resultado["precos"]          = precos[:30]
            resultado["minimo"]          = precos[0]
            resultado["maximo"]          = precos[-1]
            resultado["media"]           = int(statistics.mean(precos))
            resultado["mediana"]         = int(statistics.median(precos))
            resultado["total_listagens"] = n
            resultado["status"]          = "ok"
            print(f"  ✅ {n} precos | Min: R${precos[0]:,} | Med: R${resultado['mediana']:,} | Max: R${precos[-1]:,}")
        else:
            resultado["status"] = "sem_dados"
            print("  ⚠️  Nenhum preco extraido — verifique o HTML de debug")

    except Exception as e:
        resultado["erro"] = str(e)
        print(f"  ❌ Erro: {e}")
    finally:
        driver.quit()

    return resultado


def salvar_historico(registro):
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
    historico = []
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                historico = json.load(f)
        except Exception:
            pass
    historico.append(registro)
    historico = historico[-500:]
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(historico, f, indent=2, ensure_ascii=False)
    print(f"\n📝 Historico salvo: {len(historico)} registros")


if __name__ == "__main__":
    print("=" * 55)
    print("🏠 AIRBNB MONITOR - ORLANDO 2027")
    print("=" * 55)

    timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
    resultados = []

    for busca in BUSCAS:
        res = buscar_airbnb(busca)
        resultados.append(res)
        time.sleep(8)   # pausa entre buscas

    registro = {
        "timestamp": timestamp,
        "buscas":    resultados,
        "status":    "ok" if any(r["status"] == "ok" for r in resultados) else "erro",
    }

    print("\n" + "=" * 55)
    print(json.dumps(registro, indent=2, ensure_ascii=False))

    if registro["status"] == "ok":
        salvar_historico(registro)
    else:
        print("\n⚠️  Nenhum dado coletado. Historico nao modificado.")
        print("    Verifique os arquivos data/debug_*.html para investigar.")
