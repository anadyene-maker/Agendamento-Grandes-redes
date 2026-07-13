import streamlit as st
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="Controle de Agendamentos Logísticos", layout="wide")

st.title("🚚 Controle de Agendamentos de Cargas")
st.markdown("Plataforma operacional para monitoramento de janelas e antecipações (Muffato, Atacadão, Assaí)")

# 1. Upload do arquivo do sistema
uploaded_file = st.file_uploader("Arraste aqui o relatório de cargas extraído do sistema", type=["xlsx"])

if uploaded_file:
    # Ler pulando as 2 primeiras linhas conforme estrutura do relatório nativo
    df = pd.read_excel(uploaded_file, skiprows=2)
    
    # Criar colunas operacionais dinâmicas se elas não existirem no arquivo original
    if 'Agendado Para' not in df.columns:
        df['Agendado Para'] = df['Data Agendamento'].fillna("")
    if 'Confirmado' not in df.columns:
        df['Confirmado'] = "Pendente"
    if 'E-mail enviado ao OPL' not in df.columns:
        df['E-mail enviado ao OPL'] = False
    if 'Tem Antecipação?' not in df.columns:
        df['Tem Antecipação?'] = "Não"
        
    # Lógica Automática de Antecipação baseada nas notas de Logística
    for idx, row in df.iterrows():
        obs = str(row.get('Obs. Logística', '')).lower()
        if 'antecipar' in obs or 'portal indeferiu' in obs or 'indefe' in obs:
            df.at[idx, 'Tem Antecipação?'] = "⚠️ Solicitar Antecipação"

    # 2. Filtros na barra lateral
    st.sidebar.header("Filtros de Operação")
    
    # Identificar a Rede automaticamente com base na coluna Cliente
    def identificar_rede(cliente):
        cliente_upper = str(cliente).upper()
        if "MUFFATO" in cliente_upper:
            return "Muffato"
        elif "ATACADAO" in cliente_upper or "ATACADÃO" in cliente_upper:
            return "Atacadão"
        elif "ASSAI" in cliente_upper or "ASSAÍ" in cliente_upper:
            return "Assaí"
        return "Outros"
        
    df['Rede'] = df['Cliente'].apply(identificar_rede)
    
    redes_selecionadas = st.sidebar.multiselect("Filtrar por Rede", options=df['Rede'].unique(), default=df['Rede'].unique())
    df_filtrado = df[df['Rede'].isin(redes_selecionadas)]

    # 3. Painel de Indicadores Rápidos (KPIs)
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total de Cargas", len(df_filtrado))
    col2.metric("Antecipações Críticas", len(df_filtrado[df_filtrado['Tem Antecipação?'] == "⚠️ Solicitar Antecipação"]))
    col3.metric("Confirmados", len(df_filtrado[df_filtrado['Confirmado'] == "Confirmado"]))
    col4.metric("E-mails p/ OPL Enviados", len(df_filtrado[df_filtrado['E-mail enviado ao OPL'] == True]))

    st.markdown("---")
    st.subheader("📋 Tabela Interativa de Agendamentos")
    st.caption("Você pode alterar as colunas 'Agendado Para', 'Confirmado' e 'E-mail enviado ao OPL' diretamente na tabela abaixo:")

    # 4. Configuração das colunas editáveis da planilha na tela
    colunas_exibicao = [
        'Ordem Carga', 'Cliente', 'Rede', 'Nº Nota', 'Obs. Logística', 
        'Tem Antecipação?', 'Agendado Para', 'Confirmado', 'E-mail enviado ao OPL'
    ]
    
    df_exibir = df_filtrado[colunas_exibicao]
    
    edited_df = st.data_editor(
        df_exibir,
        column_config={
            "E-mail enviado ao OPL": st.column_config.CheckboxColumn(
                "E-mail OPL?",
                help="Marque se o e-mail para o operador logístico já foi disparado",
                default=False,
            ),
            "Confirmado": st.column_config.SelectboxColumn(
                "Status Janela",
                options=["Pendente", "Aguardando Portal", "Confirmado", "Reagenda"],
                required=True,
            ),
            "Agendado Para": st.column_config.TextColumn(
                "Agendado Para (Data/Hora)",
                help="Insira a data final confirmada no portal"
            ),
            "Tem Antecipação?": st.column_config.TextColumn(
                "Status Antecipação",
                disabled=True
            )
        },
        disabled=["Ordem Carga", "Cliente", "Rede", "Nº Nota", "Obs. Logística"],
        hide_index=True,
        use_container_width=True
    )
    
    # Botão para exportar o controle do dia atualizado
    st.markdown(" ")
    st.download_button(
        label="📥 Baixar Planilha Atualizada da Dashboard",
        data=edited_df.to_csv(index=False).encode('utf-8'),
        file_name=f"controle_agendamentos_{datetime.now().strftime('%d_%m_%Y')}.csv",
        mime="text/csv",
    )
else:
    st.info("Aguardando o upload do arquivo excel extraído do sistema para montar a dashboard interativa.")
