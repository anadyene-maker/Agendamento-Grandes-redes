import streamlit as st
import pandas as pd
import requests
import base64
import io
from datetime import datetime

# Configuração da página - DEVE ser a primeira linha de código Streamlit
st.set_page_config(page_title="Controle de Agendamentos Logísticos", layout="wide")

st.title("🚚 Controle de Agendamentos (Banco de Dados Ativo)")
st.markdown("Plataforma compartilhável com histórico salvo automaticamente no GitHub.")

# Configurações do Repositório via Secrets
GITHUB_TOKEN = st.secrets["GITHUB_TOKEN"]
REPO = "anadyene-maker/Agendamento-Grandes-redes"
FILE_PATH = "base_dados_agendamentos.csv"
URL = f"https://api.github.com/repos/{REPO}/contents/{FILE_PATH}"

headers = {
    "Authorization": f"token {GITHUB_TOKEN}",
    "Accept": "application/vnd.github.v3+json"
}

# Função para buscar os dados existentes no GitHub
def carregar_dados_github():
    response = requests.get(URL, headers=headers)
    if response.status_code == 200:
        content = response.json()
        csv_data = base64.b64decode(content['content']).decode('utf-8')
        df = pd.read_csv(io.StringIO(csv_data))
        return df, content['sha']
    return pd.DataFrame(), None

# Função para salvar/atualizar os dados no GitHub
def salvar_dados_github(df_salvar, sha=None):
    csv_string = df_salvar.to_csv(index=False)
    content_b64 = base64.b64encode(csv_string.encode('utf-8')).decode('utf-8')
    
    data = {
        "message": "Atualização automática de agendamentos via Streamlit",
        "content": content_b64
    }
    if sha:
        data["sha"] = sha
        
    response = requests.put(URL, headers=headers, json=data)
    return response.status_code in [200, 201]

# Carrega o histórico salvo na nuvem do Git
df_banco, current_sha = carregar_dados_github()

# Área de Upload de novos relatórios do Sistema
st.subheader("📥 Alimentar o Sistema (Opcional)")
uploaded_file = st.file_uploader("Arraste o relatório diário do sistema aqui para mesclar novos dados", type=["xlsx"])

if uploaded_file:
    df_novo = pd.read_excel(uploaded_file, skiprows=2)
    
    # Remove espaços em branco antes ou depois dos nomes das colunas
    df_novo.columns = df_novo.columns.str.strip()
    
    # Criar colunas operacionais com segurança (evita o erro KeyError)
    if 'Agendado Para' not in df_novo.columns:
        if 'Data Agendamento' in df_novo.columns:
            df_novo['Agendado Para'] = df_novo['Data Agendamento'].fillna("")
        else:
            df_novo['Agendado Para'] = ""
            
    if 'Confirmado' not in df_novo.columns:
        df_novo['Confirmado'] = "Pendente"
        
    if 'E-mail enviado ao OPL' not in df_novo.columns:
        df_novo['E-mail enviado ao OPL'] = False
        
    if 'Tem Antecipação?' not in df_novo.columns:
        df_novo['Tem Antecipação?'] = "Não"
        
    # Lógica de Antecipação automática baseada nas observações
    for idx, row in df_novo.iterrows():
        obs = str(row.get('Obs. Logística', '')).lower()
        if 'antecipar' in obs or 'portal indeferiu' in obs or 'indefe' in obs:
