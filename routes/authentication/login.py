# authroutes.py
from flask import Blueprint, jsonify, request, current_app
from werkzeug.security import check_password_hash
import jwt
import datetime
from db import create_connection

# Criando o Blueprint
login = Blueprint('login', __name__)

# Endpoint para autenticar o login
@login.route('/login', methods=['POST'])
def authenticate_user():
    data = request.get_json()

    # Verificação dos dados fornecidos
    if not data.get('username') or not data.get('password'):
        return jsonify({"error": "Usuário e senha são obrigatórios"}), 400

    connection = create_connection()
    if not connection:
        return jsonify({"error": "Não foi possível conectar com o banco"}), 500

    try:
        cursor = connection.cursor()

        # Consultar o usuário pelo nome de usuário
        cursor.execute("SELECT * FROM users WHERE user = ?", (data['username'],))
        user = cursor.fetchone()

        if not user:
            return jsonify({"error": "Usuário não encontrado"}), 404

        # Verificar se a senha fornecida está correta
        if not check_password_hash(user['password'], data['password']):
            return jsonify({"error": "Senha incorreta"}), 401

        
        # Recupera informações do usuário
        user_info_query = "SELECT * FROM general_data WHERE register = ?"
        cursor.execute(user_info_query, (data['username'],))
        user_info_result = cursor.fetchone()
        
        # Recuperar informações de perfil, aprovação e tratamento
        user_security_info_query = """
        SELECT profile, approver_id, treatment_id
        FROM profile_config
        WHERE position =?"""
        cursor.execute(user_security_info_query, (user_info_result['position'],))
        user_security_info_result = cursor.fetchone()


        # Recuperar permissões das páginas que o usuário pode acessar
        pages_roles_query = """ SELECT page_id FROM pages_roles WHERE profile = ?"""
        cursor.execute(pages_roles_query, (user_security_info_result['profile'],))
        permissions = cursor.fetchall()
        # Apenas retornar os ids das permissões
        permission_ids = [permission['page_id'] for permission in permissions]


        # Gerar token JWT
        token = jwt.encode({
            # GeneralData
            "user": user['user'],
            "name": user_info_result['name'],
            "position": user_info_result['position'],
            "manager": user_info_result['manager'],
            # ProfileConfig
            "profile": user_security_info_result['profile'],
            "approver_id": user_security_info_result['approver_id'],
            "treatment_id": user_security_info_result['treatment_id'],
            # IDs das páginas permitidas
            "ids": permission_ids,
            # Datas
            "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=1)
        }, current_app.config['SECRET_KEY'], algorithm="HS256")
        
        return jsonify({
            "message": "Autenticação bem-sucedida",
            "token": token,
        }), 200

    except Exception as e:
        return jsonify({"error": f"Erro ao autenticar o usuário: {e}"}), 500
    finally:
        connection.close()
