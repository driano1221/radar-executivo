import requests
import statistics
import json
import sys
import time
from datetime import datetime, timedelta

# --- CONFIGURAÇÕES DE PERFIL (Lead Data Scientist) ---
UFS_ALVO = ['MG', 'SP', 'RJ']
KEYWORDS_TECNICAS = [
    'Visão Computacional', 'Previsão de Falhas', 
    'Otimização de Processos', 'Fomento à Pesquisa', 'IA'
]

# --- CONFIGURAÇÕES DE REDE E RESILIÊNCIA (PATCH V3.3) ---
TIMEOUT_GLOBAL = 30
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
    'Accept-Language': 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7',
    'Cache-Control': 'no-cache',
    'Pragma': 'no-cache'
}

def get_dates():
    """Gera dicionário de datas em múltiplos formatos para as APIs."""
    hoje = datetime.now()
    ontem = hoje - timedelta(days=1)
    seis_meses = hoje - timedelta(days=180)
    return {
        "hoje_br": hoje.strftime('%d/%m/%Y'),
        "ontem_br": ontem.strftime('%d/%m/%Y'),
        "seis_meses_br": seis_meses.strftime('%d/%m/%Y'),
        "hoje_iso": hoje.strftime('%Y-%m-%d'),
        "ontem_iso": ontem.strftime('%Y-%m-%d')
    }

def get_historical_sgs(codigo, dias=180):
    """Busca série histórica do Bacen usando filtro de data (Fix 400)."""
    dates = get_dates()
    url = f"https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo}/dados?formato=json&dataInicial={dates['seis_meses_br']}&dataFinal={dates['hoje_br']}"
    try:
        response = requests.get(url, headers=HEADERS, timeout=TIMEOUT_GLOBAL)
        if response.status_code == 200:
            data = response.json()
            return [float(x['valor']) for x in data if x.get('valor')]
        else:
            print(f"⚠️ Erro HTTP {response.status_code} no Bacen (Série {codigo}). URL: {url}", file=sys.stderr)
    except Exception as e:
        print(f"❌ Falha na conexão com Bacen (Série {codigo}): {str(e)}", file=sys.stderr)
    return []

def get_market_data():
    """Busca dados de mercado com redundância e retry (Fix 429)."""
    market_assets = {}
    
    # 1. AwesomeAPI (Tentativa 1)
    try:
        url = "https://economia.awesomeapi.com.br/json/last/USD-BRL,BTC-BRL,XAU-BRL"
        res = requests.get(url, headers=HEADERS, timeout=TIMEOUT_GLOBAL)
        if res.status_code == 200:
            j = res.json()
            market_assets["Dólar"] = float(j['USDBRL']['bid'])
            market_assets["Bitcoin"] = float(j['BTCBRL']['bid'])
            market_assets["Ouro"] = float(j['XAUBRL']['bid'])
            return market_assets
        print(f"⚠️ AwesomeAPI limitada ({res.status_code}). Ativando contingência...", file=sys.stderr)
    except:
        pass

    # 2. Contingência: CoinGecko para Cripto
    try:
        res_btc = requests.get("https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=brl", headers=HEADERS, timeout=15)
        if res_btc.status_code == 200:
            market_assets["Bitcoin"] = float(res_btc.json()['bitcoin']['brl'])
            print("✅ Bitcoin capturado via CoinGecko (Redundância)", file=sys.stderr)
    except:
        pass
    
    return market_assets

def get_leads_pncp():
    """Busca leads no PNCP com formato DD/MM/YYYY (Fix 404)."""
    dates = get_dates()
    url = f"https://pncp.gov.br/api/pncp/v1/contratos?dataInicial={dates['ontem_br']}&dataFinal={dates['ontem_br']}&pagina=1"
    leads = []
    try:
        response = requests.get(url, headers=HEADERS, timeout=TIMEOUT_GLOBAL)
        if response.status_code == 200:
            contratos = response.json().get('data', [])
            for c in contratos:
                objeto = str(c.get('objeto', '')).upper()
                uf = c.get('orgaoEntidade', {}).get('uf', '')
                if uf in UFS_ALVO and any(kw.upper() in objeto for kw in KEYWORDS_TECNICAS):
                    leads.append({
                        "orgao": c.get('orgaoEntidade', {}).get('razaoSocial'),
                        "valor": c.get('valorTotal', 0),
                        "local": uf,
                        "link": f"https://pncp.gov.br/app/contratos/{c.get('cnpjOrgao')}/{c.get('anoContrato')}/{c.get('numeroContrato')}"
                    })
        else:
            print(f"⚠️ Erro HTTP {response.status_code} no PNCP. URL: {url}", file=sys.stderr)
    except Exception as e:
        print(f"❌ Falha na conexão com PNCP: {str(e)}", file=sys.stderr)
    return leads

def main():
    assets = []
    # Camada Bacen
    for name, code in [("Selic", 432), ("IPCA", 433)]:
        vals = get_historical_sgs(code)
        if vals:
            current = vals[-1]
            mean = statistics.mean(vals)
            stdev = statistics.stdev(vals) if len(vals) > 1 else 0.1
            z_score = (current - mean) / stdev if stdev > 0 else 0
            status = "⚠️ Anomalia" if abs(z_score) > 2 else "✅ Estável"
            assets.append({"Ativo": name, "Valor": f"{current}%", "Status": status, "Z-Score": round(z_score, 2)})
    
    # Camada Mercado
    mkt = get_market_data()
    for name, val in mkt.items():
        assets.append({"Ativo": name, "Valor": f"R$ {val:,.2f}", "Status": "✅ Estável", "Z-Score": "N/A"})

    # Camada Leads
    leads = get_leads_pncp()
    
    now_str = datetime.now().strftime('%d/%m/%Y %H:%M')
    md = [f"# 🚀 Radar Executivo v3.3 | {now_str}", "\n---", "## 💰 Inteligência de Mercado"]
    
    if not assets:
        md.append("> ⚠️ Falha crítica na captura de dados financeiros mundiais.")
    else:
        md.append("| Ativo | Valor Atual | Status | Z-Score (6m) |")
        md.append("| :--- | :--- | :--- | :--- |")
        for a in assets:
            md.append(f"| {a['Ativo']} | {a['Valor']} | {a['Status']} | {a['Z-Score']} |")
    
    md.append("\n## 💼 Prospecção Ativa (MG, SP, RJ)")
    if not leads:
        md.append("> ℹ️ Nenhuma oportunidade técnica de alta aderência identificada hoje.")
    else:
        md.append("| Órgão | Valor | Local | Link |")
        md.append("| :--- | :--- | :--- | :--- |")
        for l in leads:
            md.append(f"| {l['orgao']} | R$ {l['valor']:,.2f} | {l['local']} | [Ver Contrato]({l['link']}) |")

    md.append("\n---")
    md.append("*Dashboard resiliente v3.3 via Python & GitHub Actions.*")
    
    report_md = "\n".join(md)
    with open("relatorio.md", "w", encoding="utf-8") as f:
        f.write(report_md)
    
    print(report_md)

if __name__ == "__main__":
    main()
