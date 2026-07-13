import streamlit as st
import pandas as pd
import requests
import base64
import io

# Configuração da página - DEVE ser a primeira linha de código Streamlit
st.set_page_config(page_title="Controle de Agendamentos Logísticos", layout="wide")

st.title("🚚 Controle de Agendamentos (Banco de Dados Ativo)")
st.markdown("Plataforma compartilhável com histórico permanente em nuvem (GitHub).")

# Configurações do Repositório via Secrets
GITHUB_TOKEN = st.secrets["GITHUB_TOKEN"]
REPO = "anadyene-maker/Agendamento-Grandes-redes"
FILE_PATH = "base_dados_agendamentos.csv"
URL = f"https://api.github.com/repos/{REPO}/contents/{FILE_PATH}"

headers = {
    "Authorization": f"token {GITHUB_TOKEN}",
    "Accept": "application/vnd.github.v3+json"
}

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
            if 'E-mail enviado ao OPL' in df.columns:
                df['E-mail enviado ao OPL'] = df['E-mail enviado ao OPL'].map({'True': True, 'False': False, True: True, False: False}).fillna(False)
            return df, sha
        except Exception:
            return pd.DataFrame(), sha
    return pd.DataFrame(), None

df_banco, current_sha = carregar_dados_github()

st.subheader("📥 Alimentar o Sistema")
uploaded_file = st.file_uploader("Arraste o relatório aqui (Excel ou CSV)", type=["xlsx", "csv"])

if uploaded_file:
    df_novo = None
    try:
        # --- MOTOR DE LEITURA UNIVERSAL ---
        if uploaded_file.name.lower().endswith('.csv'):
            # Lendo formato CSV
            bytes_data = uploaded_file.read()
            text_data = bytes_data.decode('utf-8', errors='ignore')
            linhas = text_data.splitlines()
            uploaded_file.seek(0)
            
            # Identifica a linha correta do cabeçalho
            skip_rows = 0
            for i, linha in enumerate(linhas[:10]):
                if "Ordem Carga" in linha:
                    skip_rows = i
                    break
            
            separador = ';' if ';' in (linhas[skip_rows] if len(linhas) > skip_rows else "") else ','
            df_novo = pd.read_csv(uploaded_file, skiprows=skip_rows, sep=separador)
        else:
            # Lendo formato Excel (.xlsx)
            df_excel_cru = pd.read_excel(uploaded_file)
            uploaded_file.seek(0)
            
            # Varre as primeiras linhas para achar onde está o cabeçalho "Ordem Carga"
            skip_rows = None
            for i in range(min(10, len(df_excel_cru))):
                linha_valores = df_excel_cru.iloc[i].astype(str).tolist()
                if any("Ordem Carga" in v for v in linha_valores):
                    skip_rows = i + i  # Ajuste do índice real de pulo
                    break
            
            if skip_rows is not None:
                df_novo = pd.read_excel(uploaded_file, skiprows=skip_rows)
            else:
                # Fallback se não encontrar o marcador textual nas linhas
                df_teste = pd.read_excel(uploaded_file, nrows=5)
                if df_teste.dropna(how='all').iloc[0].astype(str).str.contains('Emissão|Total|Relatório|arquivo').any():
                    df_novo = pd.read_excel(uploaded_file, skiprows=2)
                else:
                    df_novo = pd.read_excel(uploaded_file)
        
        # Garante a limpeza dos nomes das colunas
        if df_novo is not None:
            df_novo.columns = df_novo.columns.str.strip()
            
            # Tratamento caso a primeira linha ainda venha duplicada como string residual do cabeçalho
            if not df_novo.empty and "Ordem Carga" in str(df_novo.iloc[0, 0]):
                df_novo = df_novo.iloc[1:].reset_index(drop=True)
        
        # Validação crucial de segurança das colunas
        if df_novo is None or 'Ordem Carga' not in df_novo.columns or 'Nº Nota' not in df_novo.columns:
            st.error("Não foi possível mapear as colunas obrigatórias ('Ordem Carga' e 'Nº Nota'). Por favor, verifique a estrutura do arquivo enviado.")
        else:
            # Inicializa colunas operacionais se não existirem
            if 'Agendado Para' not in df_novo.columns:
                df_novo['Agendado Para'] = df_novo['Data Agendamento'].fillna("") if 'Data Agendamento' in df_novo.columns else ""
                
            if 'Confirmado' not in df_novo.columns:
                df_novo['Confirmado'] = "Pendente"
                
            if 'E-mail enviado ao OPL' not in df_novo.columns:
                df_novo['E-mail enviado ao OPL'] = False
            else:
                df_novo['E-mail enviado ao OPL'] = df_novo['E-mail enviado ao OPL'].map({'True': True, 'False': False, True: True, False: False}).fillna(False)
                
            if 'Tem Antecipação?' not in df_novo.columns:
                df_novo['Tem Antecipação?'] = "Não"
                
            if 'Obs. Logística' in df_novo.columns:
                for idx, row in df_novo.iterrows():
                    obs = str(row.get('Obs. Logística', '')).lower()
                    if 'antecipar' in obs or 'portal indeferiu' in obs or 'indefe' in obs:
                        df_novo.at[idx, 'Tem Antecipação?'] = "⚠️ Solicitar Antecipação"
            
            # Sincronização inteligente com o banco remoto
            if df_banco is not None and not df_banco.empty:
                df_banco['chave'] = df_banco['Ordem Carga'].astype(str) + "_" + df_banco['Nº Nota'].astype(str)
                df_novo['chave'] = df_novo['Ordem Carga'].astype(str) + "_" + df_novo['Nº Nota'].astype(str)
                
                novas_linhas = df_novo[~df_novo['chave'].isin(df_banco['chave'])]
                df_final = pd.concat([df_banco, novas_linhas], ignore_index=True).drop(columns=['chave'], errors='ignore')
            else:
                df_final = df_novo
                
            if st.button("💾 Gravar Novas Cargas no Sistema Compartilhado"):
                with st.spinner("Sincronizando com o GitHub..."):
                    sucesso = salvar_dados_github(df_final, current_sha)
                    if sucesso:
                        st.success("Novas cargas integradas com sucesso!")
                        st.rerun()
                    else:
                        st.error("Erro ao salvar no repositório. Verifique as configurações do Token.")
                        
    except Exception as e:
        st.error(f"Erro crítico no processamento do arquivo: {e}")

# Exibição do painel se houver dados salvos
if df_banco is not None and not df_banco.empty:
    st.markdown("---")
    
    def identificar_rede(cliente):
        cliente_upper = str(cliente).upper()
        if "MUFFATO" in cliente_upper: return "Muffato"
        elif "ATACADAO" in cliente_upper or "ATACADÃO" in cliente_upper: return "Atacadão"
        elif "ASSAI" in cliente_upper or "ASSAÍ" in cliente_upper: return "Assaí"
        return "Outros"
        
    if 'Cliente' in df_banco.columns:
        df_banco['Rede'] = df_banco['Cliente'].apply(identificar_rede)
    else:
        df_banco['Rede'] = "Outros"
    
    st.sidebar.header("Filtros de Operação")
    redes_disponiveis = df_banco['Rede'].unique().tolist()
    redes_selecionadas = st.sidebar.multiselect("Filtrar por Rede", options=redes_disponiveis, default=redes_disponiveis)
    
    df_filtrado = df_banco[df_banco['Rede'].isin(redes_selecionadas)]
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total de Cargas", len(df_filtrado))
    if 'Tem Antecipação?' in df_filtrado.columns:
        col2.metric("Antecipações Críticas", len(df_filtrado[df_filtrado['Tem Antecipação?'] == "⚠️ Solicitar Antecipação"]))
    if 'Confirmado' in df_filtrado.columns:
        col3.metric("Confirmados", len(df_filtrado[df_filtrado['Confirmado'] == "Confirmado"]))
    if 'E-mail enviado ao OPL' in df_filtrado.columns:
        col4.metric("E-mails Enviados", len(df_filtrado[df_filtrado['E-mail enviado ao OPL'] == True]))
    
    st.subheader("📋 Tabela Interativa de Agendamentos")
    
    colunas_exibicao = [
        'Ordem Carga', 'Cliente', 'Rede', 'Nº Nota', 'Obs. Logística', 
        'Tem Antecipação?', 'Agendado Para', 'Confirmado', 'E-mail enviado ao OPL'
    ]
    df_exibir = df_filtrado[[c for c in colunas_exibicao if c in df_filtrado.columns]].copy()
    
    if 'E-mail enviado ao OPL' in df_exibir.columns:
        df_exibir['E-mail enviado ao OPL'] = df_exibir['E-mail enviado ao OPL'].astype(bool)

    edited_df = st.data_editor(
        df_exibir,
        column_config={
            "E-mail enviado ao OPL": st.column_config.CheckboxColumn("E-mail OPL?", default=False),
            "Confirmado": st.column_config.SelectboxColumn("Status Janela", options=["Pendente", "Aguardando Portal", "Confirmado", "Reagenda"], required=True),
            "Agendado Para": st.column_config.TextColumn("Agendado Para (Data/Hora)"),
            "Tem Antecipação?": st.column_config.TextColumn("Status Antecipação", disabled=True)
        },
        disabled=[c for c in ["Ordem Carga", "Cliente", "Rede", "Nº Nota", "Obs. Logística"] if c in df_exibir.columns],
        hide_index=True,
        use_container_width=True,
        key="editor_global"
    )
    
    if st.button("🚀 Salvar Alterações da Tabela para a Equipe"):
        df_banco.update(edited_df)
        with st.spinner("Sincronizando alterações..."):
            sucesso = salvar_dados_github(df_banco, current_sha)
            if sucesso:
                st.success("Alterações salvas e compartilhadas!")
                st.rerun()
            else:
                st.error("Erro ao salvar alterações no banco remoto.")
else:
    st.info("O banco de dados está pronto e vazio. Por favor, faça o upload de um relatório acima para iniciar.")
