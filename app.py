from flask import Flask
from flask_cors import CORS
from config import Config
from routes.approval.approvals import approvals
from routes.approval.approve import approve
from routes.approval.reject import reject
from routes.authentication.login import login
from routes.tickets.open_ticket import open_tickets
from routes.tickets.search_tickets import search_tickets
from routes.tickets.ticket_types import ticket_types
from routes.treatment.processing import processing
from routes.treatment.treat import treat
from routes.treatment.cancel import cancel

# Criação do aplicativo Flask
app = Flask(__name__)

# Configuração do CORS (permitindo requisições de qualquer origem)
CORS(app)

# Carregar as configurações do arquivo config.py
app.config.from_object(Config)

# Registrar os Blueprints para as rotas
# Aprovações
app.register_blueprint(approvals)
app.register_blueprint(approve)
app.register_blueprint(reject)

# Login
app.register_blueprint(login)

# Tickets
app.register_blueprint(open_tickets)
app.register_blueprint(search_tickets)
app.register_blueprint(ticket_types)

# Tratamento
app.register_blueprint(processing)
app.register_blueprint(treat)
app.register_blueprint(cancel)



if __name__ == "__main__":
    app.run(debug=True)