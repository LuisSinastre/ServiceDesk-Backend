from flask import Blueprint, jsonify, request
from utils.token import decode_token
from db import create_connection
import datetime
import json

# Criando o Blueprint
cancel = Blueprint('cancel', __name__)


# Endpoint para listar os motivos de reprovação
@cancel.route('/get_cancel_reasons', methods=['GET'])
def get_cancel_reasons():
    try:
        connection = create_connection()
        cursor = connection.cursor()

        # Buscar todos os motivos de reprovação
        cursor.execute("SELECT cancel_reasons FROM cancellation_reasons")
        reasons = cursor.fetchall()

        # Se não houver motivos cadastrados
        if not reasons:
            return jsonify({"error": "Nenhum motivo de cancelamento encontrado"}), 404

        # Montar a lista de motivos com apenas o campo 'reason'
        cancellation_reasons = [reason[0] for reason in reasons]

        return jsonify({"cancel_reasons": cancellation_reasons}), 200

    except Exception as e:
        print(f"Erro ao buscar motivos de reprovação: {e}")
        return jsonify({"error": "Erro interno no servidor"}), 500
    finally:
        connection.close()





# Endpoint para reprovar um chamado
@cancel.route('/cancel_ticket/<int:ticket_number>', methods=['POST'])
def cancel_ticket(ticket_number):
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
        # Recuperar informações do token
        treatment_id = decoded_token.get("treatment_id")
        user = decoded_token.get("user")
        profile = decoded_token.get("profile")
        
        if not treatment_id:
            return jsonify({"error": "Perfil do tratador não encontrado"}), 404
        print("Tratador atual:", treatment_id)


        # Obter dados do formulário de tratamento
        data = request.get_json()
        cancel_reason = data.get('cancelReason')

        if not cancel_reason:
            return jsonify({"error": "Motivo de cancelamento obrigatório"}), 400


        # Pesquisa inicial na tabela tickets
        ticket_status_query = """
        SELECT next_treatment, treatment_observation
        FROM tickets
        WHERE ticket_number = ?
        """
        cursor.execute(ticket_status_query, (ticket_number,))
        ticket_status_result = cursor.fetchone()

        if not ticket_status_result:
            return jsonify({"error": "Chamado não encontrado"}), 404


        next_treatment = ticket_status_result[0]
        print("Próximo:", next_treatment)
        

        # Verificar se o tratador atual está na sequência
        if treatment_id != next_treatment:
            return jsonify({"error": "Tratador atual não não é o da sequência"}), 400


        # Definir status do chamado como concluído
        current_date_time = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
        ticket_status = "Cancelado"
        close_date_time = current_date_time

        # Ajustando as observações
        old_observation = ticket_status_result[1]
        if old_observation is None:
            old_observation = ""
        new_observation_entry = f"[{current_date_time}] Tratador {treatment_id} {user} {profile}: {cancel_reason}"
        updated_observation = f"{old_observation}\n{new_observation_entry}".strip()


        update_ticket_info = """
        UPDATE tickets
        SET ticket_status = ?,
            next_treatment =?,
            close_date_time =?,
            treatment_observation =?,
            cancellation_reason =?
        WHERE ticket_number = ?
        """
        cursor.execute(update_ticket_info, (ticket_status, 0, close_date_time, updated_observation, cancel_reason, ticket_number))

        # Confirmar transação
        connection.commit()
        return {"success": True, "message": "Cancelamento processado com sucesso!"}

    except Exception as e:
        print(f"Erro ao cancelar o chamado: {e}")
        return jsonify({"error": "Erro interno no servidor"}), 500
    finally:
        connection.close()
