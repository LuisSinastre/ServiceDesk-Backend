from flask import Blueprint, jsonify, request, current_app
from utils.token import decode_token
from db import create_connection
import json
import datetime


# Criando o Blueprint
open_tickets = Blueprint('open_ticket', __name__)


# Endpoint para abrir um chamado
@open_tickets.route('/open_ticket', methods=['POST'])
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