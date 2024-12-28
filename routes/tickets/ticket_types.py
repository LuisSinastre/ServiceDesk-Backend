from flask import Blueprint, jsonify, request, current_app
from utils.token import decode_token
from db import create_connection
import json

# Criando o Blueprint
ticket_types = Blueprint('ticket_types', __name__)

# Endpoint para retornar os chamados disponíveis
@ticket_types.route('/ticket_types', methods=['GET'])
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
