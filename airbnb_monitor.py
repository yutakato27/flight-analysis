#!/usr/bin/env python3
"""
Airbnb Monitor - Orlando 2027
Busca casas para 2 semanas: semana 1 (5 pessoas) e semana 2 (7 pessoas)
Extrai métricas gerais + Top Casas em Destaque (Link, Título, Preço/noite, Avaliação e Detalhes)
Salva histórico em data/airbnb_historico.json
"""
import time, json, datetime, os, re, statistics
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

DATA_FILE = os.path.join(os.path.dirname(__file__), "data", "airbnb_historico.json")

BUSCAS = [
    {
        "id":       "semana1_5pax",
        "label":    "Semana 1 - 5 pessoas",
        "emoji":    "🏠",
        "checkin":  "2027-02-15",
        "checkout": "2027-02-22",
        "adultos":  5,
        "noites":   7,
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

TIMEOUT          = 25
PRECO_MIN_BRL    = 300
PRECO_MAX_BRL    = 4000

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
    padroes = [
        r"R\$\s*([\d]{1,3}(?:[.,][\d]{3})*)\s*(?:por noite|/\s*noite|per night)",
        r"([\d]{1,3}(?:[.,][\d]{3})*)\s*(?:por noite|/\s*noite)",
    ]
    for pat in padroes:
        m = re.search(pat, texto, re.IGNORECASE)
        if m:
            val = int(m.group(1).replace(".", "").replace(",", ""))
            if PRECO_MIN_BRL <= val <= PRECO_MAX_BRL:
                return val

    for m in re.finditer(r"R\$\s*([\d]{1,3}(?:[.,][\d]{3})*)", texto):
        val = int(m.group(1).replace(".", "").replace(",", ""))
        if PRECO_MIN_BRL <= val <= PRECO_MAX_BRL:
            return val
    return None

def buscar_airbnb(busca):
    driver = criar_driver()
    resultado = {
        "id":               busca["id"],
        "label":            busca["label"],
        "adultos":          busca["adultos"],
        "noites":           busca["noites"],
        "checkin":          busca["checkin"],
        "checkout":         busca["checkout"],
        "precos":           [],
        "destaques":        [],
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

        # Rolar pagina para carregar mais elementos
        driver.execute_script("window.scrollBy(0, 1000);")
        time.sleep(3)

        cards = driver.find_elements(By.CSS_SELECTOR, "div[data-testid='card-container']")
        if not cards:
            cards = driver.find_elements(By.CSS_SELECTOR, "div.c4mnd7m")

        destaques = []
        precos_todos = []

        for card in cards:
            texto = card.text
            preco = extrair_preco_noite(texto)
            if not preco:
                continue

            precos_todos.append(preco)

            # Tentar extrair link
            link = ""
            try:
                a_tag = card.find_element(By.CSS_SELECTOR, "a[href*='/rooms/']")
                href = a_tag.get_attribute("href")
                if href:
                    clean_id = re.search(r"/rooms/(\d+)", href)
                    if clean_id:
                        link = f"https://www.airbnb.com.br/rooms/{clean_id.group(1)}?check_in={busca['checkin']}&check_out={busca['checkout']}&adults={busca['adultos']}"
                    else:
                        link = href
            except:
                pass

            # Extrair titulo / descricao
            linhas = [l.strip() for l in texto.split("\n") if l.strip()]
            titulo = "Casa em Orlando"
            for l in linhas:
                if any(kw in l.lower() for kw in ["casa", "villa", "quarto", "condomínio", "resort", "em orlando", "kissimmee", "davenport"]):
                    titulo = l
                    break
                elif len(l) > 10 and not "R$" in l and not "★" in l and not "Avaliação" in l:
                    titulo = l
                    break

            # Extrair avaliação e nota
            avaliacao = "Sem nota"
            m_nota = re.search(r"(★\s*[\d,.]+)|([\d,.]{3,4}\s*\(\d+\))|([\d,.]{3,4}\s*·)", texto)
            if m_nota:
                avaliacao = m_nota.group(0).strip()
            elif "Novo" in texto or "New" in texto:
                avaliacao = "Novo no Airbnb"

            # Detalhes (ex: 4 quartos, 5 camas)
            detalhes = ""
            m_det = re.search(r"(\d+\s*quarto[s]?.*|\d+\s*cama[s]?.*|\d+\s*banheiro[s]?)", texto, re.IGNORECASE)
            if m_det:
                detalhes = m_det.group(0).strip()

            if link and preco:
                destaques.append({
                    "titulo": titulo,
                    "preco_noite": preco,
                    "preco_total": preco * busca["noites"],
                    "avaliacao": avaliacao,
                    "detalhes": detalhes,
                    "link": link
                })

        precos_todos = sorted(set(precos_todos))
        
        # Ordenar destaques por nota / melhor preço
        # Remover duplicados de link
        vistos = set()
        destaques_unicos = []
        for d in destaques:
            if d["link"] not in vistos:
                vistos.add(d["link"])
                destaques_unicos.append(d)
        
        destaques_unicos.sort(key=lambda x: x["preco_noite"])

        if precos_todos:
            n = len(precos_todos)
            resultado["precos"]          = precos_todos[:30]
            resultado["destaques"]       = destaques_unicos[:6] # guarda os 6 melhores destaques
            resultado["minimo"]          = precos_todos[0]
            resultado["maximo"]          = precos_todos[-1]
            resultado["media"]           = int(statistics.mean(precos_todos))
            resultado["mediana"]         = int(statistics.median(precos_todos))
            resultado["total_listagens"] = n
            resultado["status"]          = "ok"
            print(f"  ✅ {n} preços | {len(destaques_unicos)} casas com link extraídas | Min: R${precos_todos[0]:,}")
        else:
            resultado["status"] = "sem_dados"

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
    print(f"\n📝 Histórico atualizado: {len(historico)} registros")

if __name__ == "__main__":
    print("=" * 55)
    print("🏠 AIRBNB MONITOR - ORLANDO 2027")
    print("=" * 55)

    timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
    resultados = []

    for busca in BUSCAS:
        res = buscar_airbnb(busca)
        resultados.append(res)
        time.sleep(5)

    registro = {
        "timestamp": timestamp,
        "buscas":    resultados,
        "status":    "ok" if any(r["status"] == "ok" for r in resultados) else "erro",
    }

    if registro["status"] == "ok":
        salvar_historico(registro)
