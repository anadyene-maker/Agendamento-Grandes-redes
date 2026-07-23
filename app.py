import streamlit as st
import pandas as pd
import requests
import base64
import io
import smtplib
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Configuração da página
st.set_page_config(page_title="Controle de Agendamentos Logísticos", layout="wide")

# Mapeamento de e-mails dos Operadores
EMAILS_OPERADORES = {
    "CARRARO ARMAZENS GERAIS LTDA": "logistica@carraro.com.br",
    "J. LOBO": "agendamento@jlobo.com.br",
    "CARRARO": "logistica@carraro.com.br",
    "J.LOBO": "agendamento@jlobo.com.br"
}

# 🎭 ESTILIZAÇÃO E IMPRESSÃO
st.markdown("""
    <style>
    div[data-testid="stDataFrame"] input[type="checkbox"]:checked {
        background-color: #28a745 !important;
        border-color: #28a745 !important;
    }
    @media print {
        section[data-testid="stSidebar"], .stFileUploader, .stButton, 
        div[data-testid="stDataFrame"], h3, hr, div:has(> input[type="checkbox"]) {
            display: none !important;
        }
        .main .block-container { padding-top: 1rem !important; padding-bottom: 1rem !important; }
    }
    </style>
""", unsafe_allow_html=True)

st.title("🚚 Controle de Agendamentos Logísticos")

# Configurações do Repositório via Secrets
GITHUB_TOKEN = st.secrets.get("GITHUB_TOKEN", "")
REPO = "anadyene-maker/Agendamento-Grandes-redes"
FILE_PATH = "base_dados_agendamentos.csv"
URL = f"https://api.github.com/repos/{REPO}/contents/{FILE_PATH}"
headers = {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"}

# 🛠️ FUNÇÃO PARA LIMPAR NÚMEROS (TIRAR O .0)
def limpar_inteiro(valor):
    if pd.isna(valor) or str(valor).strip() in ['', 'nan', 'None']:
        return ""
    try:
        val_str = str(valor).split('.')[0].strip()
        return val_str
    except:
        return str(valor).strip()

# 📧 FUNÇÃO PARA ENVIAR E-MAIL VIA SMTP
def enviar_email_opl(destinatario, dados_carga):
    try:
        remetente = st.secrets["email"]["user"]
        senha = st.secrets["email"]["password"]
        server_smtp = st.secrets["email"]["smtp_server"]
        porta_smtp = int(st.secrets["email"]["smtp_port"])
        
        msg = MIMEMultipart()
        msg['From'] = remetente
        msg['To'] = destinatario
        msg['Subject'] = f"📢 CONFIRMAÇÃO DE AGENDAMENTO - NOTA FISCAL {dados_carga.get('Nº Nota', '')}"
        
        corpo = f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <p>Prezada equipe de Logística,</p>
            <p>Confirmamos o agendamento da carga abaixo e solicitamos a programação do carregamento/entrega:</p>
            <table style="border-collapse: collapse; width: 100%; max-width: 600px; margin: 20px 0;">
                <tr style="background-color: #f2f2f2;"><td style="padding: 8px; border: 1px solid #ddd; font-weight: bold;">Cliente/Rede:</td><td style="padding: 8px; border: 1px solid #ddd;">{dados_carga.get('Cliente', '')}</td></tr>
                <tr><td style="padding: 8px; border: 1px solid #ddd; font-weight: bold;">Nº Nota Fiscal:</td><td style="padding: 8px; border: 1px solid #ddd;">{dados_carga.get('Nº Nota', '')}</td></tr>
                <tr style="background-color: #f2f2f2;"><td style="padding: 8px; border: 1px solid #ddd; font-weight: bold;">Ordem de Carga:</td><td style="padding: 8px; border: 1px solid #ddd;">{dados_carga.get('Ordem Carga', '')}</td></tr>
                <tr><td style="padding: 8px; border: 1px solid #ddd; font-weight: bold;">Data/Hora Agendada:</td><td style="padding: 8px; border: 1px solid #ddd; color: #d9534f; font-weight: bold;">{dados_carga.get('Data Agendamento', '')}</td></tr>
                <tr style="background-color: #f2f2f2;"><td style="padding: 8px; border: 1px solid #ddd; font-weight: bold;">Obs. Logística:</td><td style="padding: 8px; border: 1px solid #ddd;">{dados_carga.get('Obs. Logística', '')}</td></tr>
            </table>
            <p><em>Por favor, considerem este e-mail como a validação oficial da agenda.</em></p>
            <br>
            <p>Atenciosamente,<br><strong>Torre de Controle Logístico</strong></p>
        </body>
        </html>
        """
        msg.attach(MIMEText(corpo, 'html'))
        
        if porta_smtp == 465:
            server = smtplib.SMTP_SSL(server_smtp, porta_smtp, timeout=10)
        else:
            server = smtplib.SMTP(server_smtp, porta_smtp, timeout=10)
            server.starttls()
            
        server.login(remetente, senha)
        server.sendmail(remetente, destinatario, msg.as_string())
        server.quit()
        return True
    except Exception as e:
        st.error(f"❌ Erro ao tentar enviar o e-mail: {e}")
        return False

# Funções GitHub
def salvar_dados_github(df_salvar, sha=None):
    csv_string = df_salvar.to_csv(index=False, sep=';')
    content_b64 = base64.b64encode(csv_string.encode('utf-8')).decode('utf-8')
    data = {"message": "Atualização via Streamlit", "content": content_b64}
    if sha: data["sha"] = sha
    return requests.put(URL, headers=headers, json=data).status_code in [200, 201]

def carregar_dados_github():
    try:
        response = requests.get(URL, headers=headers)
        if response.status_code == 200:
            content = response.json()
            sha = content.get('sha')
            csv_data = base64.b64decode(content['content']).decode('utf-8', errors='ignore')
            if not csv_data.strip():
                return pd.DataFrame(), sha
            
            try:
                df = pd.read_csv(io.StringIO(csv_data), sep=';', dtype=str)
                if len(df.columns) <= 1:
                    df = pd.read_csv(io.StringIO(csv_data), sep=',', dtype=str)
            except:
                df = pd.read_csv(io.StringIO(csv_data), sep=',', dtype=str)
                
            df.columns = df.columns.str.strip()
            return df, sha
        else:
            return pd.DataFrame(), None
    except Exception as e:
        st.error(f"Erro na conexão com GitHub: {e}")
        return pd.DataFrame(), None

df_banco, current_sha = carregar_dados_github()

# 🔐 CONTROLE DE ACESSO COM SENHA
st.sidebar.markdown("### 🔑 Controle de Acesso")
senha_input = st.sidebar.text_input("Digite a senha de editor:", type="password")

# 💡 ALTERE A SENHA NA LINHA ABAIXO CASO PREFIRA OUTRA
SENHA_CORRETA = "1234"
modo_editor = (senha_input == SENHA_CORRETA)

if modo_editor:
    st.sidebar.success("🔓 Modo Editor Ativado")
elif senha_input != "":
    st.sidebar.error("❌ Senha incorreta")

# 📥 SEÇÃO DE UPLOAD OPCIONAL NO MODO EDITOR
if modo_editor:
    with st.expander("📥 Deseja mesclar uma nova planilha do Sankhya? (Opcional)"):
        uploaded_file = st.file_uploader("Arraste a planilha do Sankhya (Excel ou CSV)", type=["xlsx", "csv"])
        if uploaded_file:
            try:
                df_raw = pd.read_csv(uploaded_file, header=None, sep=None, engine='python', dtype=str) if uploaded_file.name.lower().endswith('.csv') else pd.read_excel(uploaded_file, header=None, dtype=str)
                linha_cabecalho = next((idx for idx, row in df_raw.iterrows() if any("Nº Nota" in str(s) or "Ordem Carga" in str(s) for s in row)), 0)
                uploaded_file.seek(0)
                df_novo = pd.read_csv(uploaded_file, skiprows=linha_cabecalho, sep=None, engine='python', dtype=str) if uploaded_file.name.lower().endswith('.csv') else pd.read_excel(uploaded_file, skiprows=linha_cabecalho, dtype=str)
                df_novo.columns = df_novo.columns.str.strip()
                
                for col, default in {'Fase do Agendamento': 'Pendente', 'Pedido de Antecipação': '', 'Antecipado': False, 'E-mail enviado ao OPL': False}.items():
                    if col not in df_novo.columns: df_novo[col] = default

                if df_banco is not None and not df_banco.empty:
                    df_banco['Nº Nota'] = df_banco['Nº Nota'].apply(limpar_inteiro)
                    df_novo['Nº Nota'] = df_novo['Nº Nota'].apply(limpar_inteiro)
                    df_final = pd.concat([df_banco, df_novo[~df_novo['Nº Nota'].isin(df_banco['Nº Nota'])]], ignore_index=True)
                else:
                    df_final = df_novo

                if st.button("💾 Mesclar e Atualizar no GitHub"):
                    if salvar_dados_github(df_final, current_sha):
                        st.success("Dados integrados com sucesso no GitHub!")
                        st.rerun()
            except Exception as e: 
                st.error(f"Erro ao processar planilha: {e}")

# 📊 EXIBIÇÃO E FILTROS
if df_banco is None or df_banco.empty:
    st.info("ℹ️ O banco de dados no GitHub está vazio ou não foi encontrado.")
else:
    for col, default in {'Fase do Agendamento': 'Pendente', 'Pedido de Antecipação': '', 'Antecipado': False, 'E-mail enviado ao OPL': False, 'Obs. Logística': ''}.items():
        if col not in df_banco.columns:
            df_banco[col] = default

    for col_num in ['Nº Nota', 'Ordem Carga', 'Obs. Logística']:
        if col_num in df_banco.columns:
            df_banco[col_num] = df_banco[col_num].apply(limpar_inteiro)

    if 'Operador Logístico' not in df_banco.columns:
        df_banco['Operador Logístico'] = df_banco['Logística Ent.'] if 'Logística Ent.' in df_banco.columns else (df_banco['Transportadora'] if 'Transportadora' in df_banco.columns else "Não Informado")
    df_banco['Operador Logístico'] = df_banco['Operador Logístico'].fillna("Não Informado").astype(str).str.strip()
    
    st.sidebar.markdown("### 🔍 Filtros de Operação")
    opls_selecionados = st.sidebar.multiselect("Filtrar por Operador", options=df_banco['Operador Logístico'].unique().tolist(), default=df_banco['Operador Logístico'].unique().tolist())
    df_filtrado = df_banco[df_banco['Operador Logístico'].isin(opls_selecionados)].copy()
    
    if 'Cliente' in df_filtrado.columns:
        clientes_selecionados = st.sidebar.multiselect("Filtrar por Cliente", options=df_filtrado['Cliente'].dropna().unique().tolist(), default=df_filtrado['Cliente'].dropna().unique().tolist())
        df_filtrado = df_filtrado[df_filtrado['Cliente'].isin(clientes_selecionados)].copy()
        
    df_filtrado['E-mail enviado ao OPL'] = df_filtrado['E-mail enviado ao OPL'].map({'True': True, 'False': False, True: True, False: False}).fillna(False).astype(bool)
    df_filtrado['Antecipado'] = df_filtrado['Antecipado'].map({'True': True, 'False': False, True: True, False: False}).fillna(False).astype(bool)
    
    for col in ['Pedido de Antecipação', 'Data Agendamento', 'Obs. Logística', 'Ordem Carga', 'Nº Nota']:
        if col in df_filtrado.columns: df_filtrado[col] = df_filtrado[col].fillna("").astype(str)

    opcoes_permitidas = ["Pendente", "Solicitado no Portal", "Confirmado", "Reagenda"]
    df_filtrado['Fase do Agendamento'] = df_filtrado['Fase do Agendamento'].fillna("Pendente").astype(str).str.strip()

    # Indicadores
    st.markdown("---")
    m1, m2, m3 = st.columns(3)
    m1.metric("📦 Total de Cargas Monitoradas", len(df_filtrado))
    m2.metric("⚠️ Antecipações Solicitadas", f"{df_filtrado['Antecipado'].sum()} pedidas")
    m3.metric("✅ Agendamentos Confirmados", (df_filtrado['Fase do Agendamento'] == "Confirmado").sum())
    
    st.markdown("---")
    st.subheader("📋 Painel de Controle Operacional")
    
    # 📅 PREENCHIMENTO RÁPIDO DE DATA (LIBERADO APENAS COM SENHA)
    if modo_editor:
        col_dt1, col_dt2 = st.columns([2, 4])
        with col_dt1:
            data_selecionada = st.date_input("📅 Preencher Data de Agendamento em Massa:", datetime.now())
        with col_dt2:
            st.write("")
            st.write("")
            if st.button("⚡ Aplicar Data nas Cargas Filtradas"):
                data_formatada = data_selecionada.strftime("%d/%m")
                notas_filtradas = df_filtrado['Nº Nota'].tolist()
                df_banco.loc[df_banco['Nº Nota'].isin(notas_filtradas), 'Data Agendamento'] = data_formatada
                if salvar_dados_github(df_banco, current_sha):
                    st.toast(f"Data {data_formatada} aplicada em {len(notas_filtradas)} cargas!", icon="✅")
                    st.rerun()

    # 📌 ORDEM FIXA DAS COLUNAS
    ordem_fixa_colunas = [
        'Nº Nota', 
        'Cliente', 
        'Operador Logístico', 
        'Fase do Agendamento', 
        'Data Agendamento', 
        'Obs. Logística', 
        'Pedido de Antecipação', 
        'Antecipado', 
        'E-mail enviado ao OPL', 
        'Ordem Carga'
    ]
    
    colunas_presentes = [c for c in ordem_fixa_colunas if c in df_filtrado.columns]
    df_exibir = df_filtrado[colunas_presentes]

    edited_df = st.data_editor(
        df_exibir,
        column_order=colunas_presentes,
        column_config={
            "Nº Nota": st.column_config.TextColumn("Nº Nota", disabled=True),
            "Cliente": st.column_config.TextColumn("Cliente", disabled=True),
            "Operador Logístico": st.column_config.TextColumn("Operador Logístico", disabled=True),
            "Fase do Agendamento": st.column_config.SelectboxColumn("Fase do Agendamento", options=opcoes_permitidas, required=True, disabled=not modo_editor),
            "Data Agendamento": st.column_config.TextColumn("Data Agendamento", disabled=not modo_editor),
            "Obs. Logística": st.column_config.TextColumn("Obs. Logística", disabled=not modo_editor),
            "Pedido de Antecipação": st.column_config.TextColumn("Pedido de Antecipação", disabled=not modo_editor),
            "Antecipado": st.column_config.CheckboxColumn("Antecipado?", disabled=not modo_editor),
            "E-mail enviado ao OPL": st.column_config.CheckboxColumn("E-mail OPL?", disabled=not modo_editor),
            "Ordem Carga": st.column_config.TextColumn("Ordem Carga", disabled=True)
        },
        hide_index=True, use_container_width=True, key="editor_fases_v23"
    )
    
    if modo_editor:
        if st.button("🚀 Salvar Alterações e Enviar E-mails"):
            with st.spinner("Processando alterações e checando e-mails..."):
                df_banco['Nº Nota'] = df_banco['Nº Nota'].apply(limpar_inteiro)
                edited_df['Nº Nota'] = edited_df['Nº Nota'].apply(limpar_inteiro)
                
                for idx, row in edited_df.iterrows():
                    nota = row['Nº Nota']
                    nova_fase = row['Fase do Agendamento']
                    
                    idx_banco = df_banco[df_banco['Nº Nota'] == nota].index
                    if len(idx_banco) > 0:
                        idx_banco = idx_banco[0]
                        email_ja_enviado = df_banco.at[idx_banco, 'E-mail enviado ao OPL']
                        
                        if str(email_ja_enviado).lower() in ['true', '1']: email_ja_enviado = True
                        if str(email_ja_enviado).lower() in ['false', '0']: email_ja_enviado = False
                        
                        if nova_fase == "Confirmado" and not row['E-mail enviado ao OPL'] and not email_ja_enviado:
                            operador = row['Operador Logístico']
                            destinatario_email = EMAILS_OPERADORES.get(operador)
                            
                            if destinatario_email:
                               sucesso_envio = enviar_email_opl(destinatario_email, row)
                               if sucesso_envio:
                                   edited_df.at[idx, 'E-mail enviado ao OPL'] = True
                                   st.toast(f"✉️ E-mail enviado para {operador} (NF {nota})", icon="✅")
                            else:
                               st.warning(f"⚠️ Operador '{operador}' não possui e-mail cadastrado no dicionário do código.")

                for col in edited_df.columns:
                    if col != 'Nº Nota' and col in df_banco.columns:
                        mapeamento = dict(zip(edited_df['Nº Nota'], edited_df[col]))
                        df_banco[col] = df_banco['Nº Nota'].map(mapeamento).fillna(df_banco[col])
                
                if salvar_dados_github(df_banco, current_sha):
                    st.success("Alterações salvas com sucesso!")
                    st.rerun()
    else:
        st.info("💡 Modo de Visualização Ativo.")
