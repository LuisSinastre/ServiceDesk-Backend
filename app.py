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
        # Usando a chave secreta diretamente de app.config
        decoded = jwt.decode(token, app.config['SECRET_KEY'], algorithms=["HS256"])
        
        # Retornar um dicionário com os dados do token
        return {
            "user": int(decoded.get("user")),
            "position": decoded.get("position"),
            "profile": decoded.get("profile")
        }
    
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
        cursor.execute("SELECT * FROM users WHERE user = ?", (data['username'],))
        user = cursor.fetchone()

        if not user:
            return jsonify({"error": "Usuário não encontrado"}), 404

        # Verificar se a senha fornecida está correta
        if not check_password_hash(user['password'], data['password']):
            return jsonify({"error": "Senha incorreta"}), 401

        
        # Recupera informações do usuário
        cursor.execute("SELECT * FROM general_data WHERE register = ?", (data['username'],))
        user_data = cursor.fetchone()
        
        
        # Recuperar permissões com base no cargo
        cursor.execute("""
            SELECT page_id
            FROM pages_roles
            WHERE profile = ?
        """, (user_data['profile'],))
        permissions = cursor.fetchall()

        # Apenas retornar os ids das permissões
        permission_ids = [permission['page_id'] for permission in permissions]

        # Gerar token JWT
        token = jwt.encode({
            "user": user['user'],
            "name": user_data['name'],
            "position": user_data['position'],
            "manager": user_data['manager'],
            "profile": user_data['profile'],
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


# Essa parte aqui eu vou deixar destinada para chamadas ao backend durante a navegação, por exemplo, pegar os chamados que o usuário pode abrir.
# Endpoint para retornar os chamados disponíveis
@app.route('/ticket_types', methods=['GET'])
def get_ticket_type():
    # Obter o token no cabeçalho
    token = request.headers.get("Authorization")
    if not token:
        print("Nenhum token no cabeçalho")
        return jsonify({"error": "Token não fornecido"}), 401

    # Limpar o token do formato 'Bearer' e decodificar
    token = token.replace("Bearer ", "")
    decoded_token = decode_token(token)  # Recuperando os dados do token

    if not decoded_token or not isinstance(decoded_token, dict):
        print("Erro ao validar token ou formato inválido")
        return jsonify({"error": "Token inválido ou expirado"}), 401

    # Recuperar informações do token
    profile = decoded_token.get("profile")

    # Criar conexão com o banco
    connection = create_connection()
    if not connection:
        print("Falha ao conectar com o banco")
        return jsonify({"error": "Não foi possível se conectar com o banco"}), 500

    try:
        cursor = connection.cursor()
        # Consulta ao banco
        cursor.execute("SELECT ticket_type, submotive, form FROM ticket_types WHERE profile = ?", (profile,))
        tickets = cursor.fetchall()

        print("Resultados da consulta ao banco:", tickets)

        # Processar dados retornados
        returned_data = []
        for ticket in tickets:
            try:
                # Carregar o JSON do campo "form", se existir
                form_data = json.loads(ticket[2]) if ticket[2] else {}
            except json.JSONDecodeError as e:
                print("Erro ao processar JSON:", e)
                form_data = {}

            returned_data.append({
                "ticket_type": ticket[0],
                "submotive": ticket[1],
                "form": form_data
            })

        return jsonify(returned_data), 200

    except Exception as e:
        print("Erro ao buscar chamados:", e)
        return jsonify({"error": "Erro ao buscar dados dos chamados"}), 500

    finally:
        connection.close()
        print("Conexão com banco fechada")


# Endpoint para abrir um chamado
@app.route('/open_ticket', methods=['POST'])
def open_ticket():
    # Obter o token no cabeçalho
    token = request.headers.get("Authorization")
    if not token:
        return jsonify({"error": "Token não fornecido"}), 401

    # Limpar o token do formato 'Bearer' e decodificar
    token = token.replace("Bearer ", "")
    decoded_token = decode_token(token)  # Recuperando os dados do token

    if not decoded_token:
        return jsonify({"error": "Token inválido ou expirado"}), 401

    # Recuperar informações do token
    profile = decoded_token.get("profile")
    user = decoded_token.get("user")

    # Obter dados do formulário da requisição
    data = request.get_json()
    ticket_type = data.get('ticket_type')
    submotive = data.get('submotive')
    form = json.dumps(data.get('form'))
    motive_submotive = f"{ticket_type}/{submotive}" if ticket_type and submotive else None

    # Criar conexão com banco
    connection = create_connection()
    if not connection:
        return jsonify({"error": "Não foi possível se conectar com o banco"}), 500

    # Verifica se é necessário aprovação
    try:
        cursor = connection.cursor()

        # Consulta das regras de aprovação do chamado
        cursor.execute("""
            SELECT approval_sequence
            FROM ticket_types
            WHERE motive_submotive = ? AND profile = ?
        """, (motive_submotive, profile))
        approval_roles = cursor.fetchall()


        approval_sequence = approval_roles[0][0]

        # Verifica se o resultado está vazio
        if approval_sequence == 0:  
            print("Chamado aberto sem necessidade de aprovação")
            ticket_status = "Aberto"
            next_approver = None

        else:
            ticket_status = "Aguardando Aprovação"
            
            
            # Garantir que approval_sequence seja uma string
            if isinstance(approval_sequence, int):
                approval_sequence = str(approval_sequence)

            approvers = list(map(int, approval_sequence.split(',')))
            
            if approvers:
                next_approver = approvers[0]

        current_datetime = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")


        # Inserir chamado no banco com o ID do usuário e o próximo aprovador
        cursor.execute(
            "INSERT INTO tickets (ticket_type, submotive, form, user, ticket_status, ticket_open_date_time, next_approver) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (ticket_type, submotive, form, user, ticket_status, current_datetime, next_approver)
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


# Endpoint para listar todos os chamados abertos
@app.route('/list_tickets', methods=['GET'])
def list_tickets():
    try:
        # Obter o token no cabeçalho
        token = request.headers.get("Authorization")
        if not token:
            return jsonify({"error": "Token não fornecido"}), 401

        # Limpar o token do formato 'Bearer' e decodificar
        token = token.replace("Bearer ", "")
        decoded_token = decode_token(token)  # Recuperando os dados do token

        if not decoded_token:
            return jsonify({"error": "Token inválido ou expirado"}), 401

        # Recuperar informações do token
        user = decoded_token.get("user")

        connection = create_connection()
        if not connection:
            return jsonify({"error": "Não foi possível se conectar com o banco"}), 500

        # Obter o termo de busca (query string)
        search_query = request.args.get("search", "").strip()

        sql_query = "SELECT ticket_number, ticket_type, submotive, form FROM tickets WHERE user = ?"
        params = [user]

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


# Endpoint para detalhemento do ticket
@app.route('/ticket_detail/<int:ticket_number>', methods=['GET'])
def ticket_detail(ticket_number):
    try:
        # Obter o token no cabeçalho
        token = request.headers.get("Authorization")
        if not token:
            return jsonify({"error": "Token não fornecido"}), 401

        # Limpar o token do formato 'Bearer' e decodificar
        token = token.replace("Bearer ", "")
        decoded_token = decode_token(token)  # Recuperando os dados do token

        if not decoded_token:
            return jsonify({"error": "Token inválido ou expirado"}), 401

        # Recuperar informações do token
        user = decoded_token.get("user")

        connection = create_connection()
        if not connection:
            return jsonify({"error": "Erro ao conectar com o banco"}), 500

        # Buscar detalhes do chamado pelo ticket_number
        cursor = connection.cursor()
        cursor.execute("SELECT * FROM tickets WHERE ticket_number = ? AND user = ?", (ticket_number, user))
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


# Endpoint para aprovar um chamado
@app.route('/approve_ticket/<int:ticket_id>', methods=['POST'])
def approve_ticket(ticket_id):
    # Lógica para aprovar o ticket no banco de dados
    connection = create_connection()
    cursor = connection.cursor()
    cursor.execute("UPDATE tickets SET ticket_status = 'Aprovado' WHERE id = ?", (ticket_id,))
    connection.commit()
    return jsonify({"message": "Chamado aprovado com sucesso."}), 200

@app.route('/reject_ticket/<int:ticket_id>', methods=['POST'])
def reject_ticket(ticket_id):
    # Lógica para recusar o ticket no banco de dados
    connection = create_connection()
    cursor = connection.cursor()
    cursor.execute("UPDATE tickets SET ticket_status = 'Recusado' WHERE id = ?", (ticket_id,))
    connection.commit()
    return jsonify({"message": "Chamado recusado com sucesso."}), 200


if __name__ == "__main__":
    app.run(debug=True)
