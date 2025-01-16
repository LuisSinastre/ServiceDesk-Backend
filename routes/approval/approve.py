from flask import Blueprint, jsonify, request
from utils.token import decode_token
from db import create_connection
import json
import datetime

# Criando o Blueprint
approve = Blueprint('approve', __name__)


# Endpoint para aprovar um chamado
@approve.route('/approve_ticket/<int:ticket_number>', methods=['POST'])
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
        SELECT approval_sequence, treatment_sequence
        FROM tickets
        WHERE ticket_number = ?
        """
        cursor.execute(find_next_approver_sequence_query, (ticket_number,))
        approver_treatment_sequence = cursor.fetchone()
        if approver_treatment_sequence is None:
            return jsonify({"error": "Sequência de aprovação não encontrada"}), 404

        approver_sequence = json.loads(approver_treatment_sequence[0])
        treatment_sequence = json.loads(approver_treatment_sequence[1])
        print("Sequência de aprovação:", approver_sequence)
        print("Sequência de tratamento:", treatment_sequence)


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
        next_treatment = treatment_sequence[0] if next_approver == 0 else 0

        # Inserir ou atualizar informações de aprovação
        current_date_time = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
        if not already_approved:
            insert_approval_info = """
            INSERT INTO tickets_approvals (ticket_number, approver_id, approver_profile, date_time_approval)
            VALUES (?, ?, ?, ?)
            """
            cursor.execute(insert_approval_info, (ticket_number, approver_id, profile, current_date_time))

        update_ticket_info = """
        UPDATE tickets
        SET next_approver = ?, 
            ticket_status = ?,
            next_treatment =?
        WHERE ticket_number = ?
        """
        cursor.execute(update_ticket_info, (next_approver, ticket_status, next_treatment, ticket_number))

        # Confirmar transação
        connection.commit()
        return {"success": True, "message": "Aprovação processada com sucesso!"}
            
    except Exception as e:
        print(f"Erro ao processar aprovação: {e}")
        return jsonify({"error": "Erro interno no servidor"}), 500
    
    finally:
        connection.close()

