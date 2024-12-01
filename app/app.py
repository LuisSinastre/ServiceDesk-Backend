from flask import Flask, jsonify, request
import mysql.connector
from mysql.connector import Error

app = Flask(__name__)


# Função para criar uma conexão com o banco de dados MySQL
def create_connection():
    try:
        # Tenta estabelecer uma conexão com o banco de dados MySQL
        connection = mysql.connector.connect(
            host="localhost",          # Nome do host onde o banco de dados está hospedado (localhost para o próprio servidor)
            user="root",               # Nome de usuário do banco de dados (neste caso, o usuário padrão 'root')
            password="Sinas@4731",     # Senha para o usuário especificado
            database="bdservicedesk",  # Nome do banco de dados a ser acessado
            charset="utf8mb4"          # Configuração do charset para garantir suporte a caracteres especiais e emojis
        )

        # Verifica se a conexão foi bem-sucedida
        if connection.is_connected():
            print("Conexão com MySQL foi bem-sucedida!")  # Mensagem de sucesso ao estabelecer a conexão
            return connection                             # Retorna o objeto de conexão para uso posterior
    except Error as e:
        # Captura erros que podem ocorrer ao tentar se conectar ao banco de dados
        print(f"Conexão deu pau: {e}")  # Mensagem de erro com detalhes
        return None                     # Retorna None para indicar falha na conexão


# Endpoint para listar usuários
@app.route('/users', methods=['GET'])
def get_users():
    # Tenta criar uma conexão com o banco de dados
    connection = create_connection()
    if not connection:
        # Retorna um erro 500 (falha no servidor) se a conexão não for estabelecida
        return jsonify({"error": "Não foi possível se conectar com o banco"}), 500

    try:
        # Cria um cursor para executar consultas SQL
        # O argumento `dictionary=True` permite que os resultados sejam retornados como dicionários
        cursor = connection.cursor(dictionary=True)

        # Garante que o banco de dados use a codificação UTF-8 para evitar problemas com caracteres especiais
        cursor.execute("SET NAMES 'utf8mb4'")  # Configura a codificação de caracteres

        # Executa a consulta para buscar todos os usuários
        cursor.execute("SELECT * FROM `bdservicedesk`.`users`")
        users = cursor.fetchall()  # Obtém todos os resultados da consulta

        # Prepara a resposta como JSON
        response = jsonify(users)
        response.headers.add('Content-Type', 'application/json; charset=utf-8')  # Define UTF-8 no cabeçalho da resposta
        return response

    except Error as e:
        # Captura erros durante a execução da consulta e retorna uma mensagem de erro
        return jsonify({"error": f"Erro ao consultar os usuários e detalhes: {e}"}), 500

    finally:
        # Fecha a conexão com o banco de dados, garantindo que ela não fique aberta
        if connection:
            connection.close()

# Endpoint para adicionar um novo usuário
@app.route('/users', methods=['POST'])
def add_user():
    # Obtém os dados enviados pelo cliente no corpo da requisição (JSON)
    data = request.get_json()

    # Validação dos campos obrigatórios na requisição
    if not data.get('rg') or not data.get('senha') or not data.get('nome_completo') or \
       not data.get('perfil_acesso') or not data.get('superior_imediato') or not data.get('celula'):
        return jsonify({"error": "Todos os campos são obrigatórios"}), 400  # Retorna erro 400 (requisição inválida)

    # Tenta criar uma conexão com o banco de dados
    connection = create_connection()
    if not connection:
        # Retorna erro 500 se a conexão falhar
        return jsonify({"error": "Não foi possível conectar com o banco"}), 500

    try:
        # Cria um cursor para executar comandos SQL
        cursor = connection.cursor()

        # Verifica se o RG fornecido já existe no banco de dados
        cursor.execute("SELECT rg FROM users WHERE rg = %s", (data['rg'],))
        if cursor.fetchone():
            # Retorna erro 400 se o RG já estiver cadastrado
            return jsonify({"error": "RG já cadastrado"}), 400

        # Insere os dados do novo usuário no banco de dados
        query = """
        INSERT INTO users (rg, senha, nome_completo, perfil_acesso, superior_imediato, celula)
        VALUES (%s, %s, %s, %s, %s, %s)
        """
        values = (
            data['rg'], data['senha'], data['nome_completo'], 
            data['perfil_acesso'], data['superior_imediato'], data['celula']
        )

        cursor.execute(query, values)  # Executa a consulta
        connection.commit()  # Confirma as alterações no banco de dados

        # Retorna uma mensagem de sucesso
        return jsonify({"message": "Usuário adicionado com sucesso"}), 201  # Código 201: recurso criado com sucesso

    except Error as e:
        # Captura erros durante a execução da inserção e retorna uma mensagem de erro
        return jsonify({"error": f"Erro ao adicionar o usuário: {e}"}), 500

    finally:
        # Fecha a conexão com o banco de dados
        if connection:
            connection.close()

# Inicia o servidor Flask no modo de depuração
if __name__ == "__main__":
    app.run(debug=True)
