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
            "profile": decoded.get("profile"),
            "name": decoded.get("name")
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
            SELECT manager_approval, fieldservice_approval
            FROM ticket_types
            WHERE motive_submotive = ? AND profile = ?
        """, (motive_submotive, profile))
        approval_roles = cursor.fetchall()

        # Recuperação dos aprovadores
        for row in approval_roles:
            manager_approval = row[0]
            fieldservice_approval = row[1]

        # Verificando se o chamado necessita de aprovação
        if manager_approval == 0 and fieldservice_approval == 0:
            ticket_status = "Aberto"
            next_approver = 0
        else:
            # Definindo o próximo aprovador
            if manager_approval == 1:
                next_approver = "GERENTE"
                ticket_status = "Aguardando Aprovação do Gerente"
            elif fieldservice_approval == 1:
                next_approver = "FIELD"
                ticket_status = "Aguardando Aprovação do Field"

       
        # Definição da data e hora de abertura do chamado
        current_datetime = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")


        # Inserir chamado no banco com o ID do usuário e o próximo aprovador
        cursor.execute(
            "INSERT INTO tickets (ticket_type, submotive, motive_submotive, form, user, ticket_status, ticket_open_date_time, required_manager_approval, required_fieldservice_approval, approved_manager, approved_fieldservice, next_approver) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (ticket_type, submotive, motive_submotive, form, user, ticket_status, current_datetime, manager_approval, fieldservice_approval, 0, 0, next_approver)
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
        name = decoded_token.get("name")
        profile = decoded_token.get("profile")  # Obter o perfil (campo no token)
        
        connection = create_connection()
        if not connection:
            return jsonify({"error": "Não foi possível se conectar com o banco"}), 500

        # Obter o termo de busca (query string)
        search_query = request.args.get("search", "").strip()

        # Consultas SQL baseadas no perfil
        if profile == "GERENTE":
            sql_query = """
                SELECT ticket_number, ticket_type, submotive, form
                FROM tickets
                WHERE user IN (
                    SELECT register FROM general_data WHERE manager = ?
                )
            """
            params = [name]

        elif profile == "FIELD":
            sql_query = "SELECT ticket_number, ticket_type, submotive, form FROM tickets"
            params = []  # Campo de busca para FIELD

        else:  # Para usuário normal
            sql_query = "SELECT ticket_number, ticket_type, submotive, form FROM tickets WHERE user = ?"
            params = [user]

        # Adicionar a pesquisa se fornecida
        if search_query:
            if 'WHERE' in sql_query:  # Se já houver uma cláusula WHERE
                sql_query += " AND (ticket_number = ? OR ticket_type LIKE ? OR submotive LIKE ?)"
            else:  # Caso contrário, inicia com WHERE
                sql_query += " WHERE (ticket_number = ? OR ticket_type LIKE ? OR submotive LIKE ?)"
            params.extend([search_query, f"%{search_query}%", f"%{search_query}%"])

        cursor = connection.cursor()
        cursor.execute(sql_query, params)

        tickets = cursor.fetchall()

        # Verificar se há tickets retornados
        if not tickets:
            return jsonify({"error": "Nenhum ticket encontrado"}), 404

        # Retornar os tickets
        return jsonify([{
            "ticket_number": ticket[0],
            "ticket_type": ticket[1],
            "submotive": ticket[2],
            "form": json.loads(ticket[3]) if ticket[3] else {}
        } for ticket in tickets]), 200

    except Exception as e:
        return jsonify({"error": f"Erro interno no servidor: {str(e)}"}), 500
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
        name = decoded_token.get("name")
        profile = decoded_token.get("profile")  # Obter o perfil (campo no token)

        connection = create_connection()
        if not connection:
            return jsonify({"error": "Erro ao conectar com o banco"}), 500

        # Consultar os detalhes do ticket com base no perfil
        cursor = connection.cursor()

        # Se o perfil for GERENTE ou FIELD, podemos acessar qualquer chamado
        if profile == "GERENTE":
            cursor.execute("""
                SELECT ticket_number, ticket_type, submotive, form, user, ticket_status, ticket_open_date_time
                FROM tickets 
                WHERE ticket_number = ?
            """, (ticket_number,))
        elif profile == "FIELD":
            cursor.execute("""
                SELECT ticket_number, ticket_type, submotive, form, user, ticket_status, ticket_open_date_time
                FROM tickets 
                WHERE ticket_number = ?
            """, (ticket_number,))
        else:
            # Para o usuário normal, só poderá acessar o próprio ticket
            cursor.execute("""
                SELECT ticket_number, ticket_type, submotive, form, user, ticket_status, ticket_open_date_time
                FROM tickets 
                WHERE ticket_number = ? AND user = ?
            """, (ticket_number, user))

        ticket = cursor.fetchone()

        if not ticket:
            return jsonify({"error": "Chamado não encontrado ou acesso negado"}), 404

        # Verificar se o campo 'form' não está vazio antes de tentar carregar como JSON
        form_data = None
        if ticket[3]:  # Verifica se 'form' tem algum valor
            try:
                form_data = json.loads(ticket[3])  # Tenta converter o valor em JSON
            except json.JSONDecodeError:
                form_data = None  # Caso o valor não seja um JSON válido

        # Retornar os detalhes
        ticket_data = {
            "ticket_number": ticket[0],
            "ticket_type": ticket[1],
            "submotive": ticket[2],
            "form": form_data,
            "user": ticket[4],
            "ticket_status": ticket[5],
            "ticket_open_date_time": ticket[6]
        }
        return jsonify(ticket_data), 200
    except Exception as e:
        print("Erro ao buscar detalhes do chamado:", e)
        return jsonify({"error": "Erro interno no servidor"}), 500
    finally:
        if connection:
            connection.close()



# Endpoint para listar todos os chamados a serem aprovados
@app.route('/pending_approvals', methods=['GET'])
def list_approval():
    try:
        # Obter o token no cabeçalho
        token = request.headers.get("Authorization")
        if not token:
            return jsonify({"error": "Token não fornecido"}), 401

        # Limpar o token do formato 'Bearer' e decodificar
        token = token.replace("Bearer ", "")
        decoded_token = decode_token(token)

        if not decoded_token:
            return jsonify({"error": "Token inválido ou expirado"}), 401

        # Recuperar informações do token
        profile = decoded_token.get("profile")
        name = decoded_token.get("name")
        
        connection = create_connection()
        if not connection:
            return jsonify({"error": "Não foi possível se conectar com o banco"}), 500
        
        cursor = connection.cursor()

        approval_tickets = []

        if profile == "GERENTE":
            cursor.execute("""
                SELECT t.ticket_number, t.user, t.approved_manager, t.approved_fieldservice, t.next_approver, gd.manager, gd.name, t.motive_submotive, t.form
                FROM tickets t
                JOIN general_data gd ON t.user = gd.register
                WHERE t.next_approver = ?
                AND gd.manager = ?
            """, (profile, name))
            approval_tickets = cursor.fetchall()

        elif profile == "FIELD":
            cursor.execute("""
                SELECT t.ticket_number, t.user, t.approved_manager, t.approved_fieldservice, t.next_approver, gd.manager, gd.name, t.motive_submotive, t.form
                FROM tickets t
                JOIN general_data gd ON t.user = gd.register
                WHERE t.next_approver = ?
            """, (profile,))
            approval_tickets = cursor.fetchall()

        if not approval_tickets:
            return jsonify({"message": "Nenhum ticket pendente de aprovação"}), 404

        ticket_data_list = []  # Lista para armazenar os dados dos tickets

        # Iterando sobre os resultados de approval_tickets
        for ticket in approval_tickets:
            
            ticket_data = {
                "ticket": ticket[0],
                "user": ticket[1],
                "approved_manager": ticket[2],
                "approved_fieldservice": ticket[3],
                "next_approver": ticket[4],
                "manager": ticket[5],
                "name": ticket[6],
                "motive_submotive": ticket[7],
                "form": json.loads(ticket[8]) if ticket[8] else {}
            }
            
            ticket_data_list.append(ticket_data)  # Adiciona o dicionário à lista

        # Retornar todos os tickets como resposta JSON
        return jsonify(ticket_data_list), 200
    
    except Exception as e:
        print("Erro ao buscar detalhes do chamado:", e)
        return jsonify({"error": "Erro interno no servidor"}), 500
    finally:
        connection.close()


@app.route('/approve_ticket/<int:ticket_number>', methods=['POST'])
def approve_ticket(ticket_number):
    try:
        # Obter o token no cabeçalho
        token = request.headers.get("Authorization")
        if not token:
            return jsonify({"error": "Token não fornecido"}), 401

        # Limpar o token do formato 'Bearer' e decodificar
        token = token.replace("Bearer ", "")
        decoded_token = decode_token(token)

        if not decoded_token:
            return jsonify({"error": "Token inválido ou expirado"}), 401

        # Recuperar informações do token
        profile = decoded_token.get("profile")

        # Verificar se o perfil é GERENTE ou FIELD
        if profile not in ["GERENTE", "FIELD"]:
            return jsonify({"error": "Você não tem permissão para aprovar este chamado"}), 403

        connection = create_connection()
        if not connection:
            return jsonify({"error": "Não foi possível se conectar com o banco"}), 500

        cursor = connection.cursor()

        # Buscar o chamado a ser aprovado
        cursor.execute("""
            SELECT ticket_number, next_approver, approved_manager, approved_fieldservice, ticket_status
            FROM tickets 
            WHERE ticket_number = ?
        """, (ticket_number,))
        ticket = cursor.fetchone()

        if not ticket:
            return jsonify({"error": "Chamado não encontrado"}), 404

        # Verificar se o chamado já foi aprovado por ambos os aprovadores
        if ticket[2] == 1 and ticket[3] == 1:  # Verifica se ambos os aprovadores já aprovaram
            
            cursor.execute("""
                UPDATE tickets
                SET ticket_status = 'Aberto', next_approver = 0
                WHERE ticket_number = ?
            """, (ticket_number,))
            connection.commit()
            return jsonify({"message": "Chamado já aprovado."}), 200

        # Se o próximo aprovador for nulo ou vazio, significa que o ticket já está aprovado
        if not ticket[1]:  # ticket[1] é o campo next_approver
            cursor.execute("""
                UPDATE tickets
                SET ticket_status = 'Aberto', next_approver = 0
                WHERE ticket_number = ?
            """, (ticket_number,))
            connection.commit()
            return jsonify({"message": "Chamado já aprovado, sem mais aprovadores."}), 200

        # Verificar se o usuário tem permissão para aprovar (deve ser o gerente ou field)
        current_datetime = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
        if profile == "GERENTE":
            # Atualizar o campo de aprovação do gerente
            cursor.execute("""
                UPDATE tickets
                SET approved_manager = 1, date_time_approved_rejected_manager = ?,
                    next_approver = CASE 
                        WHEN next_approver = 'GERENTE' THEN 'FIELD'
                        ELSE next_approver
                    END,
                    ticket_status = 'Aguardando Aprovação do FieldService'
                WHERE ticket_number = ?
            """, (current_datetime, ticket_number,))
            connection.commit()

            return jsonify({"message": "Chamado aprovado, aguarda aprovação do field service."}), 200

        elif profile == "FIELD":
            # Atualizar o campo de aprovação do field service
            cursor.execute("""
                UPDATE tickets
                SET approved_fieldservice = 1, date_time_approved_rejected_fieldservice = ?,
                    ticket_status = 'Aberto', next_approver = 0
                WHERE ticket_number = ?
            """, (current_datetime, ticket_number,))
            connection.commit()

            return jsonify({"message": "Chamado aprovado."}), 200

    except Exception as e:
        print("Erro ao aprovar o chamado:", e)
        return jsonify({"error": "Erro interno no servidor"}), 500
    finally:
        connection.close()


@app.route('/reject_ticket/<int:ticket_number>', methods=['POST'])
def reject_ticket(ticket_number):
    try:
        # Obter o token do cabeçalho
        token = request.headers.get("Authorization")
        if not token:
            return jsonify({"error": "Token não fornecido"}), 401

        # Limpar o token do formato 'Bearer' e decodificar
        token = token.replace("Bearer ", "")
        decoded_token = decode_token(token)

        if not decoded_token:
            return jsonify({"error": "Token inválido ou expirado"}), 401

        # Recuperar informações do token
        profile = decoded_token.get("profile")

        # Verificar se o perfil é GERENTE ou FIELD
        if profile not in ["GERENTE", "FIELD"]:
            return jsonify({"error": "Você não tem permissão para reprovar este chamado"}), 403

        # Obter o motivo da reprovação do corpo da requisição
        data = request.get_json()
        rejection_reason = data.get("rejection_reason")

        if not rejection_reason:
            return jsonify({"error": "Motivo da reprovação é obrigatório"}), 400

        connection = create_connection()
        if not connection:
            return jsonify({"error": "Não foi possível se conectar com o banco"}), 500

        cursor = connection.cursor()

        # Buscar o chamado a ser reprovado
        cursor.execute("""
            SELECT ticket_number, next_approver, ticket_status
            FROM tickets 
            WHERE ticket_number = ?
        """, (ticket_number,))
        ticket = cursor.fetchone()

        if not ticket:
            return jsonify({"error": "Chamado não encontrado"}), 404

        # Atualizar o status para "Reprovado" e armazenar o motivo da reprovação
        current_datetime = datetime.datetime.now().strftime("%d/%m/%y %H:%M")

        if profile == "GERENTE":
            cursor.execute("""
                UPDATE tickets
                SET ticket_status = 'Reprovado pelo Gerente', 
                    rejection_reason = ?,
                    next_approver = 0,  -- Nenhum próximo aprovador
                    date_time_approved_rejected_manager = ?
                WHERE ticket_number = ?
            """, (rejection_reason, current_datetime, ticket_number))
            connection.commit()

            return jsonify({"message": "Chamado reprovado pelo gerente."}), 200

        elif profile == "FIELD":
            cursor.execute("""
                UPDATE tickets
                SET ticket_status = 'Reprovado pelo Field Service', 
                    rejection_reason = ?,
                    next_approver = 0,  -- Nenhum próximo aprovador
                    date_time_approved_rejected_fieldservice = ?
                WHERE ticket_number = ?
            """, (rejection_reason, current_datetime, ticket_number))
            connection.commit()

            return jsonify({"message": "Chamado reprovado pelo field service."}), 200

    except Exception as e:
        print("Erro ao reprovar o chamado:", e)
        return jsonify({"error": "Erro interno no servidor"}), 500
    finally:
        connection.close()


if __name__ == "__main__":
    app.run(debug=True)
