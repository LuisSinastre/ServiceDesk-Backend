from flask import Blueprint, jsonify, request
from utils.token import decode_token
from db import create_connection
import datetime

# Criando o Blueprint
reject = Blueprint('reject', __name__)


# Endpoint para listar os motivos de reprovação
@reject.route('/get_rejection_reasons', methods=['GET'])
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
@reject.route('/reject_ticket/<int:ticket_number>', methods=['POST'])
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
                SET ticket_status = 'Reprovado', rejection_reason = ?, next_approver = 0, next_treatment = 0, close_date_time = ?
                WHERE ticket_number = ?
            """
            cursor.execute(update_ticket_query, (rejection_reason, date_time_rejection, ticket_number,))
            return jsonify({"message": "Você já rejeitou este chamado. Atualizando a tabela tickets"}), 200
        else:
            # Registrar a rejeição na tabela tickets_approvals
            current_date_time = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
            
            reject_approvals_query = """
                INSERT INTO tickets_approvals (ticket_number, rejected_id, repprover_profile, date_time_rejection)
                VALUES (?, ?, ?, ?)
            """
            cursor.execute(reject_approvals_query, (ticket_number, approver_id, profile, current_date_time,))

            # Atualizar o status do ticket para "Reprovado"
            
            

            
            reject_tickets_query = """
                UPDATE tickets
                SET ticket_status = 'Reprovado', rejection_reason = ?, next_approver = 0, next_treatment = 0, close_date_time = ?
                WHERE ticket_number = ?
            """
            cursor.execute(reject_tickets_query, (rejection_reason, current_date_time, ticket_number))

        connection.commit()
        return jsonify({"message": "Chamado rejeitado com sucesso"}), 200

    except Exception as e:
        print(f"Erro ao reprovar o chamado: {e}")
        return jsonify({"error": "Erro interno no servidor"}), 500
    finally:
        connection.close()
