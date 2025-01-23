from flask import Blueprint, jsonify, request, current_app
from utils.token import decode_token
from db import create_connection
import json

# Criando o Blueprint
approvals = Blueprint('approvals', __name__)



# Endpoint para listar todos os chamados a serem aprovados
@approvals.route('/pending_approvals', methods=['GET'])
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
                form,
                ticket_status
            FROM
                tickets
            WHERE
                next_approver = ? AND
                manager = ?
            """
            cursor.execute(pending_tickets_query, (approver_id, name))
            pending_tickets_result = cursor.fetchall()
        
        elif approver_id == 2 or approver_id == 3:
            pending_tickets_query = """
            SELECT
                ticket_number,
                user,
                next_approver,
                manager,
                name,
                motive_submotive,
                form,
                ticket_status
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
                "form": json.loads(ticket[6]) if ticket[6] else {},
                "ticket_status": ticket[7]
            }
            ticket_data_list.append(ticket_data)  # Adiciona o dicionário à lista

        # Retornar todos os tickets como resposta JSON
        return jsonify(ticket_data_list), 200
    
    except Exception as e:
        print("Erro ao buscar detalhes do chamado:", e)
        return jsonify({"error": "Erro interno no servidor"}), 500
    finally:
        connection.close()
