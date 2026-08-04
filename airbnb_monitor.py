#!/usr/bin/env python3
"""
Airbnb Monitor - Orlando 2027
Busca casas para 2 semanas:
Semana 1: 15/02/2027 a 22/02/2027 (7 noites, 5 adultos)
Semana 2: 22/02/2027 a 27/02/2027 (5 noites, 7 adultos)
Corrige a captura do preço (Total / noites = preço por noite real) e links formatados do Airbnb.
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
            "https://www.airbnb.com.br/s/Orlando--FL--Estados-Unidos/homes"
            "?checkin=2027-02-15&checkout=2027-02-22"
            "&adults=5&children=0&infants=0&pets=0"
            "&room_types%5B%5D=Entire+home%2Fapt"
            "&min_bedrooms=3"
            "&search_type=filter_change"
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
            "https://www.airbnb.com.br/s/Orlando--FL--Estados-Unidos/homes"
            "?checkin=2027-02-22&checkout=2027-02-27"
            "&adults=7&children=0&infants=0&pets=0"
            "&room_types%5B%5D=Entire+home%2Fapt"
            "&min_bedrooms=4"
            "&search_type=filter_change"
        ),
    },
]

TIMEOUT          = 25
PRECO_MIN_BRL    = 250   # Preço diário mínimo aceitável
PRECO_MAX_BRL    = 3500  # Preço diário máximo aceitável

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

def extrair_valores_card(texto, noites):
    """
    Analisa o texto do card para diferenciar 'Total da Estadia' de 'Preço por Noite'.
    O Airbnb exibe textos como:
    - 'R$ 3.317 no total' (onde 3317 é o valor total de 7 noites => R$ 473/noite)
    - 'R$ 450 por noite'
    """
    texto_clean = texto.replace("\xa0", " ")
    
    # 1. Procurar por "R$ X.XXX total" ou "R$ X.XXX no total"
    m_total = re.search(r"R\$\s*([\d]{1,3}(?:[.,][\d]{3})*)\s*(?:total|no total)", texto_clean, re.IGNORECASE)
    if m_total:
        val_total = int(m_total.group(1).replace(".", "").replace(",", ""))
        preco_noite = int(val_total / noites)
        if PRECO_MIN_BRL <= preco_noite <= PRECO_MAX_BRL:
            return preco_noite, val_total

    # 2. Procurar por "R$ XXX por noite"
    m_noite = re.search(r"R\$\s*([\d]{1,3}(?:[.,][\d]{3})*)\s*(?:por noite|/\s*noite)", texto_clean, re.IGNORECASE)
    if m_noite:
        preco_noite = int(m_noite.group(1).replace(".", "").replace(",", ""))
        if PRECO_MIN_BRL <= preco_noite <= PRECO_MAX_BRL:
            return preco_noite, preco_noite * noites

    # 3. Se houver apenas um valor genérico "R$ X.XXX"
    m_gen = re.findall(r"R\$\s*([\d]{1,3}(?:[.,][\d]{3})*)", texto_clean)
    if m_gen:
        val = int(m_gen[0].replace(".", "").replace(",", ""))
        # Se for um valor alto (> R$ 2000), assume que é o total da estadia
        if val > (PRECO_MAX_BRL * 1.2):
            preco_noite = int(val / noites)
            if PRECO_MIN_BRL <= preco_noite <= PRECO_MAX_BRL:
                return preco_noite, val
        elif PRECO_MIN_BRL <= val <= PRECO_MAX_BRL:
            return val, val * noites

    return None, None

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

        # Rolar a tela em etapas para disparar o lazy load de imóveis
        for _ in range(3):
            driver.execute_script("window.scrollBy(0, 800);")
            time.sleep(2)

        cards = driver.find_elements(By.CSS_SELECTOR, "div[data-testid='card-container']")
        if not cards:
            cards = driver.find_elements(By.CSS_SELECTOR, "div.c4mnd7m")

        destaques = []
        precos_todos = []

        for card in cards:
            texto = card.text
            preco_noite, preco_total = extrair_valores_card(texto, busca["noites"])
            if not preco_noite:
                continue

            precos_todos.append(preco_noite)

            # Extração e formatação correta do link do imóvel com datas
            link = ""
            try:
                a_tag = card.find_element(By.CSS_SELECTOR, "a[href*='/rooms/']")
                href = a_tag.get_attribute("href")
                if href:
                    clean_id = re.search(r"/rooms/(\d+)", href)
                    if clean_id:
                        room_id = clean_id.group(1)
                        link = f"https://www.airbnb.com.br/rooms/{room_id}?check_in={busca['checkin']}&check_out={busca['checkout']}&adults={busca['adultos']}"
                    else:
                        link = href
            except:
                pass

            # Extração de Título Limpo
            linhas = [l.strip() for l in texto.split("\n") if l.strip()]
            titulo = "Casa em Orlando"
            for l in linhas:
                if re.search(r"de\s+\d+.*a.*\d+", l, re.IGNORECASE) or re.search(r"^\d+.*–.*\d+", l) or "de fev" in l.lower() or "de mar" in l.lower():
                    continue
                if any(kw in l.lower() for kw in ["casa", "villa", "quarto", "condomínio", "resort", "em orlando", "kissimmee", "davenport", "apartamento", "townhouse"]):
                    titulo = l
                    break
                elif len(l) > 6 and not "R$" in l and not "★" in l and not "Avaliação" in l and not "Preferido" in l and not "Superhost" in l:
                    titulo = l
                    break

            # Extração da nota/avaliação
            avaliacao = "Sem nota"
            m_nota = re.search(r"(★\s*[\d,.]+.*?\(.*?\))|(★\s*[\d,.]+)|([\d,.]{3,4}\s*\(\d+\))", texto)
            if m_nota:
                avaliacao = m_nota.group(0).strip()
            elif "Novo" in texto or "New" in texto:
                avaliacao = "Novo no Airbnb"

            # Detalhes do imóvel
            detalhes = ""
            m_det = re.search(r"(\d+\s*quarto[s]?.*|\d+\s*cama[s]?.*|\d+\s*banheiro[s]?)", texto, re.IGNORECASE)
            if m_det:
                detalhes = m_det.group(0).strip()

            if link and preco_noite:
                destaques.append({
                    "titulo": titulo,
                    "preco_noite": preco_noite,
                    "preco_total": preco_total,
                    "avaliacao": avaliacao,
                    "detalhes": detalhes,
                    "link": link
                })

        precos_todos = sorted(set(precos_todos))
        
        # Deduplicar e ordenar imóveis
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
            resultado["destaques"]       = destaques_unicos[:12]  # Retorna até 12 melhores opções
            resultado["minimo"]          = precos_todos[0]
            resultado["maximo"]          = precos_todos[-1]
            resultado["media"]           = int(statistics.mean(precos_todos))
            resultado["mediana"]         = int(statistics.median(precos_todos))
            resultado["total_listagens"] = n
            resultado["status"]          = "ok"
            print(f"  ✅ {n} preços por noite | {len(destaques_unicos)} casas capturadas | Min: R${precos_todos[0]:,}/noite")
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
    print("🏠 AIRBNB MONITOR - ORLANDO 2027 (PREÇO POR NOITE FIX)")
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
