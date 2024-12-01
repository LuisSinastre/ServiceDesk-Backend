from flask import Flask, jsonify, request
import mysql.connector
from mysql.connector import Error

app = Flask(__name__)

# Conexão com o banco de dados MySQL
def create_connection():
    try:
        connection = mysql.connector.connect(
            host="localhost",
            user="root",
            password="Sinas@4731",
            database="bdservicedesk",
            charset="utf8mb4"  # Garantir que o charset seja UTF-8
        )
        if connection.is_connected():
            print("Conexão com MySQL foi bem-sucedida!")
            return connection
    except Error as e:
        print(f"Conexão deu pau: {e}")
        return None

# Endpoint para listar usuários
@app.route('/users', methods=['GET'])
def get_users():
    connection = create_connection()
    if not connection:
        return jsonify({"error": "Não foi possível se conectar com o banco"}), 500

    try:
        cursor = connection.cursor(dictionary=True)

        # Garantir que os dados sejam recuperados com o charset correto
        cursor.execute("SET NAMES 'utf8mb4'")  # Definir a codificação UTF-8 para a consulta

        # Consultando os dados
        cursor.execute("SELECT * FROM `bdservicedesk`.`users`")
        users = cursor.fetchall()

        # Garantir que os dados sejam retornados com caracteres especiais corretamente
        response = jsonify(users)
        response.headers.add('Content-Type', 'application/json; charset=utf-8')  # Forçando UTF-8
        return response

    except Error as e:
        return jsonify({"error": f"Erro ao consultar os usuários e detalhes: {e}"}), 500
    finally:
        if connection:
            connection.close()

# Endpoint para adicionar um novo usuário
@app.route('/users', methods=['POST'])
def add_user():
    data = request.get_json()

    # Verificação dos dados
    if not data.get('rg') or not data.get('senha') or not data.get('nome_completo') or not data.get('perfil_acesso') or not data.get('superior_imediato') or not data.get('celula'):
        return jsonify({"error": "Todos os campos são obrigatórios"}), 400

    # Criar conexão com o banco
    connection = create_connection()
    if not connection:
        return jsonify({"error": "Não foi possível conectar com o banco"}), 500

    try:
        cursor = connection.cursor()

        # Verificar se o rg já existe
        cursor.execute("SELECT rg FROM users WHERE rg = %s", (data['rg'],))
        if cursor.fetchone():
            return jsonify({"error": "RG já cadastrado"}), 400

        # Insere os dados do usuário
        query = """
        INSERT INTO users (rg, senha, nome_completo, perfil_acesso, superior_imediato, celula)
        VALUES (%s, %s, %s, %s, %s, %s)
        """
        values = (data['rg'], data['senha'], data['nome_completo'], data['perfil_acesso'], data['superior_imediato'], data['celula'])

        cursor.execute(query, values)
        connection.commit()

        return jsonify({"message": "Usuário adicionado com sucesso"}), 201

    except Error as e:
        return jsonify({"error": f"Erro ao adicionar o usuário: {e}"}), 500
    finally:
        if connection:
            connection.close()

if __name__ == "__main__":
    app.run(debug=True)
