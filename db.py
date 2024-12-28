import sqlite3

# Conexão SQLite
def create_connection():
    try:
        connection = sqlite3.connect("bdservicedesk.db")
        connection.row_factory = sqlite3.Row  # Retorna resultados como dicionário
        print("Conexão SQLite foi bem-sucedida!")
        return connection
    except Exception as e:
        print(f"Erro na conexão SQLite: {e}")
        return None