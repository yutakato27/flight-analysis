#!/usr/bin/env python3
"""
Monitor de Voos: CWB -> MCO (Orlando 2027)
15/02 - 27/02/2027 | 2 adultos
Busca rota ideal: 1 parada ida + volta com duração máx 13h em cada trecho
"""
import time, json, datetime, os, re
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

LOG_FILE      = os.path.join(os.path.dirname(__file__), "data", "historico.json")
TIMEOUT_KAYAK = 30
NUM_ADULTOS   = 2

# Busca 1: Menor preço geral (1 ou 2 paradas)
URL_MENOR_PRECO = (
    "https://www.kayak.com.br/flights/CWB-MCO/2027-02-15/2027-02-27/"
    "2adults?sort=price_a&fs=stops=1,2"
)

# Busca 2: Melhor rota — percorre os cards até achar 1 parada CADA perna E volta <= 13h
URL_MELHOR_ROTA = (
    "https://www.kayak.com.br/flights/CWB-MCO/2027-02-15/2027-02-27/"
    "2adults?sort=price_a&fs=stops=1"
)

# Busca 3: Mista — 1 parada na ida, qualquer número na volta (mais barato)
# Percorre cards filtrando pelo card cuja IDA tem "1 escala"
URL_MISTA = (
    "https://www.kayak.com.br/flights/CWB-MCO/2027-02-15/2027-02-27/"
    "2adults?sort=price_a&fs=stops=1,2"
)

# Limite de duração aceitável para a volta (em horas)
MAX_HORAS_VOLTA = 13


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
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    driver = webdriver.Chrome(options=options)
    driver.execute_script("Object.defineProperty(navigator,'webdriver',{get:()=>undefined})")
    return driver


def extrair_duracoes(texto_card):
    """
    Extrai durações de ida e volta identificando linhas de duração que aparecem
    logo após linhas de horário no formato 'HH:MM – HH:MM'.
    Retorna (horas_ida, horas_volta) ou (None, None).
    """
    linhas = [l.strip() for l in texto_card.split('\n') if l.strip()]
    # Padrão de horário: "6:00 – 15:30" ou "17:20 – 15:30+1"
    padrao_horario = re.compile(r'^\d{1,2}:\d{2}\s*[–-]\s*\d{1,2}:\d{2}')
    # Padrão de duração: "11h 30min", "19h 10min", "24h", etc.
    padrao_duracao = re.compile(r'^(\d+)h\s*(\d+)?')

    duracoes = []
    for i, linha in enumerate(linhas):
        if padrao_horario.match(linha):
            # A linha de duração fica logo após a de horário
            if i + 1 < len(linhas):
                prox = linhas[i + 1]
                m = padrao_duracao.match(prox)
                if m:
                    h = int(m.group(1))
                    mins = int(m.group(2)) if m.group(2) else 0
                    total = h + mins / 60
                    if 5 <= total <= 50:   # inclui até 50h para capturar qualquer caso
                        duracoes.append(total)
    if len(duracoes) >= 2:
        return duracoes[0], duracoes[1]
    return None, None


def extrair_preco_card(texto_card):
    """Extrai o preço total do casal do card."""
    total = re.search(r'R\$\s?([\d]{1,3}(?:\.[\d]{3})*)\s*no total', texto_card)
    if total:
        preco = int(total.group(1).replace(".", ""))
        if 4_000 <= preco <= 30_000:
            return preco

    pessoa = re.search(r'R\$\s?([\d]{1,3}(?:\.[\d]{3})*)\s*\n?\s*/\s*pessoa', texto_card)
    if pessoa:
        preco_pessoa = int(pessoa.group(1).replace(".", ""))
        if 2_000 <= preco_pessoa <= 15_000:
            return preco_pessoa * NUM_ADULTOS

    return None


def extrair_detalhes_card(card):
    """Extrai companhia, horários e duração do card."""
    linhas_card = [l for l in card.text.split('\n') if l.strip()]

    cia = "—"
    for i, l in enumerate(linhas_card):
        if "R$" in l:
            if i > 0:
                cia = linhas_card[i - 1]
            break

    horarios = [l for l in linhas_card if "–" in l and ":" in l]
    duracoes = [l for l in linhas_card if re.search(r'\d+h', l) and "Escala" not in l and "escala" not in l]

    ida   = f"🛫 Ida: {horarios[0]} ({duracoes[0]})"   if len(horarios) > 0 and len(duracoes) > 0 else ""
    volta = f"🛬 Volta: {horarios[1]} ({duracoes[1]})" if len(horarios) > 1 and len(duracoes) > 1 else ""

    return f"✈️ {cia} | {ida} | {volta}"


def buscar(url, label, filtrar_volta_curta=False, is_mista=False):
    """
    Abre a URL no Kayak e retorna o primeiro card que atende ao filtro.
    filtrar_volta_curta=True: percorre os cards buscando volta <= MAX_HORAS_VOLTA
    is_mista=True: percorre os cards buscando aquele cuja IDA tem exatamente 1 escala
    """
    driver = criar_driver()
    dados = {"preco_casal": None, "detalhes_voo": None, "status": "erro"}
    try:
        print(f"🌐 [{label}] Abrindo Kayak...")
        driver.get(url)
        print(f"⏳ Aguardando {TIMEOUT_KAYAK}s carregamento inicial...")
        time.sleep(TIMEOUT_KAYAK)

        # Scroll progressivo para acionar lazy-load dos resultados
        print("  🖱️  Rolando página para carregar mais resultados...")
        for scroll_pct in [0.3, 0.5, 0.7, 0.9, 1.0]:
            driver.execute_script(
                f"window.scrollTo(0, document.body.scrollHeight * {scroll_pct});"
            )
            time.sleep(2)
        # Volta ao topo para leitura estável
        driver.execute_script("window.scrollTo(0, 0);")
        time.sleep(2)

        cards = driver.find_elements(By.CSS_SELECTOR, "div.nrc6-wrapper")
        if not cards:
            cards = driver.find_elements(By.CSS_SELECTOR, "div.inner-wrapper")

        print(f"  📋 {len(cards)} cards encontrados após scroll")

        if not cards:
            dados["status"] = "sem_cards"
            print(f"⚠️  [{label}] Nenhum card encontrado.")
            return dados


        card_escolhido = None

        if filtrar_volta_curta:
            # Percorre os cards buscando o mais barato com volta <= MAX_HORAS_VOLTA
            for i, c in enumerate(cards[:30]):
                h_ida, h_volta = extrair_duracoes(c.text)
                if h_ida and h_volta:
                    print(f"  Card {i+1}: ida={h_ida:.1f}h volta={h_volta:.1f}h", end="")
                    if h_volta <= MAX_HORAS_VOLTA:
                        print(f" ✅ volta OK")
                        card_escolhido = c
                        break
                    else:
                        print(f" ❌ volta longa ({h_volta:.1f}h > {MAX_HORAS_VOLTA}h)")
            if not card_escolhido:
                dados["status"] = "sem_rota_ideal"
                print(f"⚠️  [{label}] Nenhum card com volta <= {MAX_HORAS_VOLTA}h nos primeiros 15 resultados.")
                return dados

        elif is_mista:
            # Percorre os cards buscando o mais barato onde a IDA tem "1 escala"
            for i, c in enumerate(cards[:30]):
                linhas = [l.strip() for l in c.text.split('\n') if l.strip()]
                escalas = [l for l in linhas if "escala" in l.lower() and "escala de" not in l.lower()]
                print(f"  Card {i+1}: escalas={escalas[:2]}", end="")
                if len(escalas) >= 1 and "1 escala" in escalas[0].lower():
                    print(f" ✅ ida com 1 escala")
                    card_escolhido = c
                    break
                else:
                    print(f" ❌ skip")
            if not card_escolhido:
                dados["status"] = "sem_cards"
                print(f"⚠️  [{label}] Nenhum card misto encontrado.")
                return dados

        else:
            card_escolhido = cards[0]

        dados["detalhes_voo"] = extrair_detalhes_card(card_escolhido)
        preco_casal = extrair_preco_card(card_escolhido.text)
        if preco_casal:
            dados["preco_casal"] = preco_casal
            dados["status"] = "ok"
            h_ida, h_volta = extrair_duracoes(card_escolhido.text)
            print(f"✅ [{label}] R$ {preco_casal:,} | ida={h_ida:.1f}h volta={h_volta:.1f}h")
        else:
            dados["status"] = "sem_preco"
            print(f"⚠️  [{label}] Preço não encontrado no card.")

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
    print("=" * 55)
    print("✈️  MONITOR CWB → MCO | 15/02 - 27/02/2027")
    print("=" * 55)

    # Busca 1: menor preço (qualquer rota)
    menor_preco = buscar(URL_MENOR_PRECO, "Menor Preço (1-2 paradas)")

    # Busca 2: melhor rota com filtro de volta <= 13h
    melhor_rota = buscar(URL_MELHOR_ROTA, "Melhor Rota (volta <= 13h)", filtrar_volta_curta=True)

    # Busca 3: mista (1 parada na ida, qualquer número na volta, mais barato)
    mista = buscar(URL_MISTA, "Mista (1 ida, 2 volta)", is_mista=True)

    registro = {
        "timestamp":   datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "menor_preco": menor_preco,
        "melhor_rota": melhor_rota,
        "mista":       mista,
        "status":      "ok" if menor_preco["status"] == "ok" or melhor_rota["status"] == "ok" or mista["status"] == "ok" else "erro",
    }

    print()
    print(json.dumps(registro, indent=2, ensure_ascii=False))

    if registro["status"] == "ok":
        salvar_historico(registro)
    else:
        print("⚠️  Nenhum preço encontrado. Histórico não modificado.")
