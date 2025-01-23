from flask import Blueprint, jsonify, request, current_app
from utils.token import decode_token
from db import create_connection
import json

# Criando o Blueprint
search_tickets = Blueprint('search_tickets', __name__)

# Endpoint para listar todos os chamados abertos
@search_tickets.route('/list_tickets', methods=['GET'])
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
                SELECT ticket_number, ticket_type, submotive, form, user, name
                FROM tickets
                WHERE (
                    user IN (
                        SELECT register FROM general_data WHERE manager = ?
                    ) OR user = ?
                )
            """
            params = [name, user]

        elif profile in ("FIELDSERVICE", "ADM"):
            sql_query = "SELECT ticket_number, ticket_type, submotive, form, user, name FROM tickets"
            params = []  # Campo de busca para FIELD

        else:  # Para usuário normal
            sql_query = "SELECT ticket_number, ticket_type, submotive, form, user, name FROM tickets WHERE user = ?"
            params = [user]

        # Adicionar a pesquisa se fornecida
        if search_query:
            search_clause = " AND " if "WHERE" in sql_query else " WHERE "
            search_filter = "(ticket_number = ? OR ticket_type LIKE ? OR submotive LIKE ?)"
            sql_query += search_clause + search_filter
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
            "form": json.loads(ticket[3]) if ticket[3] else {},
            "user": ticket[4],
            "name": ticket[5],

        } for ticket in tickets]), 200

    except Exception as e:
        return jsonify({"error": f"Erro interno no servidor: {str(e)}"}), 500
    finally:
        connection.close()


# Endpoint para detalhemento do ticket
@search_tickets.route('/ticket_detail/<int:ticket_number>', methods=['GET'])
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
        elif profile == "FIELDSERVICE" or "ADM":
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

