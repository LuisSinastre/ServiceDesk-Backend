from flask import Blueprint, jsonify, request, current_app
from utils.token import decode_token
from db import create_connection
import json

# Criando o Blueprint
processing = Blueprint('processing', __name__)



# Endpoint para listar os chamados na fila de tratamento
@processing.route('/processing_tickets', methods=['GET'])
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
        treatment_id = decoded_token.get("treatment_id")
        print(treatment_id)
        
        connection = create_connection()
        if not connection:
            return jsonify({"error": "Não foi possível se conectar com o banco"}), 500
        
        cursor = connection.cursor()

        # Trazer somente os chamados estão abertos ou aprovados com o meu ID de tratamento
        # Já ajustar um form para o tratamento em ticket_types

        processing_query = """
            SELECT
                ticket_number,
                motive_submotive,
                form, 
                user,
                name,
                manager,
                ticket_open_date_time,
                ticket_status
            FROM
                tickets
            WHERE
                next_treatment = ?
            """
        cursor.execute(processing_query, (treatment_id,))
        processing_result = cursor.fetchall()

        ticket_data_list = []

        # Iterando sobre os resultados de approval_tickets
        for ticket in processing_result:
            ticket_data = {
                "ticket": ticket[0],
                "motive_submotive": ticket[1],
                "form": json.loads(ticket[2]) if ticket[2] else {},
                "user": ticket[3],
                "name": ticket[4],
                "manager": ticket[5],
                "ticket_open_date_time": ticket[6],
                "ticket_status": ticket[7],
            }
            ticket_data_list.append(ticket_data)  # Adiciona o dicionário à lista

        # Retornar todos os tickets como resposta JSON
        return jsonify(ticket_data_list), 200
    
    except Exception as e:
        print("Erro ao buscar detalhes do chamado:", e)
        return jsonify({"error": "Erro interno no servidor"}), 500
    finally:
        connection.close()



