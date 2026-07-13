import streamlit as st
import pandas as pd
import requests
import base64
import io

# Configuração da página
st.set_page_config(page_title="Controle de Agendamentos Logísticos", layout="wide")

st.title("🚚 Controle de Agendamentos Logísticos")
st.markdown("Sistema reconstruído do zero para controle de fases de agendamento.")

# Configurações do Repositório via Secrets
GITHUB_TOKEN = st.secrets["GITHUB_TOKEN"]
REPO = "anadyene-maker/Agendamento-Grandes-redes"
FILE_PATH = "base_dados_agendamentos.csv"
URL = f"https://api.github.com/repos/{REPO}/contents/{FILE_PATH}"

headers = {
    "Authorization": f"token {GITHUB_TOKEN}",
    "Accept": "application/vnd.github.v3+json"
}

# Função para salvar no GitHub
def salvar_dados_github(df_salvar, sha=None):
    csv_string = df_salvar.to_csv(index=False)
    content_b64 = base64.b64encode(csv_string.encode('utf-8')).decode('utf-8')
    
    data = {
        "message": "Atualização de agendamentos via Streamlit",
        "content": content_b64
    }
    if sha:
        data["sha"] = sha
        
    response = requests.put(URL, headers=headers, json=data)
    return response.status_code in [200, 201]

# Função para carregar do GitHub
def carregar_dados_github():
    response = requests.get(URL, headers=headers)
    if response.status_code == 200:
        content = response.json()
        sha = content.get('sha')
        try:
            csv_data = base64.b64decode(content['content']).decode('utf-8')
            if not csv_data.strip():
                return pd.DataFrame(), sha
            df = pd.read_csv(io.StringIO(csv_data))
            return df, sha
        except Exception:
            return pd.DataFrame(), sha
    return pd.DataFrame(), None

# Carrega o banco de dados atualizado
df_banco, current_sha = carregar_dados_github()

# 1. Área de Upload de novos relatórios
st.subheader("📥 1. Alimentar com Nova Planilha do Sistema")
uploaded_file = st.file_uploader("Arraste aqui a planilha extraída do sistema", type=["xlsx", "csv"])

if uploaded_file:
    try:
        # Leitura direta e simples do arquivo novo
        if uploaded_file.name.lower().endswith('.csv'):
            df_novo = pd.read_csv(uploaded_file)
        else:
            df_novo = pd.read_excel(uploaded_file)
            
        df_novo.columns = df_novo.columns.str.strip()
        
        # Garante que as colunas de controle operacional que você pediu existam
        if 'Fase do Agendamento' not in df_novo.columns:
            df_novo['Fase do Agendamento'] = "Pendente"
            
        if 'Pedido de Antecipação' not in df_novo.columns:
            df_novo['Pedido de Antecipação'] = ""
            
        if 'E-mail enviado ao OPL' not in df_novo.columns:
            df_novo['E-mail enviado ao OPL'] = False

        # Se já tiver dados salvos no banco, cruza pela chave única para não duplicar e manter o que foi editado
        if df_banco is not None and not df_banco.empty and 'Ordem Carga' in df_novo.columns and 'Nº Nota' in df_novo.columns:
            df_banco['chave'] = df_banco['Ordem Carga'].astype(str) + "_" + df_banco['Nº Nota'].astype(str)
            df_novo['chave'] = df_novo['Ordem Carga'].astype(str) + "_" + df_novo['Nº Nota'].astype(str)
            
            # Mantém as linhas antigas que já estão no banco e adiciona apenas o que for novo do relatório
            novas_linhas = df_novo[~df_novo['chave'].isin(df_banco['chave'])]
            df_final = pd.concat([df_banco, novas_linhas], ignore_index=True).drop(columns=['chave'], errors='ignore')
        else:
            df_final = df_novo

        if st.button("💾 Enviar e Atualizar Banco de Dados Compartilhado"):
            with st.spinner("Salvando..."):
                sucesso = salvar_dados_github(df_final, current_sha)
                if sucesso:
                    st.success("Planilha integrada com sucesso!")
                    st.rerun()
                else:
                    st.error("Erro ao salvar. Verifique se o Token nas Secrets está correto.")
    except Exception as e:
        st.error(f"Erro ao ler o arquivo enviado: {e}")

# 2. Exibição da Tabela de Controle Operacional
st.markdown("---")
st.subheader("📋 2. Painel de Controle Operacional")

if df_banco is not None and not df_banco.empty:
    
    # Filtro simples por cliente na barra lateral
    if 'Cliente' in df_banco.columns:
        clientes_disponiveis = df_banco['Cliente'].dropna().unique().tolist()
        clientes_selecionados = st.sidebar.multiselect("Filtrar por Cliente", options=clientes_disponiveis, default=clientes_disponiveis)
        df_filtrado = df_banco[df_banco['Cliente'].isin(clientes_selecionados)].copy()
    else:
        df_filtrado = df_banco.copy()
        
    # Garante tipos corretos para a tabela interativa não dar erro visual
    if 'E-mail enviado ao OPL' in df_filtrado.columns:
        df_filtrado['E-mail enviado ao OPL'] = df_filtrado['E-mail enviado ao OPL'].map({'True': True, 'False': False, True: True, False: False}).fillna(False).astype(bool)
    if 'Pedido de Antecipação' in df_filtrado.columns:
        df_filtrado['Pedido de Antecipação'] = df_filtrado['Pedido de Antecipação'].fillna("").astype(str)
    if 'Fase do Agendamento' in df_filtrado.columns:
        df_filtrado['Fase do Agendamento'] = df_filtrado['Fase do Agendamento'].fillna("Pendente").astype(str)

    # Colunas que fará sentido você ver e editar na tela
    colunas_visiveis = [
        'Ordem Carga', 'Cliente', 'Nº Nota', 'Data Agendamento', 'Obs. Logística',
        'Fase do Agendamento', 'Pedido de Antecipação', 'E-mail enviado ao OPL'
    ]
    
    df_exibir = df_filtrado[[c for c in colunas_visiveis if c in df_filtrado.columns]]

    # Tabela Interativa Customizada com os campos solicitados
    edited_df = st.data_editor(
        df_exibir,
        column_config={
            "Fase do Agendamento": st.column_config.SelectboxColumn(
                "Fase do Agendamento", 
                options=["Pendente", "Solicitado no Portal", "Confirmado", "Reagenda"], 
                required=True
            ),
            "Pedido de Antecipação": st.column_config.TextColumn("Pedido de Antecipação (Data/Status)"),
            "E-mail enviado ao OPL": st.column_config.CheckboxColumn("E-mail OPL?", default=False),
            "Ordem Carga": st.column_config.TextColumn("Ordem Carga", disabled=True),
            "Cliente": st.column_config.TextColumn("Cliente", disabled=True),
            "Nº Nota": st.column_config.TextColumn("Nº Nota", disabled=True),
            "Data Agendamento": st.column_config.TextColumn("Data Agendamento", disabled=True),
            "Obs. Logística": st.column_config.TextColumn("Obs. Logística", disabled=True)
        },
        hide_index=True,
        use_container_width=True,
        key="editor_fases_zero"
    )
    
    if st.button("🚀 Salvar Alterações das Fases"):
        # Aplica as modificações de volta no banco principal
        df_banco.update(edited_df)
        with st.spinner("Sincronizando com a nuvem..."):
            sucesso = salvar_dados_github(df_banco, current_sha)
            if sucesso:
                st.success("Alterações salvas com sucesso para toda a equipe!")
                st.rerun()
            else:
                st.error("Erro ao sincronizar. Tente atualizar a página.")
else:
    st.info("O banco de dados está vazio. Por favor, suba essa planilha nova acima para ativar o painel.")
