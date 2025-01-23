from flask import Blueprint, jsonify, request
from utils.token import decode_token
from db import create_connection
import json
import datetime

# Criando o Blueprint
treat = Blueprint('treat', __name__)


# Endpoint para aprovar um chamado
@treat.route('/treat_ticket/<int:ticket_number>', methods=['POST'])
def treat_ticket(ticket_number):
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
        treatment_id = decoded_token.get("treatment_id")
        user = decoded_token.get("user")
        profile = decoded_token.get("profile")
        
        if not treatment_id:
            return jsonify({"error": "Perfil do tratador não encontrado"}), 404
        print("Tratador atual:", treatment_id)


        # Obter dados do formulário de tratamento
        data = request.get_json()
        observation = data.get('observation')

        if not observation:
            return jsonify({"error": "Formulário de tratamento é obrigatório"}), 400


        # Pesquisa inicial na tabela tickets
        ticket_status_query = """
        SELECT ticket_status, next_treatment, treatment_sequence, treatment_observation
        FROM tickets
        WHERE ticket_number = ?
        """
        cursor.execute(ticket_status_query, (ticket_number,))
        ticket_status_result = cursor.fetchone()

        if not ticket_status_result:
            return jsonify({"error": "Chamado não encontrado"}), 404


        initial_ticket_status = ticket_status_result[0]
        current_treatment = ticket_status_result[1]
        treatment_sequence = json.loads(ticket_status_result[2])
        print(initial_ticket_status, current_treatment, treatment_sequence)
        

        # Verificar se o tratador atual está na sequência
        if treatment_id not in treatment_sequence:
            return jsonify({"error": "Tratador atual não está na sequência de tratamento"}), 400

        current_index = treatment_sequence.index(treatment_id)
        next_treatment = treatment_sequence[current_index + 1] if current_index + 1 < len(treatment_sequence) else 0




        # Definir status do chamado como concluído
        current_date_time = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        ticket_status = "Concluído" if next_treatment == 0 else initial_ticket_status
        close_date_time = current_date_time if next_treatment == 0 else ""

        # Ajustando as observações
        old_observation = ticket_status_result[3]
        if old_observation is None:
            old_observation = ""
        new_observation_entry = f"[{current_date_time}] Tratador {treatment_id} {user} {profile}: {observation}"
        updated_observation = f"{old_observation}\n{new_observation_entry}".strip()


        update_ticket_info = """
        UPDATE tickets
        SET ticket_status = ?,
            next_treatment =?,
            close_date_time =?,
            treatment_observation =?
        WHERE ticket_number = ?
        """
        cursor.execute(update_ticket_info, (ticket_status, next_treatment, close_date_time, updated_observation, ticket_number))

        # Confirmar transação
        connection.commit()
        return {"success": True, "message": "Aprovação processada com sucesso!"}
            
    except Exception as e:
        print(f"Erro ao processar tratamento: {e}")
        return jsonify({"error": "Erro interno no servidor"}), 500
    
    finally:
        if connection:
            connection.close()
