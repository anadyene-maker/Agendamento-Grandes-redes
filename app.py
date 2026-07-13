import streamlit as st
import pandas as pd
import requests
import base64
import io

# Configuração da página
st.set_page_config(page_title="Controle de Agendamentos Logísticos", layout="wide")

st.title("🚚 Controle de Agendamentos Logísticos")
st.markdown("Painel dinâmico com limpeza automática de cabeçalhos do sistema e edição livre.")

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

# 1. Área de Upload de novos relatórios
st.subheader("📥 1. Alimentar com Nova Planilha do Sistema")
uploaded_file = st.file_uploader("Arraste aqui a planilha extraída do sistema (Excel ou CSV)", type=["xlsx", "csv"])

if uploaded_file:
    try:
        # Leitura inicial bruta para limpar metadados de relatórios do sistema (Emissão, Usuário, etc.)
        if uploaded_file.name.lower().endswith('.csv'):
            df_raw = pd.read_csv(uploaded_file, header=None)
        else:
            df_raw = pd.read_excel(uploaded_file, header=None)
            
        # Localiza a linha onde realmente começam os dados procurando por "Nº Nota" ou "Ordem Carga"
        linha_cabecalho = 0
        for idx, row in df_raw.iterrows():
            linha_str = row.astype(str).tolist()
            if any("Nº Nota" in s or "Ordem Carga" in s for s in linha_str):
                linha_cabecalho = idx
                break
        
        # Reconstrói o DataFrame pulando a sujeira do topo
        uploaded_file.seek(0)
        if uploaded_file.name.lower().endswith('.csv'):
            df_novo = pd.read_csv(uploaded_file, skiprows=linha_cabecalho)
        else:
            df_novo = pd.read_excel(uploaded_file, skiprows=linha_cabecalho)
            
        df_novo.columns = df_novo.columns.str.strip()
        
        # Garante a existência das colunas operacionais personalizadas
        colunas_status = {
            'Fase do Agendamento': 'Pendente',
            'Pedido de Antecipação': '',
            'Antecipado': False,
            'E-mail enviado ao OPL': False
        }
        for col, default in colunas_status.items():
            if col not in df_novo.columns:
                df_novo[col] = default

        # Se houver banco ativo, cruza as tabelas usando apenas o Nº Nota como chave única e segura
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

# 2. Exibição da Tabela de Controle Operacional
st.markdown("---")
st.subheader("📋 2. Painel de Controle Operacional")

if df_banco is not None and not df_banco.empty:
    
    # Filtro por cliente na barra lateral
    if 'Cliente' in df_banco.columns:
        clientes_disponiveis = df_banco['Cliente'].dropna().unique().tolist()
        clientes_selecionados = st.sidebar.multiselect("Filtrar por Cliente", options=clientes_disponiveis, default=clientes_disponiveis)
        df_filtrado = df_banco[df_banco['Cliente'].isin(clientes_selecionados)].copy()
    else:
        df_filtrado = df_banco.copy()
        
    # Tratamento preventivo de formatos para o editor visual não travar
    if 'E-mail enviado ao OPL' in df_filtrado.columns:
        df_filtrado['E-mail enviado ao OPL'] = df_filtrado['E-mail enviado ao OPL'].map({'True': True, 'False': False, True: True, False: False}).fillna(False).astype(bool)
    if 'Antecipado' in df_filtrado.columns:
        df_filtrado['Antecipado'] = df_filtrado['Antecipado'].map({'True': True, 'False': False, True: True, False: False}).fillna(False).astype(bool)
    
    colunas_texto = ['Fase do Agendamento', 'Pedido de Antecipação', 'Data Agendamento', 'Obs. Logística', 'Ordem Carga', 'Nº Nota']
    for col in colunas_texto:
        if col in df_filtrado.columns:
            df_filtrado[col] = df_filtrado[col].fillna("").astype(str)

    # Organização das colunas na ordem perfeita de trabalho
    colunas_visiveis = [
        'Fase do Agendamento', 'Antecipado', 'Data Agendamento', 'Obs. Logística', 
        'Pedido de Antecipação', 'E-mail enviado ao OPL', 'Ordem Carga', 'Cliente', 'Nº Nota'
    ]
    
    df_exibir = df_filtrado[[c for c in colunas_visiveis if c in df_filtrado.columns]]

    # Tabela Interativa
    edited_df = st.data_editor(
        df_exibir,
        column_config={
            "Fase do Agendamento": st.column_config.SelectboxColumn(
                "Fase do Agendamento", 
                options=["Pendente", "Solicitado no Portal", "Confirmado", "Reagenda"], 
                required=True
            ),
            "Antecipado": st.column_config.CheckboxColumn("Antecipado?"),
            "Data Agendamento": st.column_config.TextColumn("Data Agendamento (Editável)"),
            "Obs. Logística": st.column_config.TextColumn("Obs. Logística (Editável)"),
            "Pedido de Antecipação": st.column_config.TextColumn("Pedido de Antecipação (Data/Status)"),
            "E-mail enviado ao OPL": st.column_config.CheckboxColumn("E-mail OPL?"),
            "Ordem Carga": st.column_config.TextColumn("Ordem Carga (Editável)"),
            "Nº Nota": st.column_config.TextColumn("Nº Nota"),
            "Cliente": st.column_config.TextColumn("Cliente", disabled=True)
        },
        hide_index=True,
        use_container_width=True,
        key="editor_fases_v4"
    )
    
    if st.button("🚀 Salvar Alterações"):
        with st.spinner("Gravando edições de forma segura..."):
            # Lógica de salvamento blindada usando o Nº Nota como indexador estável
            df_banco['Nº Nota'] = df_banco['Nº Nota'].astype(str).str.strip()
            edited_df['Nº Nota'] = edited_df['Nº Nota'].astype(str).str.strip()
            
            for col in edited_df.columns:
                if col != 'Nº Nota':
                    mapeamento = dict(zip(edited_df['Nº Nota'], edited_df[col]))
                    df_banco[col] = df_banco['Nº Nota'].map(mapeamento).fillna(df_banco[col])
            
            sucesso = salvar_dados_github(df_banco, current_sha)
            if sucesso:
                st.success("Alterações salvas com sucesso!")
                st.rerun()
            else:
                st.error("Erro ao sincronizar. Tente recarregar a página.")
else:
    st.info("O banco de dados está vazio. Suba o relatório do sistema acima para iniciar o monitoramento.")
