import sqlite3

# Conectar ao banco de dados SQLite
conn = sqlite3.connect("bdservicedesk.db")
cursor = conn.cursor()

# Criar tabela pages_roles
cursor.execute("""
CREATE TABLE IF NOT EXISTS pages_roles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cargo TEXT NOT NULL,
    pagina_permitida TEXT NOT NULL,
    id_pagina INTEGER NOT NULL
)
""")

# Inserir dados fornecidos
dados = [
    ("GERENTE", "ABERTURA", 1),
    ("GERENTE", "CONSULTA", 2),
    ("GERENTE", "CADASTRO", 3),
    ("ANALISTA", "ABERTURA", 1),
    ("ANALISTA", "CONSULTA", 2),
    ("ANALISTA", "TRATAMENTO", 4),
    ("DEMAIS", "ABERTURA", 1),
    ("DEMAIS", "CONSULTA", 2),
]

# Inserir dados no banco
cursor.executemany("""
INSERT INTO pages_roles (cargo, pagina_permitida, id_pagina) 
VALUES (?, ?, ?)
""", dados)

# Confirmar alterações
conn.commit()
print("Tabela criada e dados inseridos com sucesso!")

# Fechar conexão
conn.close()
