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



