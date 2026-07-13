import streamlit as st
import pandas as pd
import requests
import base64
import io

# Configuração da página
st.set_page_config(page_title="Controle de Agendamentos Logísticos", layout="wide")

# 🎭 CÓDIGO PARA IMPRESSÃO: Mantém apenas os gráficos visíveis na hora de imprimir
st.markdown("""
    <style>
    @media print {
        section[data-testid="stSidebar"], 
        .stFileUploader, 
        .stButton, 
        div[data-testid="stDataFrame"],
        div[data-testid="element-container"]:has(.stFileUploader),
        h3:contains("1. Alimentar com Nova Planilha"),
        h3:contains("2. Painel de Controle Operacional"),
        div:has(> input[type="checkbox"]),
        hr {
            display: none !important;
        }
        .main .block-container {
            padding-top: 1rem !important;
            padding-bottom: 1rem !important;
        }
    }
    </style>
""", unsafe_allow_html=True)

st.title("🚚 Controle de Agendamentos Logísticos")
st.markdown("Painel dinâmico com gráficos gerenciais, controle de fases e proteção de dados.")

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

# Carrega o banco de dados
df_banco, current_sha = carregar_dados_github()

# 🔐 CONTROLE DE ACESSO NA BARRA LATERAL
st.sidebar.markdown("### 🔑 Controle de Acesso")
modo_editor = st.sidebar.checkbox("Ativar Modo Editor", value=False)

# 1. Área de Upload de novos relatórios (Só aparece no modo editor)
if modo_editor:
    st.subheader("📥 1. Alimentar com Nova Planilha do Sistema")
    uploaded_file = st.file_uploader("Arraste aqui a planilha extraída do sistema (Excel ou CSV)", type=["xlsx", "csv"])

    if uploaded_file:
        try:
            if uploaded_file.name.lower().endswith('.csv'):
                df_raw = pd.read_csv(uploaded_file, header=None)
            else:
                df_raw = pd.read_excel(uploaded_file, header=None)
                
            linha_cabecalho = 0
            for idx, row in df_raw.iterrows():
                linha_str = row.astype(str).tolist()
                if any("Nº Nota" in s or "Ordem Carga" in s for s in linha_str):
                    linha_cabecalho = idx
                    break
            
            uploaded_file.seek(0)
            if uploaded_file.name.lower().endswith('.csv'):
                df_novo = pd.read_csv(uploaded_file, skiprows=linha_cabecalho)
            else:
                df_novo = pd.read_excel(uploaded_file, skiprows=linha_cabecalho)
                
            df_novo.columns = df_novo.columns.str.strip()
            
            colunas_status = {
                'Fase do Agendamento': 'Pendente',
                'Pedido de Antecipação': '',
                'Antecipado': False,
                'E-mail enviado ao OPL': False
            }
            for col, default in colunas_status.items():
                if col not in df_novo.columns:
                    df_novo[col] = default

            if df_banco is not None and not df_banco.empty and 'Nº Nota' in df_novo.columns:
                df_banco['Nº Nota'] = df_banco['Nº Nota'].astype(str).str.strip()
                df_novo['Nº Nota'] = df_novo['Nº Nota'].astype(str).str.strip()
                
                novas_linhas = df_novo[~df_novo['Nº Nota'].isin(df_banco['Nº Nota'])]
                df_final = pd.concat([df_banco, novas_linhas], ignore_index=True)
            else:
                df_final = df_novo

            if st.button("💾 Enviar e Atualizar Banco de Dados Compartilhado"):
                with st.spinner("Salvando no repositório..."):
                    sucesso = salvar_dados_github(df_final, current_sha)
                    if sucesso:
                        st.success("Novos dados integrados com sucesso!")
                        st.rerun()
                    else:
                        st.error("Erro ao salvar no servidor. Verifique suas configurações.")
        except Exception as e:
            st.error(f"Erro ao processar o arquivo enviado: {e}")

# Tratamento dos dados para os Gráficos e Filtros
if df_banco is not None and not df_banco.empty:
    
    # Identifica ou cria a coluna de Operador Logístico padronizada
    if 'Operador Logístico' not in df_banco.columns:
        if 'Logística Ent.' in df_banco.columns:
            df_banco['Operador Logístico'] = df_banco['Logística Ent.']
        elif 'Transportadora' in df_banco.columns:
            df_banco['Operador Logístico'] = df_banco['Transportadora']
        else:
            df_banco['Operador Logístico'] = "Não Informado"
            
    df_banco['Operador Logístico'] = df_banco['Operador Logístico'].fillna("Não Informado").astype(str).str.strip()
    
    # 📑 FILTROS NA BARRA LATERAL
    st.sidebar.markdown("### 🔍 Filtros de Operação")
    
    # Filtro 1: Operador Logístico (Carraro, J.Lobo, etc.)
    opls_disponiveis = df_banco['Operador Logístico'].unique().tolist()
    opls_selecionados = st.sidebar.multiselect("Filtrar por Operador Logístico", options=opls_disponiveis, default=opls_disponiveis)
    df_filtrado = df_banco[df_banco['Operador Logístico'].isin(opls_selecionados)].copy()
    
    # Filtro 2: Cliente
    if 'Cliente' in df_filtrado.columns:
        clientes_disponiveis = df_filtrado['Cliente'].dropna().unique().tolist()
        clientes_selecionados = st.sidebar.multiselect("Filtrar por Cliente", options=clientes_disponiveis, default=clientes_disponiveis)
        df_filtrado = df_filtrado[df_filtrado['Cliente'].isin(clientes_selecionados)].copy()
        
    # Tratamentos de formato estáveis
    if 'E-mail enviado ao OPL' in df_filtrado.columns:
        df_filtrado['E-mail enviado ao OPL'] = df_filtrado['E-mail enviado ao OPL'].map({'True': True, 'False': False, True: True, False: False}).fillna(False).astype(bool)
    if 'Antecipado' in df_filtrado.columns:
        df_filtrado['Antecipado'] = df_filtrado['Antecipado'].map({'True': True, 'False': False, True: True, False: False}).fillna(False).astype(bool)
    
    colunas_texto = ['Pedido de Antecipação', 'Data Agendamento', 'Obs. Logística', 'Ordem Carga', 'Nº Nota']
    for col in colunas_texto:
        if col in df_filtrado.columns:
            df_filtrado[col] = df_filtrado[col].fillna("").astype(str)

    opcoes_permitidas = ["Pendente", "Solicitado no Portal", "Confirmado", "Reagenda"]
    if 'Fase do Agendamento' in df_filtrado.columns:
        df_filtrado['Fase do Agendamento'] = df_filtrado['Fase do Agendamento'].fillna("Pendente").astype(str).str.strip()
        df_filtrado.loc[~df_filtrado['Fase do Agendamento'].isin(opcoes_permitidas), 'Fase do Agendamento'] = "Pendente"

    # 📊 SEÇÃO GRÁFICOS E METRICAS GERENCIAIS
    st.markdown("---")
    
    c_titulo, c_botao = st.columns([3, 1])
    with c_titulo:
        st.subheader("📊 Resumo Executivo")
    with c_botao:
        st.markdown("""
            <button onclick="window.print()" style="
                width: 100%;
                background-color: #FF4B4B;
                color: white;
                border: none;
                padding: 0.50rem 0.75rem;
                border-radius: 0.5rem;
                cursor: pointer;
                font-weight: bold;
                box-shadow: 0px 4px 6px rgba(0,0,0,0.1);
            ">🖨️ Imprimir Só os Gráficos</button>
        """, unsafe_allow_html=True)
    
    # 1. Cards Indicadores
    m1, m2, m3 = st.columns(3)
    total_cargas = len(df_filtrado)
    total_antecipados = df_filtrado['Antecipado'].sum()
    total_confirmados = (df_filtrado['Fase do Agendamento'] == "Confirmado").sum()
    
    m1.metric("📦 Total de Cargas Monitoradas", total_cargas)
    m2.metric("⚠️ Antecipações Solicitadas", f"{total_antecipados} pedidas")
    m3.metric("✅ Agendamentos Confirmados", total_confirmados)
    
    # 2. Gráficos Visuais
    g1, g2 = st.columns(2)
    
    with g1:
        st.markdown("**Situação Atual dos Agendamentos**")
        fases_contagem = df_filtrado['Fase do Agendamento'].value_counts().reindex(opcoes_permitidas, fill_value=0)
        st.bar_chart(fases_contagem, color="#FF4B4B")
        
    with g2:
        st.markdown("**Volume de Cargas por Operador Logístico**")
        opl_contagem = df_filtrado['Operador Logístico'].value_counts()
        st.bar_chart(opl_contagem, color="#0068C9")

    # 3. Exibição da Tabela de Controle Operacional
    st.markdown("---")
    st.subheader("📋 2. Painel de Controle Operacional")

    colunas_visiveis = [
        'Fase do Agendamento', 'Antecipado', 'Data Agendamento', 'Obs. Logística', 
        'Operador Logístico', 'Pedido de Antecipação', 'E-mail enviado ao OPL', 'Ordem Carga', 'Cliente', 'Nº Nota'
    ]
    
    df_exibir = df_filtrado[[c for c in colunas_visiveis if c in df_filtrado.columns]]

    # Tabela Interativa (Bloqueia ou libera edições com base na caixinha lateral)
    edited_df = st.data_editor(
        df_exibir,
        column_config={
            "Fase do Agendamento": st.column_config.SelectboxColumn("Fase do Agendamento", options=opcoes_permitidas, required=True, disabled=not modo_editor),
            "Antecipado": st.column_config.CheckboxColumn("Antecipado?", disabled=not modo_editor),
            "Data Agendamento": st.column_config.TextColumn("Data Agendamento", disabled=not modo_editor),
            "Obs. Logística": st.column_config.TextColumn("Obs. Logística", disabled=not modo_editor),
            "Operador Logístico": st.column_config.TextColumn("Operador Logístico", disabled=True),
            "Pedido de Antecipação": st.column_config.TextColumn("Pedido de Antecipação", disabled=not modo_editor),
            "E-mail enviado ao OPL": st.column_config.CheckboxColumn("E-mail OPL?", disabled=not modo_editor),
            "Ordem Carga": st.column_config.TextColumn("Ordem Carga", disabled=not modo_editor),
            "Nº Nota": st.column_config.TextColumn("Nº Nota", disabled=True),
            "Cliente": st.column_config.TextColumn("Cliente", disabled=True)
        },
        hide_index=True,
        use_container_width=True,
        key="editor_fases_v9"
    )
    
    # Botão de salvar só aparece se o usuário ativar o modo editor
    if modo_editor:
        if st.button("🚀 Salvar Alterações"):
            with st.spinner("Gravando edições de forma segura..."):
                df_banco['Nº Nota'] = df_banco['Nº Nota'].astype(str).str.strip()
                edited_df['Nº Nota'] = edited_df['Nº Nota'].astype(str).str.strip()
                
                for col in edited_df.columns:
                    if col != 'Nº Nota' and col in df_banco.columns:
                        mapeamento = dict(zip(edited_df['Nº Nota'], edited_df[col]))
                        df_banco[col] = df_banco['Nº Nota'].map(mapeamento).fillna(df_banco[col])
                
                sucesso = salvar_dados_github(df_banco, current_sha)
                if sucesso:
                    st.success("Alterações salvas com sucesso!")
                    st.rerun()
                else:
                    st.error("Erro ao sincronizar. Tente recarregar a página.")
    else:
        st.info("💡 Modo de Visualização Ativo. Para fazer alterações ou subir planilhas, marque a caixinha 'Modo Editor' na barra lateral.")
else:
    st.info("O banco de dados está vazio. Suba o relatório no Modo Editor para começar.")
