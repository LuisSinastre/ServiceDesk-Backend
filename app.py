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
        
        # Consulta separada em variável
        query = """
        SELECT 
            t.ticket_type,
            t.submotive,
            t.motive_submotive,
            t.form,
            a.allowed_profile
        FROM 
            ticket_types t
        LEFT JOIN 
            allowed_tickets a 
            ON t.motive_submotive = a.motive_submotive
        WHERE 
            a.allowed_profile = ?;
        """
        
        # Execução da consulta
        cursor.execute(query, (profile,))
        
        # Recupera os resultados
        tickets = cursor.fetchall()

        print("Resultados da consulta ao banco:", tickets)

        # Processar dados retornados
        returned_data = []
        for ticket in tickets:
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

    # Verifica se é necessário aprovação
    try:
        cursor = connection.cursor()

        # Consulta o tipo de aprovação do chamado
        approval_type_query = """
        SELECT o.approval_type
        FROM opening_config o
        LEFT JOIN ticket_types t ON o.motive_submotive = t.motive_submotive
        WHERE o.motive_submotive =?
        """
        cursor.execute(approval_type_query, (motive_submotive,))
        approval_type_result = cursor.fetchall()

        if approval_type_result:
            approval_type_result = approval_type_result[0][0]
        else:
            return jsonify({"error": "Nenhum tipo de aprovação encontrado para o motivo e submotivo informados"}), 400

        # Consulta a sequência de aprovação
        approval_sequence_query = """
        SELECT approval_sequence
        FROM approval_config
        WHERE id_approval_type =? AND approver_profile =?
        """
        cursor.execute(approval_sequence_query, (approval_type_result, profile,))
        approval_sequence_result = cursor.fetchall()

        # Verifica e ordena a sequência de aprovação
        if approval_sequence_result:
            approval_sequence_result.sort(key=lambda x: x[0])  # Ordena pela sequência de aprovação
            first_approver = approval_sequence_result[0][0]
            approval_sequence_list = [x[0] for x in approval_sequence_result]
            approval_sequence_str = json.dumps(approval_sequence_list)

            # Consultar o perfil do aprovador
            approver_profile_query = """
            SELECT approver_profile
            FROM approver_list
            WHERE approver_id =?
            """
            cursor.execute(approver_profile_query, (first_approver,))
            approver_profile_result = cursor.fetchall()

            if approver_profile_result:
                approver_profile = approver_profile_result[0][0]
                ticket_status = f"Aguardando Aprovação - {approver_profile.capitalize()}"
            else:
                ticket_status = "Aberto"
                first_approver = 0  # Se não encontrar perfil do aprovador, tratamos como 'Aberto'
                approval_sequence_str = "[]"

        else:
            ticket_status = "Aberto"
            first_approver = 0  # Caso não haja aprovadores
            approval_sequence_str = "[]"
            print('Sem aprovadores')

        # Definição da data e hora de abertura do chamado
        current_datetime = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")

        # Inserir chamado no banco de dados
        cursor.execute(
            "INSERT INTO tickets (ticket_type, submotive, motive_submotive, form, user, ticket_status, ticket_open_date_time, next_approver, approval_sequence) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (ticket_type, submotive, motive_submotive, form, user, ticket_status, current_datetime, first_approver, approval_sequence_str)
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

        # Verifica os perfis de aprovação disponíveis
        all_approval_profile_search_query = """
        SELECT 
            approver_id
        FROM
            approver_list
        """
        cursor.execute(all_approval_profile_search_query)
        all_approval_profile = cursor.fetchall()
        all_approver_ids = [profile[0] for profile in all_approval_profile]  # Lista de todos os approver_ids

        # Verifica se o perfil de aprovação do usuário está na lista de approver_ids
        approval_id_search_query = """
        SELECT 
            approver_id
        FROM
            approver_list
        WHERE
            approver_profile =?
        """
        cursor.execute(approval_id_search_query, (profile,))
        approval_id = cursor.fetchall()
        
        if approval_id:
            approver_id = approval_id[0][0]  # Se houver algum ID de aprovador retornado
            if approver_id not in all_approver_ids:
                return jsonify({"error": "Perfil de aprovação não encontrado na lista de aprovadores"}), 404
        else:
            return jsonify({"error": "Perfil de aprovação não encontrado"}), 404

        # Agora, busca pelos tickets pendentes de aprovação para o perfil do usuário
        approval_tickets = []

        if profile == "GERENTE":
            cursor.execute("""
                SELECT t.ticket_number, t.user, t.next_approver, gd.manager, gd.name, t.motive_submotive, t.form
                FROM tickets t
                JOIN general_data gd ON t.user = gd.register
                WHERE t.next_approver = ? AND gd.manager = ?
            """, (approver_id, name))
            approval_tickets = cursor.fetchall()

        elif profile == "FIELD":
            cursor.execute("""
                SELECT t.ticket_number, t.user, t.next_approver, gd.manager, gd.name, t.motive_submotive, t.form
                FROM tickets t
                JOIN general_data gd ON t.user = gd.register
                WHERE t.next_approver = ?
            """, (approver_id,))
            approval_tickets = cursor.fetchall()

        if not approval_tickets:
            return jsonify({"message": "Nenhum ticket pendente de aprovação"}), 404

        ticket_data_list = []  # Lista para armazenar os dados dos tickets

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


@app.route('/approve_ticket/<int:ticket_number>', methods=['POST'])
def approve_ticket(ticket_number):
    try:
        # Conexão e token
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

        profile = decoded_token.get("profile")
        name = decoded_token.get("name")

        # Obter meu ID de aprovador
        my_approver_id_query = "SELECT approver_id FROM approver_list WHERE approver_profile = ?"
        cursor.execute(my_approver_id_query, (profile,))
        my_approver_id_result = cursor.fetchone()
        my_approver_id = int(my_approver_id_result[0]) if my_approver_id_result else None
        print(f"[LOG] Meu ID de aprovador: {my_approver_id} (Tipo: {type(my_approver_id)})")

        if not my_approver_id:
            return jsonify({"error": "Perfil do aprovador não encontrado"}), 404

        # Recuperar próximo aprovador e sequência de aprovação
        ticket_query = """
        SELECT next_approver, approval_sequence, ticket_status
        FROM tickets
        WHERE ticket_number = ?
        """
        cursor.execute(ticket_query, (ticket_number,))
        ticket_result = cursor.fetchone()

        if not ticket_result:
            return jsonify({"error": "Ticket não encontrado"}), 404

        next_approver, approval_sequence_str, ticket_status = ticket_result
        next_approver = int(next_approver) if next_approver else None  # Garantir consistência no tipo
        print(f"[LOG] Próximo aprovador: {next_approver} (Tipo: {type(next_approver)})")
        print(f"[LOG] Status do ticket: {ticket_status}")

        # Verificar sequência de aprovação
        try:
            approval_sequence = json.loads(approval_sequence_str)
            print(f"[LOG] Sequência de aprovação decodificada: {approval_sequence}")
        except json.JSONDecodeError:
            print("[LOG] Erro ao decodificar a sequência de aprovação")
            return jsonify({"error": "Erro ao decodificar a sequência de aprovação"}), 500

        # Verificar aprovações realizadas
        if next_approver == my_approver_id:
            print("[LOG] Usuário é o próximo aprovador")
            realized_approval_query = """
            SELECT approver_id
            FROM tickets_approvals
            WHERE ticket_number = ? AND approver_id = ?
            """
            cursor.execute(realized_approval_query, (ticket_number, my_approver_id))
            realized_approval_result = cursor.fetchone()

            if realized_approval_result:
                print("[LOG] Aprovação já registrada no histórico")
                return jsonify({"message": "Aprovação já realizada"}), 200

            # Inserir aprovação no histórico
            current_datetime = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")  # Obtendo o horário atual
            insert_approval_query = """
            INSERT INTO tickets_approvals (ticket_number, approver_id, date_time_approval, approver_profile)
            VALUES (?, ?, ?, ?)
            """
            cursor.execute(insert_approval_query, (ticket_number, my_approver_id, current_datetime, profile))
            print(f"[LOG] Aprovação registrada no histórico com sucesso - {current_datetime}")

            # Atualizar o próximo aprovador ou status do ticket
            if len(approval_sequence) > 1:
                approval_sequence.pop(0)  # Remove o aprovador atual da sequência
                new_next_approver = approval_sequence[0]

                # Obter o perfil do próximo aprovador
                next_approver_profile_query = """
                SELECT approver_profile FROM approver_list WHERE approver_id = ?
                """
                cursor.execute(next_approver_profile_query, (new_next_approver,))
                next_approver_profile_result = cursor.fetchone()

                if next_approver_profile_result:
                    next_approver_profile = next_approver_profile_result[0]
                else:
                    next_approver_profile = "Desconhecido"  # Caso não encontre o próximo aprovador

                update_ticket_query = """
                UPDATE tickets
                SET next_approver = ?, approval_sequence = ?, ticket_status = ?
                WHERE ticket_number = ?
                """
                cursor.execute(update_ticket_query, (
                    new_next_approver,
                    json.dumps(approval_sequence),
                    f"Aguardando Aprovação - {next_approver_profile.capitalize()}",
                    ticket_number
                ))
                print(f"[LOG] Próximo aprovador atualizado: {new_next_approver} e status de ticket atualizado com perfil {next_approver_profile}")
            else:
                update_ticket_status_query = """
                UPDATE tickets
                SET next_approver = 0, approval_sequence = '[0]', ticket_status = 'Aprovado'
                WHERE ticket_number = ?
                """
                cursor.execute(update_ticket_status_query, (ticket_number,))
                print("[LOG] Ticket aprovado. Sequência de aprovação concluída")

            connection.commit()
            return jsonify({"message": "Aprovação realizada com sucesso"}), 200
        else:
            print("[LOG] Usuário não é o próximo aprovador")
            return jsonify({"message": "Você não é o próximo aprovador"}), 403

    except Exception as e:
        print("[LOG] Erro ao aprovar o chamado:", e)
        return jsonify({"error": "Erro interno no servidor"}), 500
    finally:
        print("[LOG] Fechando conexão com o banco de dados")
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
