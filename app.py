from flask import Flask, jsonify, request
import sqlite3
import jwt
import datetime
import os
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash, check_password_hash
from flask_cors import CORS
import json


# Carregar variáveis de ambiente do arquivo .env
load_dotenv('config.env')

app = Flask(__name__)

# Configuração de CORS
CORS(app)

# Definir chave secreta a partir do .env ou diretamente no código
secret = app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')


# Conexão SQLite
def create_connection():
    """
    Função responsável por criar conexão com SQLite.
    Retorna a conexão ou None em caso de falha.
    """
    try:
        connection = sqlite3.connect("bdservicedesk.db")
        connection.row_factory = sqlite3.Row  # Retorna resultados como dicionário
        print("Conexão SQLite foi bem-sucedida!")
        return connection
    except Exception as e:
        print(f"Erro na conexão SQLite: {e}")
        return None


def decode_token(token):
    try:
        decoded = jwt.decode(token, secret, algorithms=["HS256"])
        # Retornar os dados no mesmo dicionário
        user_id = int(decoded.get("sub"))
        cargo = decoded.get("cargo")
        return user_id, cargo
    except jwt.InvalidTokenError:
        print("Token inválido ou erro na decodificação")
        return None



# Endpoint para autenticar o login
@app.route('/login', methods=['POST'])
def authenticate_user():
    data = request.get_json()

    # Verificação dos dados fornecidos
    if not data.get('username') or not data.get('password'):
        return jsonify({"error": "Usuário e senha são obrigatórios"}), 400

    connection = create_connection()
    if not connection:
        return jsonify({"error": "Não foi possível conectar com o banco"}), 500

    try:
        cursor = connection.cursor()

        # Consultar o usuário pelo nome de usuário
        cursor.execute("SELECT * FROM users WHERE usuario = ?", (data['username'],))
        user = cursor.fetchone()

        if not user:
            return jsonify({"error": "Usuário não encontrado"}), 404

        # Verificar se a senha fornecida está correta
        if not check_password_hash(user['senha'], data['password']):
            return jsonify({"error": "Senha incorreta"}), 401

        # Recuperar permissões com base no cargo
        cursor.execute("""
            SELECT id_pagina
            FROM pages_roles
            WHERE cargo = ?
        """, (user['cargo'],))
        permissions = cursor.fetchall()

        # Apenas retornar os ids das permissões
        permission_ids = [permission['id_pagina'] for permission in permissions]

        # Gerar token JWT
        token = jwt.encode({
            "sub": user['usuario'],
            "nome": user['nome'],
            "cargo": user['cargo'],
            "ids": permission_ids,  # Apenas os IDs das permissões
            "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=1)
        }, app.config['SECRET_KEY'], algorithm="HS256")

        return jsonify({
            "message": "Autenticação bem-sucedida",
            "token": token,
        }), 200

    except Exception as e:
        return jsonify({"error": f"Erro ao autenticar o usuário: {e}"}), 500
    finally:
        connection.close()



# Endpoint para adicionar um novo cargo em pages_roles
@app.route('/pagesroles', methods=['POST'])
def add_page_role():
    data = request.get_json()

    # Verificação dos dados
    if not data.get('cargo') or not data.get('id_pagina') or not data.get('pagina_permitida'):
        return jsonify({"error": "Todos os campos são obrigatórios"}), 400

    connection = create_connection()
    if not connection:
        return jsonify({"error": "Não foi possível conectar com o banco"}), 500

    try:
        cursor = connection.cursor()

        # Verificar se o usuário já existe
        cursor.execute("SELECT cargo FROM pages_roles WHERE id_pagina = ?", (data['id_pagina'],))
        if cursor.fetchone():
            return jsonify({"error": "Página já cadastrada para esse cargo"}), 400

        # Insere os dados do usuário
        cursor.execute("""
            INSERT INTO pages_roles (cargo, id_pagina, pagina_permitida)
            VALUES (?, ?, ?)
            """, (data['cargo'], data['id_pagina'], data['pagina_permitida']))
        connection.commit()

        return jsonify({"message": "Permissão adicionada com sucesso"}), 201

    except Exception as e:
        return jsonify({"error": f"Erro ao adicionar a permissão: {e}"}), 500
    finally:
        connection.close()


# Endpoint para o BD de páginas disponíveis
@app.route('/pagesroles', methods=['GET'])
def get_pages():
    connection = create_connection()
    if not connection:
        return jsonify({"error": "Não foi possível se conectar com o banco"}), 500
    try:
        cursor = connection.cursor()

        # Consultando os dados
        cursor.execute("SELECT * FROM pages_roles")
        pages_roles = cursor.fetchall()

        response = jsonify([dict(role) for role in pages_roles])
        response.headers.add('Content-Type', 'application/json; charset=utf-8')
        return response
    except Exception as e:
        return jsonify({"error": f"Erro ao consultar as permissões: {e}"}), 500
    finally:
        connection.close()



# Endpoint para listar usuários
@app.route('/users', methods=['GET'])
def get_users():
    connection = create_connection()
    if not connection:
        return jsonify({"error": "Não foi possível se conectar com o banco"}), 500
    try:
        cursor = connection.cursor()

        # Consultando os dados
        cursor.execute("SELECT * FROM users")
        users = cursor.fetchall()

        # Garantir que os dados sejam retornados com caracteres especiais corretamente
        response = jsonify([dict(user) for user in users])
        response.headers.add('Content-Type', 'application/json; charset=utf-8')
        return response
    except Exception as e:
        return jsonify({"error": f"Erro ao consultar os usuários: {e}"}), 500
    finally:
        connection.close()


# Endpoint para adicionar um novo usuário
@app.route('/users', methods=['POST'])
def add_user():
    data = request.get_json()

    # Verificação dos dados
    if not data.get('usuario') or not data.get('senha') or not data.get('nome') or not data.get('cargo') or not data.get('superior'):
        return jsonify({"error": "Todos os campos são obrigatórios"}), 400

    connection = create_connection()
    if not connection:
        return jsonify({"error": "Não foi possível conectar com o banco"}), 500

    try:
        cursor = connection.cursor()

        # Verificar se o usuário já existe
        cursor.execute("SELECT usuario FROM users WHERE usuario = ?", (data['usuario'],))
        if cursor.fetchone():
            return jsonify({"error": "Usuário já cadastrado"}), 400

        # Gerar o hash da senha
        hashed_password = generate_password_hash(data['senha'])

        # Insere os dados do usuário
        cursor.execute("""
            INSERT INTO users (usuario, senha, nome, cargo, superior)
            VALUES (?, ?, ?, ?, ?)
        """, (data['usuario'], hashed_password, data['nome'], data['cargo'], data['superior']))
        connection.commit()

        return jsonify({"message": "Usuário adicionado com sucesso"}), 201

    except Exception as e:
        return jsonify({"error": f"Erro ao adicionar o usuário: {e}"}), 500
    finally:
        connection.close()


# Endpoint para excluir um usuário pelo usuário
@app.route('/users/<string:usuario>', methods=['DELETE'])
def delete_user(usuario):
    connection = create_connection()
    if not connection:
        return jsonify({"error": "Não foi possível se conectar com o banco"}), 500

    try:
        cursor = connection.cursor()

        # Verificar se o usuário existe
        cursor.execute("SELECT usuario FROM users WHERE usuario = ?", (usuario,))
        if not cursor.fetchone():
            return jsonify({"error": "Usuário não encontrado"}), 404

        # Excluir o usuário
        cursor.execute("DELETE FROM users WHERE usuario = ?", (usuario,))
        connection.commit()

        return jsonify({"message": f"Usuário {usuario} excluído com sucesso"}), 200

    except Exception as e:
        return jsonify({"error": f"Erro ao excluir o usuário: {e}"}), 500
    finally:
        connection.close()






# Essa parte aqui eu vou deixar destinada para chamadas ao backend durante a navegação, por exemplo, pegar os chamados que o usuário pode abrir.
# Endpoint para retornar todos os chamados disponíveis
@app.route('/ticket_types', methods=['GET'])
def get_chamados():
    # Obter o token no cabeçalho
    token = request.headers.get("Authorization")
    if not token:
        print("Nenhum token no cabeçalho")
        return jsonify({"error": "Token não fornecido"}), 401

    # Limpar o token do formato 'Bearer' e decodificar
    token = token.replace("Bearer ", "")
    print("Token limpo:", token)

    decoded_token = decode_token(token)  # Recuperando os dados do token
    print("Decoded token:", decoded_token)

    if not decoded_token:
        print("Erro ao validar token")
        return jsonify({"error": "Token inválido ou expirado"}), 401

    user_id, cargo = decoded_token  # Destructuring da tupla
    print("User ID:", user_id)
    print("Cargo extraído do token:", cargo)

    # Criar conexão com banco
    connection = create_connection()
    if not connection:
        print("Falha ao conectar com o banco")
        return jsonify({"error": "Não foi possível se conectar com o banco"}), 500

    try:
        cursor = connection.cursor()
        cursor.execute("SELECT id, tipo_chamado, submotivo, formulario FROM ticket_types WHERE cargo = ?", (cargo,))
        chamados = cursor.fetchall()
        
        print("Resultados da consulta ao banco:", chamados)

        dados_retornados = []
        for chamado in chamados:
            try:
                formulario_dados = json.loads(chamado[3]) if chamado[3] else {}
            except json.JSONDecodeError as e:
                print("Erro ao processar JSON:", e)
                formulario_dados = {}

            dados_retornados.append({
                "id": chamado[0],
                "tipo_chamado": chamado[1],
                "submotivo": chamado[2],
                "formulario": formulario_dados
            })

        print("Dados preparados para resposta:", dados_retornados)

        return jsonify(dados_retornados), 200

    except Exception as e:
        print("Erro ao buscar chamados:", e)
        return jsonify({"error": f"Erro ao buscar chamados: {e}"}), 500

    finally:
        connection.close()
        print("Conexão com banco fechada")




# Abrir um chamado
@app.route('/open_ticket', methods=['POST'])
def open_ticket():
    # Obter o token no cabeçalho
    token = request.headers.get("Authorization")
    if not token:
        print("Nenhum token no cabeçalho")
        return jsonify({"error": "Token não fornecido"}), 401

    # Limpar o token do formato 'Bearer' e decodificar
    token = token.replace("Bearer ", "")
    print("Token limpo:", token)

    decoded_token = decode_token(token)  # Recuperando os dados do token
    print("Decoded token:", decoded_token)

    if not decoded_token:
        print("Erro ao validar token")
        return jsonify({"error": "Token inválido ou expirado"}), 401

    # Destructuring da tupla retornada
    user_id, cargo = decoded_token
    print("User ID:", user_id)
    print("Cargo extraído do token:", cargo)

    # Obter dados do formulário da requisição
    data = request.get_json()
    ticket_type = data.get('ticket_type')
    submotivo = data.get('submotivo')
    form = json.dumps(data.get('form'))

    # Criar conexão com banco
    connection = create_connection()
    if not connection:
        return jsonify({"error": "Não foi possível se conectar com o banco"}), 500

    try:
        cursor = connection.cursor()
        
        # Definição do status de chamado aberto ao abrir o chamado
        ticket_status = "Aberto"
        ticket_open_date_time = current_datetime = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")

        # Inserir chamado no banco com o ID do usuário
        cursor.execute(
            "INSERT INTO tickets (ticket_type, submotive, form, user, ticket_status, ticket_open_date_time) VALUES (?, ?, ?, ?, ?, ?)",
            (ticket_type, submotivo, form, user_id, ticket_status, ticket_open_date_time)
        )
        connection.commit()

        # Obter o número do chamado recém-criado
        ticket_number = cursor.lastrowid

        return jsonify({"message": "Chamado aberto com sucesso", "ticket_number": ticket_number}), 201

    except Exception as e:
        print("Erro ao abrir chamado:", e)
        return jsonify({"error": f"Erro ao abrir chamado: {e}"}), 500

    finally:
        connection.close()

        


# Listar os chamados abertos
@app.route('/list_tickets', methods=['GET'])
def list_tickets():
    try:
        # Obter o token no cabeçalho
        token = request.headers.get("Authorization")
        if not token:
            return jsonify({"error": "Token não fornecido"}), 401

        # Limpar o token e validar
        token = token.replace("Bearer ", "")
        decoded_token = decode_token(token)
        
        if not decoded_token:
            return jsonify({"error": "Token inválido ou expirado"}), 401

        user_id = decoded_token[0]  # Obter o user_id do token
        connection = create_connection()
        if not connection:
            return jsonify({"error": "Não foi possível se conectar com o banco"}), 500

        # Obter o termo de busca (query string)
        search_query = request.args.get("search", "").strip()

        sql_query = "SELECT ticket_number, ticket_type, submotive, form FROM tickets WHERE user = ?"
        params = [user_id]

        if search_query:
            sql_query += " AND (ticket_number = ? OR ticket_type LIKE ? OR submotive LIKE ?)"
            params.extend([search_query, f"%{search_query}%", f"%{search_query}%"])

        cursor = connection.cursor()
        cursor.execute(sql_query, params)

        tickets = cursor.fetchall()
        return jsonify([
            {
                "ticket_number": ticket[0],
                "ticket_type": ticket[1],
                "submotive": ticket[2],
                "form": json.loads(ticket[3]) if ticket[3] else {}
            } for ticket in tickets
        ]), 200

    except Exception as e:
        print("Erro ao listar os chamados:", e)
        return jsonify({"error": "Erro interno no servidor"}), 500
    finally:
        connection.close()





# Endpoint para detalhemnto do ticket
@app.route('/ticket_detail/<int:ticket_number>', methods=['GET'])
def ticket_detail(ticket_number):
    try:
        # Obter o token no cabeçalho
        token = request.headers.get("Authorization")
        if not token:
            return jsonify({"error": "Token não fornecido"}), 401

        # Limpar o token e validar
        token = token.replace("Bearer ", "")
        decoded_token = decode_token(token)
        
        if not decoded_token:
            return jsonify({"error": "Token inválido ou expirado"}), 401

        user_id = decoded_token[0]  # Recuperando o ID do usuário
        connection = create_connection()
        
        if not connection:
            return jsonify({"error": "Erro ao conectar com o banco"}), 500

        # Buscar detalhes do chamado pelo ticket_number
        cursor = connection.cursor()
        cursor.execute("SELECT * FROM tickets WHERE ticket_number = ? AND user = ?", (ticket_number, user_id))
        ticket = cursor.fetchone()

        if not ticket:
            return jsonify({"error": "Chamado não encontrado ou acesso negado"}), 404

        # Retornar os detalhes
        ticket_data = {
            "ticket_number": ticket[0],
            "ticket_type": ticket[1],
            "submotive": ticket[2],
            "form": json.loads(ticket[3]),
            "user": ticket[4],
            "ticket_status": ticket[5],
            "ticket_open_date_time": ticket[6]
        }
        return jsonify(ticket_data), 200
    except Exception as e:
        print("Erro ao buscar detalhes do chamado:", e)
        return jsonify({"error": "Erro interno no servidor"}), 500
    finally:
        connection.close()









if __name__ == "__main__":
    app.run(debug=True)
