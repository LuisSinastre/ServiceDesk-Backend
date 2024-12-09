import sqlite3

def create_and_populate_table():
    # Conexão com o banco SQLite
    connection = sqlite3.connect("bdservicedesk.db")
    cursor = connection.cursor()

    # Criar a tabela
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS chamados (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cargo TEXT NOT NULL,
            tipo_de_chamado TEXT NOT NULL,
            submotivo TEXT NOT NULL,
            detalhamento TEXT NOT NULL,
            aprovador TEXT NOT NULL,
            tratamento TEXT NOT NULL
        )
    """)

    # Dados para serem adicionados
    data = [
        ("SUPERVISOR", "SOLICITAÇÃO", "MANUTENÇÃO", "HEADSET COM DEFEITO", "FIELD SERVICE", "FIELDSERVICE"),
        ("GERENTE", "SOLICITAÇÃO", "MANUTENÇÃO", "HEADSET COM DEFEITO", "FIELD SERVICE", "FIELDSERVICE")
    ]

    # Inserir dados
    cursor.executemany("""
        INSERT INTO chamados (cargo, tipo_de_chamado, submotivo, detalhamento, aprovador, tratamento)
        VALUES (?, ?, ?, ?, ?, ?)
    """, data)

    # Confirmar transações
    connection.commit()

    # Fechar a conexão
    connection.close()
    print("Tabela criada e dados populados com sucesso!")

# Executar a função
create_and_populate_table()
