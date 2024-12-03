from flask import Flask, jsonify, request
import mysql.connector
from mysql.connector import Error
import jwt
import datetime
import os
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash, check_password_hash
from flask_cors import CORS

# Carregar variáveis de ambiente do arquivo .env
load_dotenv('config.env')

app = Flask(__name__)

# Configuração de CORS
CORS(app)

# Definir chave secreta a partir do .env ou diretamente no código
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')

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

# Endpoint para autenticar o login
@app.route('/login', methods=['POST'])
def authenticate_user():
    data = request.get_json()

    # Verificação dos dados fornecidos
    if not data.get('username') or not data.get('password'):
        return jsonify({"error": "Usuário e senha são obrigatórios"}), 400

    # Criar conexão com o banco
    connection = create_connection()
    if not connection:
        return jsonify({"error": "Não foi possível conectar com o banco"}), 500

    try:
        cursor = connection.cursor(dictionary=True)

        # Consultar o usuário pelo RG
        cursor.execute("SELECT * FROM users WHERE usuario = %s", (data['username'],))
        user = cursor.fetchone()

        if not user:
            return jsonify({"error": "Usuário não encontrado"}), 404

        # Verificar se a senha fornecida está correta
        if not check_password_hash(user['senha'], data['password']):
            return jsonify({"error": "Senha incorreta"}), 401

        # Gerar token JWT
        token = jwt.encode({
            "sub": user['usuario'],
            "nome": user['nome'],
            "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=1)
        }, app.config['SECRET_KEY'], algorithm="HS256")

        return jsonify({
            "message": "Autenticação bem-sucedida",
            "token": token
        }), 200

    except Error as e:
        return jsonify({"error": f"Erro ao autenticar o usuário: {e}"}), 500
    finally:
        if connection:
            connection.close()




# Endpoint para adicionar um novo usuário
@app.route('/users', methods=['POST'])
def add_user():
    data = request.get_json()

    # Verificação dos dados
    if not data.get('usuario') or not data.get('senha') or not data.get('nome') or not data.get('cargo') or not data.get('superior'):
        return jsonify({"error": "Todos os campos são obrigatórios"}), 400

    # Criar conexão com o banco
    connection = create_connection()
    if not connection:
        return jsonify({"error": "Não foi possível conectar com o banco"}), 500

    try:
        cursor = connection.cursor()

        # Verificar se o rg já existe
        cursor.execute("SELECT usuario FROM users WHERE usuario = %s", (data['usuario'],))
        if cursor.fetchone():
            return jsonify({"error": "Usuário já cadastrado"}), 400

        # Gerar o hash da senha
        hashed_password = generate_password_hash(data['senha'])

        # Insere os dados do usuário
        query = """
        INSERT INTO users (usuario, senha, nome, cargo, superior)
        VALUES (%s, %s, %s, %s, %s)
        """
        values = (data['usuario'], hashed_password, data['nome'], data['cargo'], data['superior'])

        cursor.execute(query, values)
        connection.commit()

        return jsonify({"message": "Usuário adicionado com sucesso"}), 201

    except Error as e:
        return jsonify({"error": f"Erro ao adicionar o usuário: {e}"}), 500
    finally:
        if connection:
            connection.close()



# Endpoint para excluir um usuário pelo usuario
@app.route('/users/<int:usuario>', methods=['DELETE'])
def delete_user(usuario):
    connection = create_connection()
    if not connection:
        return jsonify({"error": "Não foi possível conectar com o banco"}), 500

    try:
        cursor = connection.cursor()

        # Verificar se o usuário existe
        cursor.execute("SELECT usuario FROM users WHERE usuario = %s", (usuario,))
        user = cursor.fetchone()

        if not user:
            return jsonify({"error": "Usuário não encontrado"}), 404

        # Excluir o usuário
        cursor.execute("DELETE FROM users WHERE usuario = %s", (usuario,))
        connection.commit()

        return jsonify({"message": f"Usuário {usuario} excluído com sucesso"}), 200

    except Error as e:
        return jsonify({"error": f"Erro ao excluir o usuário: {e}"}), 500
    finally:
        if connection:
            connection.close()

if __name__ == "__main__":
    app.run(debug=True)
