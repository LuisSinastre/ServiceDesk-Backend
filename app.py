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
            # GeneralData
            "user": int(decoded.get("user")),
            "position": decoded.get("position"),
            "name": decoded.get("name"),
            "manager": decoded.get("manager"),
            # Profile Config
            "profile": decoded.get("profile"),
            "approver_id": decoded.get("approver_id"),
            "treatment_id": decoded.get("treatment_id"),
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
        user_info_query = "SELECT * FROM general_data WHERE register = ?"
        cursor.execute(user_info_query, (data['username'],))
        user_info_result = cursor.fetchone()
        
        # Recuperar informações de perfil, aprovação e tratamento
        user_security_info_query = """
        SELECT profile, approver_id, treatment_id
        FROM profile_config
        WHERE position =?"""
        cursor.execute(user_security_info_query, (user_info_result['position'],))
        user_security_info_result = cursor.fetchone()


        # Recuperar permissões das páginas que o usuário pode acessar
        pages_roles_query = """ SELECT page_id FROM pages_roles WHERE profile = ?"""
        cursor.execute(pages_roles_query, (user_security_info_result['profile'],))
        permissions = cursor.fetchall()
        # Apenas retornar os ids das permissões
        permission_ids = [permission['page_id'] for permission in permissions]


        # Gerar token JWT
        token = jwt.encode({
            # GeneralData
            "user": user['user'],
            "name": user_info_result['name'],
            "position": user_info_result['position'],
            "manager": user_info_result['manager'],
            # ProfileConfig
            "profile": user_security_info_result['profile'],
            "approver_id": user_security_info_result['approver_id'],
            "treatment_id": user_security_info_result['treatment_id'],
            # IDs das páginas permitidas
            "ids": permission_ids,
            # Datas
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
        # Criação do cursor
        cursor = connection.cursor()
        
        
        # Chamados disponíveis para esse perfil
        ticket_types_query = """
        SELECT ticket_type, submotive, motive_submotive, form
        FROM ticket_types
        WHERE profile = ?
        """
        # Execução da consulta
        cursor.execute(ticket_types_query, (profile,))
        ticket_types_result = cursor.fetchall()

        # Processar dados retornados
        returned_data = []
        for ticket in ticket_types_result:
            try:
                # Carregar o JSON do campo "form", se existir
                form_data = json.loads(ticket[3]) if ticket[3] else {}
            except json.JSONDecodeError as e:
                print("Erro ao processar JSON:", e)
                form_data = {}

            returned_data.append({
                "ticket_type": ticket[0],
                "submotive": ticket[1],
                "motive_submotive": ticket[2],
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
    name = decoded_token.get("name")
    manager = decoded_token.get("manager")

    # Obter dados do formulário da requisição
    data = request.get_json()
    ticket_type = data.get('ticket_type')
    submotive = data.get('submotive')
    motive_submotive = data.get('motive_submotive')
    form = json.dumps(data.get('form'))

    # Criar conexão com banco
    connection = create_connection()
    if not connection:
        return jsonify({"error": "Não foi possível se conectar com o banco"}), 500

    try:
        cursor = connection.cursor()

        # Recupera a sequência de aprovação e tratamento do chamado
        approval_treatment_query = """
        SELECT approval_sequence, treatment_sequence
        FROM ticket_types
        WHERE profile =? AND motive_submotive =?"""

        cursor.execute(approval_treatment_query, (profile, motive_submotive,))
        approval_treatment_result = cursor.fetchone()
        approval_sequence_str = approval_treatment_result[0]
        approval_sequence = eval(approval_treatment_result[0])
        treatment_sequence_str = approval_treatment_result[1]
        treatment_sequence = eval(approval_treatment_result[1])

        # Próximo aprovador
        next_approver = approval_sequence[0]

        if next_approver == 0:
            ticket_status = "Aberto"
        else:
            
            # Verifica o perfil do próximo aprovador
            profile_approver_query = """
            SELECT profile
            FROM profile_config
            WHERE approver_id =?
            """
            cursor.execute(profile_approver_query, (next_approver,))
            profile_approver_result = cursor.fetchone()
            profile_approver = profile_approver_result[0]
            ticket_status = f"Aguardando Aprovação - {profile_approver.capitalize()}"


        # Definição da data e hora de abertura do chamado
        current_datetime = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")

        # Inserir chamado no banco de dados
        cursor.execute(
            "INSERT INTO tickets (ticket_type, submotive, motive_submotive, form, user, ticket_status, ticket_open_date_time, next_approver, approval_sequence, treatment_sequence, name, manager) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (ticket_type, submotive, motive_submotive, form, user, ticket_status, current_datetime, next_approver, approval_sequence_str, treatment_sequence_str, name, manager)
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
                ) OR user = ?
            """
            params = [name, user]
            print(params)

        elif profile == "FIELDSERVICE" or "ADM":
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
        elif profile == "FIELDSERVICE" or "ADM":
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
        name = decoded_token.get("name")
        approver_id = decoded_token.get("approver_id")
        
        connection = create_connection()
        if not connection:
            return jsonify({"error": "Não foi possível se conectar com o banco"}), 500
        
        cursor = connection.cursor()
        
        # Recupera os chamados pendentes de aprovação
        
        # Definição da consulta SQL pelo profile
        if approver_id == 1:
            pending_tickets_query = """
            SELECT
                ticket_number,
                user,
                next_approver,
                manager,
                name,
                motive_submotive,
                form
            FROM
                tickets
            WHERE
                next_approver = ? AND
                manager = ?
            """
            cursor.execute(pending_tickets_query, (approver_id, name))
            pending_tickets_result = cursor.fetchall()
        
        elif approver_id == 2 or 3:
            pending_tickets_query = """
            SELECT
                ticket_number,
                user,
                next_approver,
                manager,
                name,
                motive_submotive,
                form
            FROM
                tickets
            WHERE
                next_approver = ?
            """
            cursor.execute(pending_tickets_query, (approver_id,))
            pending_tickets_result = cursor.fetchall()

        if not pending_tickets_result:
            return jsonify({"message": "Nenhum ticket pendente de aprovação"}), 404

        ticket_data_list = []  # Lista para armazenar os dados dos tickets

        # Iterando sobre os resultados de approval_tickets
        for ticket in pending_tickets_result:
            ticket_data = {
                "ticket": ticket[0],
                "user": ticket[1],
                "next_approver": ticket[2],
                "manager": ticket[3],
                "name": ticket[4],
                "motive_submotive": ticket[5],
                "form": json.loads(ticket[6]) if ticket[6] else {}
            }
            ticket_data_list.append(ticket_data)  # Adiciona o dicionário à lista

        # Retornar todos os tickets como resposta JSON
        return jsonify(ticket_data_list), 200
    
    except Exception as e:
        print("Erro ao buscar detalhes do chamado:", e)
        return jsonify({"error": "Erro interno no servidor"}), 500
    finally:
        connection.close()


# Endpoint para aprovar um chamado
@app.route('/approve_ticket/<int:ticket_number>', methods=['POST'])
def approve_ticket(ticket_number):
    connection = None
    try:
        # Conexão com o banco de dados
        connection = create_connection()
        cursor = connection.cursor()

        # Obter informações do token
        token = request.headers.get("Authorization")
        if not token:
            return jsonify({"error": "Token não fornecido"}), 401

        token = token.replace("Bearer ", "")
        decoded_token = decode_token(token)

        if not decoded_token:
            return jsonify({"error": "Token inválido ou expirado"}), 401

        # Recuperar informações do token
        approver_id = decoded_token.get("approver_id")
        profile = decoded_token.get("profile")
        
        if not approver_id or not profile:
            return jsonify({"error": "Perfil do aprovador não encontrado"}), 404

        print("Aprovador atual:", approver_id)

        # Verificar se já foi aprovado
        approved_ticket_query = """
        SELECT id_tickets_approvals
        FROM tickets_approvals
        WHERE ticket_number = ? AND approver_id = ?
        """
        cursor.execute(approved_ticket_query, (ticket_number, approver_id))
        already_approved = cursor.fetchone()

        # Recuperar a sequência de aprovação
        find_next_approver_sequence_query = """
        SELECT approval_sequence
        FROM tickets
        WHERE ticket_number = ?
        """
        cursor.execute(find_next_approver_sequence_query, (ticket_number,))
        approver_sequence = cursor.fetchone()
        if approver_sequence is None:
            return jsonify({"error": "Sequência de aprovação não encontrada"}), 404

        approver_sequence = json.loads(approver_sequence[0])  # Converte para lista
        print("Sequência de aprovação:", approver_sequence)

        # Verificar se o aprovador atual está na sequência
        if approver_id not in approver_sequence:
            return jsonify({"error": "Aprovador atual não está na sequência de aprovação"}), 400

        # Determinar próximo aprovador
        current_index = approver_sequence.index(approver_id)
        next_approver = approver_sequence[current_index + 1] if current_index + 1 < len(approver_sequence) else 0

        # Recupera o perfil do próximo aprovador
        next_approver_profile = 0
        if next_approver != 0:
            next_approver_profile_query = """
            SELECT profile
            FROM profile_config
            WHERE approver_id = ?
            """
            cursor.execute(next_approver_profile_query, (next_approver,))
            next_approver_profile = cursor.fetchone()
            if not next_approver_profile:
                return jsonify({"error": "Perfil do próximo aprovador não encontrado"}), 404
            next_approver_profile = next_approver_profile[0]

        # Definir status do chamado
        ticket_status = "Aprovado" if next_approver == 0 else f"Aguardando Aprovação - {next_approver_profile.capitalize()}"

        # Inserir ou atualizar informações de aprovação
        current_date_time = datetime.datetime.now().strftime('%Y/%m/%d %H:%M:%S')
        if not already_approved:
            insert_approval_info = """
            INSERT INTO tickets_approvals (ticket_number, approver_id, approver_profile, date_time_approval)
            VALUES (?, ?, ?, ?)
            """
            cursor.execute(insert_approval_info, (ticket_number, approver_id, profile, current_date_time))

        update_ticket_info = """
        UPDATE tickets
        SET next_approver = ?, 
            ticket_status = ?
        WHERE ticket_number = ?
        """
        cursor.execute(update_ticket_info, (next_approver, ticket_status, ticket_number))

        # Confirmar transação
        connection.commit()
        return {"success": True, "message": "Aprovação processada com sucesso!"}
            
    except Exception as e:
        print(f"Erro ao processar aprovação: {e}")
        return jsonify({"error": "Erro interno no servidor"}), 500
    
    finally:
        connection.close()


# Endpoint para listar os motivos de reprovação
@app.route('/get_rejection_reasons', methods=['GET'])
def get_rejection_reasons():
    try:
        connection = create_connection()
        cursor = connection.cursor()

        # Buscar todos os motivos de reprovação
        cursor.execute("SELECT reason FROM rejection_reasons")
        reasons = cursor.fetchall()

        # Se não houver motivos cadastrados
        if not reasons:
            return jsonify({"error": "Nenhum motivo de reprovação encontrado"}), 404

        # Montar a lista de motivos com apenas o campo 'reason'
        rejection_reasons = [reason[0] for reason in reasons]

        return jsonify({"rejection_reasons": rejection_reasons}), 200

    except Exception as e:
        print(f"Erro ao buscar motivos de reprovação: {e}")
        return jsonify({"error": "Erro interno no servidor"}), 500
    finally:
        connection.close()


# Endpoint para reprovar um chamado
@app.route('/reject_ticket/<int:ticket_number>', methods=['POST'])
def reject_ticket(ticket_number):
    try:
        connection = create_connection()
        cursor = connection.cursor()
        
        # Obter o token do cabeçalho
        token = request.headers.get("Authorization")
        if not token:
            return jsonify({"error": "Token não fornecido"}), 401

        token = token.replace("Bearer ", "")
        decoded_token = decode_token(token)

        if not decoded_token:
            return jsonify({"error": "Token inválido ou expirado"}), 401

        approver_id = decoded_token.get("approver_id")
        profile = decoded_token.get("profile")
        if not approver_id or not profile:
            return jsonify({"error": "Perfil não encontrado no token"}), 400

        # Buscar dados do chamado
        ticket_info_query = """
        SELECT ticket_number, next_approver, approval_sequence, ticket_status
        FROM tickets
        WHERE ticket_number = ?
        """
        cursor.execute(ticket_info_query, (ticket_number,))
        ticket = cursor.fetchone()

        if not ticket:
            return jsonify({"error": "Chamado não encontrado"}), 404

        ticket_number, next_approver, approval_sequence_str, ticket_status = ticket

        # Obter motivo da reprovação
        data = request.get_json()
        rejection_reason = data.get("rejection_reason")
        if not rejection_reason:
            return jsonify({"error": "Motivo da reprovação é obrigatório"}), 400

        # Verificar se o usuário já rejeitou
        already_rejected_query = """
        SELECT date_time_rejection FROM tickets_approvals WHERE ticket_number = ? AND rejected_id = ?
        """
        cursor.execute(already_rejected_query, (ticket_number, approver_id))
        rejection = cursor.fetchone()

        # Se o chamado já estiver reprovado, atualizar tickets com as infos
        if rejection:
            date_time_rejection = rejection[0]
            # Atualizar o status do ticket para "Reprovado"
            update_ticket_query = """
                UPDATE tickets
                SET ticket_status = 'Reprovado', rejection_reason = ?, next_approver = 0, date_time_rejection = ?
                WHERE ticket_number = ?
            """
            cursor.execute(update_ticket_query, (rejection_reason, date_time_rejection, ticket_number,))
            return jsonify({"message": "Você já rejeitou este chamado. Atualizando a tabela tickets"}), 200
        else:
            # Registrar a rejeição na tabela tickets_approvals
            current_date_time = datetime.datetime.now().strftime('%Y/%m/%d %H:%M:%S')
            
            reject_approvals_query = """
                INSERT INTO tickets_approvals (ticket_number, rejected_id, repprover_profile, date_time_rejection)
                VALUES (?, ?, ?, ?)
            """
            cursor.execute(reject_approvals_query, (ticket_number, approver_id, profile, current_date_time,))

            # Atualizar o status do ticket para "Reprovado"
            
            
            reject_tickets_query = """
                UPDATE tickets
                SET ticket_status = 'Reprovado', rejection_reason = ?, next_approver = 0
                WHERE ticket_number = ?
            """
            cursor.execute(reject_tickets_query, (rejection_reason, ticket_number))

        connection.commit()
        return jsonify({"message": "Chamado rejeitado com sucesso"}), 200

    except Exception as e:
        print(f"Erro ao reprovar o chamado: {e}")
        return jsonify({"error": "Erro interno no servidor"}), 500
    finally:
        connection.close()



# Endpoint para listar os chamados na fila de tratamento
@app.route('/processing_tickets', methods=['GET'])
def list_processing_tickets():
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
        
        connection = create_connection()
        if not connection:
            return jsonify({"error": "Não foi possível se conectar com o banco"}), 500
        
        cursor = connection.cursor()

        # Verificar meu perfil de responsável do chamado
        treatment_profile_query = """
        SELECT treatment_id
        FROM treatment_list
        WHERE treatment_profile = ?        
        """
        cursor.execute(treatment_profile_query, (profile,))
        treatment_profile_result = cursor.fetchone()
        treatment_profile_id = treatment_profile_result [0][0]

        # Trazer somente os chamados que foram aprovados

        ticket_for_treatment_query = """consulta está no sqlstudio"""




















        # Iterando sobre os resultados de approval_tickets
        for ticket in approval_tickets:
            ticket_data = {
                "ticket": ticket[0],
                "user": ticket[1],
                "next_approver": ticket[2],
                "manager": ticket[3],
                "name": ticket[4],
                "motive_submotive": ticket[5],
                "form": json.loads(ticket[6]) if ticket[6] else {}
            }
            ticket_data_list.append(ticket_data)  # Adiciona o dicionário à lista

        # Retornar todos os tickets como resposta JSON
        return jsonify(ticket_data_list), 200
    
    except Exception as e:
        print("Erro ao buscar detalhes do chamado:", e)
        return jsonify({"error": "Erro interno no servidor"}), 500
    finally:
        connection.close()


if __name__ == "__main__":
    app.run(debug=True)
