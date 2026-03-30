import requests
import statistics
import json
import sys
from datetime import datetime, timedelta

# --- CONFIGURAÇÕES DE PERFIL (Lead Data Scientist) ---
UFS_ALVO = ['MG', 'SP', 'RJ']
KEYWORDS_TECNICAS = [
    'Visão Computacional', 'Previsão de Falhas', 
    'Otimização de Processos', 'Fomento à Pesquisa', 'IA'
]

# Aumentando o timeout para 30 segundos para maior resiliência em ambientes de CI
TIMEOUT_GLOBAL = 30

def get_historical_sgs(codigo, dias=180):
    """Busca série histórica do Bacen (SGS) para análise estatística."""
    url = f"https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo}/dados/ultimos/{dias}"
    try:
        response = requests.get(url, timeout=TIMEOUT_GLOBAL)
        if response.status_code == 200:
            data = response.json()
            return [float(x['valor']) for x in data]
        else:
            print(f"⚠️ Erro HTTP {response.status_code} ao buscar série {codigo}", file=sys.stderr)
    except Exception as e:
        print(f"❌ Falha na conexão com Bacen (Série {codigo}): {str(e)}", file=sys.stderr)
    return []

def get_awesome_api_data():
    """Busca Dólar, Bitcoin e Ouro via AwesomeAPI (pública e estável)."""
    url = "https://economia.awesomeapi.com.br/json/last/USD-BRL,BTC-BRL,XAU-BRL"
    try:
        response = requests.get(url, timeout=TIMEOUT_GLOBAL)
        if response.status_code == 200:
            res = response.json()
            return {
                "USD": float(res['USDBRL']['bid']),
                "BTC": float(res['BTCBRL']['bid']),
                "GOLD": float(res['XAUBRL']['bid'])
            }
        else:
            print(f"⚠️ Erro HTTP {response.status_code} na AwesomeAPI", file=sys.stderr)
    except Exception as e:
        print(f"❌ Falha na conexão com AwesomeAPI: {str(e)}", file=sys.stderr)
    return {}

def analyze_assets():
    """Camada 1: Análise de Anomalias Multi-Asset."""
    assets = []
    # 1. Bacen: Selic (432) e IPCA (433)
    for name, code in [("Selic", 432), ("IPCA", 433)]:
        vals = get_historical_sgs(code)
        if vals:
            current = vals[-1]
            mean = statistics.mean(vals)
            stdev = statistics.stdev(vals) if len(vals) > 1 else 0.1
            z_score = (current - mean) / stdev if stdev > 0 else 0
            status = "⚠️ Anomalia" if abs(z_score) > 2 else "✅ Estável"
            assets.append({"Ativo": name, "Valor": f"{current}%", "Status": status, "Z-Score": round(z_score, 2)})

    # 2. Câmbio e Commodities
    awesome = get_awesome_api_data()
    for key, name in [("USD", "Dólar"), ("BTC", "Bitcoin"), ("GOLD", "Ouro")]:
        if key in awesome:
            val = awesome[key]
            assets.append({"Ativo": name, "Valor": f"R$ {val:,.2f}", "Status": "✅ Estável", "Z-Score": "N/A"})
    
    return assets

def get_leads_v3():
    """Camada 2: Lead Scoring & AI Pitch (PNCP + Filtro Geo)."""
    ontem = (datetime.now() - timedelta(days=1)).strftime('%Y%m%d')
    url_pncp = f"https://pncp.gov.br/api/pncp/v1/contratos?dataInicial={ontem}&dataFinal={ontem}&pagina=1"
    
    leads = []
    try:
        response = requests.get(url_pncp, timeout=TIMEOUT_GLOBAL)
        if response.status_code == 200:
            contratos = response.json().get('data', [])
            for c in contratos:
                uf = c.get('orgaoEntidade', {}).get('uf', '')
                objeto = str(c.get('objeto', '')).upper()
                orgao = c.get('orgaoEntidade', {}).get('razaoSocial', 'Órgão não informado')
                
                if uf in UFS_ALVO:
                    for kw in KEYWORDS_TECNICAS:
                        if kw.upper() in objeto:
                            pitch = f"Como Mestre pela UFV e especialista em {kw}, posso atuar na otimização deste projeto para o {orgao}."
                            leads.append({
                                "orgao": orgao,
                                "valor": f"R$ {c.get('valorTotal', 0):,.2f}",
                                "local": uf,
                                "pitch": pitch,
                                "link": f"https://pncp.gov.br/app/contratos/{c.get('cnpjOrgao')}/{c.get('anoContrato')}/{c.get('numeroContrato')}"
                            })
                            break
        else:
            print(f"⚠️ Erro HTTP {response.status_code} no PNCP", file=sys.stderr)
    except Exception as e:
        print(f"❌ Falha na conexão com PNCP: {str(e)}", file=sys.stderr)
    return leads

def main():
    assets = analyze_assets()
    leads = get_leads_v3()
    
    now_str = datetime.now().strftime('%d/%m/%Y %H:%M')
    md = [f"# 🚀 Radar Executivo v3.1 | {now_str}"]
    md.append("\n---")
    
    # Seção 1: Mercado
    md.append("## 💰 Inteligência de Mercado (Multi-Asset)")
    if not assets:
        md.append("> ⚠️ Erro na conexão com as APIs financeiras no momento da execução.")
    else:
        md.append("| Ativo | Valor Atual | Status | Z-Score (6m) |")
        md.append("| :--- | :--- | :--- | :--- |")
        for a in assets:
            md.append(f"| {a['Ativo']} | {a['Valor']} | {a['Status']} | {a['Z-Score']} |")
    
    # Seção 2: Carreira
    md.append("\n## 💼 Prospecção Ativa (MG, SP, RJ)")
    if not leads:
        md.append("> ℹ️ Nenhuma oportunidade de alta aderência técnica identificada nas últimas 24h.")
    else:
        md.append("| Órgão | Valor | Local | AI Pitch |")
        md.append("| :--- | :--- | :--- | :--- |")
        for l in leads:
            md.append(f"| [{l['orgao']}]({l['link']}) | {l['valor']} | {l['local']} | *{l['pitch']}* |")
            
    # Seção 3: To-Do
    md.append("\n## ✅ Ações Recomendadas")
    if any(a.get('Status') == "⚠️ Anomalia" for a in assets):
        md.append("- [ ] **Financeiro:** Revisar alocação. Detectada anomalia estatística (>2σ) em indicadores macro.")
    if leads:
        md.append(f"- [ ] **Carreira:** Enviar portfólio customizado para os {len(leads)} leads do PNCP.")
    md.append("- [ ] **Networking:** Monitorar editais da FAPEMIG/CNPq para 'Fomento à Pesquisa/IA'.")
    
    md.append("\n---")
    md.append("*Dashboard consolidado via Python & GitHub Actions.*")
    
    report_md = "\n".join(md)
    with open("relatorio.md", "w", encoding="utf-8") as f:
        f.write(report_md)
    
    # Output para o log do GitHub Actions
    print(report_md)

if __name__ == "__main__":
    main()
