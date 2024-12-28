#utils/token.py
import jwt
from flask import current_app as app

def decode_token(token):
    try:
        # Usando a chave secreta diretamente de app.config
        decoded = jwt.decode(token, app.config['SECRET_KEY'], algorithms=["HS256"])
        
        # Retornar um dicionário com os dados do token
        return {
            # GeneralData
            "user": int(decoded.get("user")),
            "position": decoded.get("position"),
            "name": decoded.get("name"),
            "manager": decoded.get("manager"),
            # Profile Config
            "profile": decoded.get("profile"),
            "approver_id": decoded.get("approver_id"),
            "treatment_id": decoded.get("treatment_id"),
        }
    
    except jwt.InvalidTokenError:
        print("Token inválido ou erro na decodificação")
        return None