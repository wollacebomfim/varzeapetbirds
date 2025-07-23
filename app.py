from flask import Flask, render_template, redirect, url_for, flash, request, session, jsonify
from flask_login import LoginManager, login_user, current_user, logout_user, login_required, UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import pymysql
import os
import sys
import logging
import traceback
from flask_mail import Mail, Message
from datetime import datetime
import logging
from logging.handlers import RotatingFileHandler
import urllib.parse
from markupsafe import Markup

# Definir o diretório para upload de imagens
UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}

# Configuração do app
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY') or 'uma_chave_secreta'

# Configuração do MySQL
app.config['MYSQL_HOST'] = os.environ.get('MYSQL_HOST', '127.0.0.1')
app.config['MYSQL_USER'] = os.environ.get('MYSQL_USER', 'appmeutreino')
app.config['MYSQL_PASSWORD'] = os.environ.get('MYSQL_PASSWORD', 'Littleboy@1944')
app.config['MYSQL_DB'] = os.environ.get('MYSQL_DB', 'loja_virtual')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
# Configuração de e-mail
app.config['MAIL_SERVER'] = 'smtp.hostinger.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'no-reply@appmeutreino.com'
app.config['MAIL_PASSWORD'] = 'Enolagay@1945'
app.config['MAIL_DEFAULT_SENDER'] = 'no-reply@appmeutreino.com'
mail = Mail(app)

# Configuração do logger
class LogToFile:
    def __init__(self, logger):
        self.logger = logger

    def write(self, message):
        if message.strip():  # Evita logs de mensagens vazias
            self.logger.info(message.strip())

    def flush(self):
        pass  # Necessário para compatibilidade com sys.stdou

# Configuração do logger
if not app.debug:
    handler = RotatingFileHandler('app.log', maxBytes=10000, backupCount=3)
    handler.setLevel(logging.ERROR)
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    app.logger.addHandler(handler)
# Redirecionar sys.stdout e sys.stderr para o logger do Flask
sys.stdout = LogToFile(app.logger)
sys.stderr = LogToFile(app.logger)

# Inicializando o Flask-Login
login_manager = LoginManager(app)
login_manager.login_view = 'login'


# Função de controle de acesso
def tem_acesso_necessario(nivel):
    return current_user.acesslevel == nivel

# Carregar usuário no Flask-Login
@login_manager.user_loader
def load_user(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM usuarios WHERE id = %s', (user_id,))
    user = cursor.fetchone()
    cursor.close()
    conn.close()
    if user:
        return User(user['id'], user['email'], user['senha'], user['acesslevel'])  # Incluindo acesslevel
    return None

# Conexão com o banco de dados
def get_db_connection():
    return pymysql.connect(
        host=app.config['MYSQL_HOST'],
        user=app.config['MYSQL_USER'],
        password=app.config['MYSQL_PASSWORD'],
        database=app.config['MYSQL_DB'],
        cursorclass=pymysql.cursors.DictCursor
    )

# Função para verificar se o arquivo é permitido
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Classe User
class User(UserMixin):
    def __init__(self, id, email, senha, acesslevel):
        self.id = id
        self.email = email
        self.senha = senha
        self.acesslevel = acesslevel  # Adicionando o atributo acesslevel



# Rota: Login
@app.route('/login', methods=['GET', 'POST'])
def login():
    # Verifica se o usuário já está logado
    if current_user.is_authenticated:
        return redirect(url_for('home'))  # Se estiver logado, redireciona para a página inicial

    if request.method == 'POST':
        email = request.form['email']
        senha = request.form['senha']
        
        # Conectar ao banco de dados
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM usuarios WHERE email = %s', (email,))
        user = cursor.fetchone()
        cursor.close()
        conn.close()

        if user and check_password_hash(user['senha'], senha):
            # Verificar o nível de acesso
            login_user(User(user['id'], user['email'], user['senha'], user['acesslevel']))
            if user['acesslevel'] == 1:
                flash('Login bem-sucedido! Bem-vindo, Administrador.', 'success')
                return redirect(url_for('admin_dashboard'))  # Rota do administrador
            elif user['acesslevel'] == 2:
                flash('Login bem-sucedido! Bem-vindo, Vendedor.', 'success')
                return redirect(url_for('seller_dashboard'))  # Rota do vendedor
            else:
                flash('Login bem-sucedido! Bem-vindo!', 'success')
                return redirect(url_for('home'))  # Rota de usuário comum
        else:
            flash('Credenciais inválidas.', 'danger')

    return render_template('login.html')

# Função de log de erro com traceback completo
def log_error(e):
    tb = traceback.format_exc()
    app.logger.error(f"Erro: {str(e)}\nTraceback: {tb}")




@app.route('/')
def home():
    category = request.args.get('category')
    conn = get_db_connection()
    cursor = conn.cursor()
    if category:
        # Supondo que sua tabela produtos possua uma coluna “categoria”
        query = "SELECT * FROM produtos WHERE categoria = %s"
        cursor.execute(query, (category,))
    else:
        query = "SELECT * FROM produtos"
        cursor.execute(query)
    produtos = cursor.fetchall()
    cursor.close()
    conn.close()
    if category and not produtos:
        flash(f"Sem produtos para a categoria \"{category}\".", "info")
    return render_template("home.html", produtos=produtos)

# Função para obter produto por ID
def get_produto_by_id(produto_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM produtos WHERE id = %s', (produto_id,))
    produto = cursor.fetchone()
    cursor.close()
    conn.close()

    if produto:
        return produto
    return None

# Rota: Logout
@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Você saiu da conta.', 'info')
    return redirect(url_for('home'))



@app.route('/fazer_pedido', methods=['POST'])
def fazer_pedido():
    # Recupera o carrinho da sessão
    cart = session.get('cart', {})
    if not cart:
        return redirect(url_for('cart'))
    
    # Captura os dados do formulário
    nome = request.form.get('nome')
    tipo_pagamento = request.form.get('tipo_pagamento')
    tipo_entrega = request.form.get('tipo_entrega')
    total = request.form.get('total')
    
    # Se o tipo de entrega for "a_combinar", captura os dados de endereço
    rua = request.form.get('rua') if tipo_entrega == 'a_combinar' else ''
    numero = request.form.get('numero') if tipo_entrega == 'a_combinar' else ''
    bairro = request.form.get('bairro') if tipo_entrega == 'a_combinar' else ''
    cidade = request.form.get('cidade') if tipo_entrega == 'a_combinar' else ''
    
    # Obter os IDs dos produtos e consultar seus detalhes
    produto_ids = list(cart.keys())
    produto_ids_str = ", ".join(map(str, produto_ids))
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(f'SELECT * FROM produtos WHERE id IN ({produto_ids_str})')
    produtos = cursor.fetchall()
    cursor.close()
    conn.close()
    
    # Monta a mensagem com os itens do pedido
    itens_msg = ""
    for produto in produtos:
        quantidade = cart.get(str(produto['id']), 0)
        itens_msg += f"{produto['nome']} - Quantidade: {quantidade}\n"
    
    # Monta a mensagem final para o Telegram e WhatsApp
    msg_telegram = f"Pedido Realizado:\n"
    msg_telegram += f"Nome: {nome}\n"
    msg_telegram += f"Tipo de Pagamento: {tipo_pagamento}\n"
    msg_telegram += f"Tipo de Entrega: {tipo_entrega}\n"
    if tipo_entrega == 'a_combinar':
        msg_telegram += f"Endereço: \nRua {rua}, \nNº {numero}, \nBairro {bairro}, \nCidade {cidade}\n"
    msg_telegram += f"Itens:\n{itens_msg}"
    msg_telegram += f"Total: R${total}"
    
    # Envia a mensagem via Telegram
    #enviar_telegram(msg_telegram)
    
    # Limpa o carrinho após o pedido
    session['cart'] = {}
    
    # Cria a URL do WhatsApp com a mensagem do pedido (URL-encode)
    whatsapp_link = f"https://api.whatsapp.com/send?phone=5581997822380&text={urllib.parse.quote(msg_telegram)}"
    
    # Renderiza o template que redireciona o usuário
    # Esse template pode conter o script que abre o link do WhatsApp em nova aba
    return render_template("redirect_whatsapp.html", whatsapp_link=whatsapp_link)

@app.route('/cart', methods=['GET', 'POST'])
def cart():
    try:
        # Recupera o carrinho da sessão (chave: produto_id e valor: quantidade)
        cart = session.get('cart', {})
        
        # Se o carrinho estiver vazio e NÃO houver o parâmetro 'pedido' na URL, exibe a mensagem
        if not cart:
            if not request.args.get('pedido'):
                return render_template('cart.html', produtos=[], total=0)
            else:
                produtos = []
                total = 0
        else:
            # Obter os IDs dos produtos
            produto_ids = list(cart.keys())
            if not produto_ids:
                produtos = []
                total = 0
            else:
                produto_ids_str = ", ".join(map(str, produto_ids))
                # Buscar os produtos no banco de dados
                conn = get_db_connection()
                cursor = conn.cursor()
                query = f"SELECT * FROM produtos WHERE id IN ({produto_ids_str})"
                cursor.execute(query)
                produtos = cursor.fetchall()
                
                # Associar a quantidade armazenada na sessão
                for produto in produtos:
                    # Como as chaves do carrinho são strings, convertemos para string para comparar
                    produto['quantidade_carrinho'] = cart.get(str(produto['id']), 0)
                
                # Calcular o total do carrinho
                total = sum([produto['preco'] * produto['quantidade_carrinho'] for produto in produtos])
                cursor.close()
                conn.close()
        
        # Se for POST, trata o pedido e redireciona
        if request.method == 'POST':
            itens_carrinho = "\n".join([f"{produto['nome']} - Quantidade: {produto['quantidade_carrinho']}" for produto in produtos])
            flash(f"Pedido realizado com os seguintes itens:\n{itens_carrinho}", 'success')
            return redirect(url_for('cart'))
        
        return render_template('cart.html', produtos=produtos, total=total)
    except Exception as e:
        log_error(e)
        flash("Ocorreu um erro ao processar o carrinho.", "danger")
        return redirect(url_for('cart'))


@app.route('/remove_from_cart/<int:produto_id>', methods=['POST'])
def remove_from_cart(produto_id):
    cart = session.get('cart', {})
    key = str(produto_id)
    if key in cart:
        cart.pop(key)
        session['cart'] = cart
        flash('Produto removido do carrinho.', 'danger')
    else:
        flash('Produto não encontrado no carrinho.', 'danger')
    return redirect(url_for('cart'))
    

import requests
# Função para enviar mensagens via Telegram
def enviar_telegram(msg):
    bot_token = '6695650940:AAF1UdYtZpjFnZP09Oun3azpzEhGMWaqsz0'  # Coloque aqui o token do seu bot
    chat_id = '541638314'  # Coloque aqui o chat ID
    telegram_url = f'https://api.telegram.org/bot{bot_token}/sendMessage'

    payload = {
        'chat_id': chat_id,
        'text': msg
    }

    response = requests.post(telegram_url, json=payload)
    if response.status_code != 200:
        print(f'Erro ao enviar mensagem para o Telegram: {response.text}')


@app.route('/add_to_cart/<int:produto_id>', methods=['POST'])

def add_to_cart(produto_id):
    # Verificar se a quantidade foi passada no formulário
    quantidade = request.form.get('quantidade')
    if not quantidade or not quantidade.isdigit():
        flash('Quantidade inválida.', 'danger')
        return redirect(url_for('cart'))
    
    quantidade = int(quantidade)
    
    # Usar a sessão para armazenar o carrinho localmente
    cart = session.get('cart', {})
    key = str(produto_id)
    if key in cart:
        cart[key] += quantidade
    else:
        cart[key] = quantidade
    session['cart'] = cart

    flash('Produto adicionado ao carrinho!', 'success')
    return redirect(url_for('cart'))



# Rota: Dashboard do Administrador
@app.route('/admin_dashboard', methods=['GET', 'POST'])
@login_required
def admin_dashboard():
    if current_user.acesslevel != 1:
        flash('Você não tem permissão para acessar esta página.', 'danger')
        return redirect(url_for('home'))

    # Adicionar produto
    if request.method == 'POST' and 'add_product' in request.form:
        nome = request.form['nome']
        preco = request.form['preco']
        descricao = request.form['descricao']
        peso = request.form['peso']
        categoria = request.form['categoria']
        
        # Verificar se o arquivo foi enviado
        if 'imagem' not in request.files:
            flash('Nenhuma imagem foi enviada.', 'danger')
            return redirect(url_for('admin_dashboard'))
        
        imagem = request.files['imagem']
        
        if imagem and allowed_file(imagem.filename):
            filename = secure_filename(imagem.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            imagem.save(filepath)
        else:
            flash('Tipo de arquivo não permitido. Apenas imagens PNG, JPG, JPEG são aceitas.', 'danger')
            return redirect(url_for('admin_dashboard'))

        # Inserir no banco de dados
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('INSERT INTO produtos (nome, preco, descricao, peso, imagem, data_criacao, categoria) VALUES (%s, %s, %s, %s, %s, %s, %s)',
                       (nome, preco, descricao, peso, filename, datetime.now(), categoria))
        conn.commit()
        cursor.close()
        flash('Produto adicionado com sucesso!', 'success')
        return redirect(url_for('admin_dashboard'))

    # Buscar todos os produtos cadastrados
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM produtos')
    produtos = cursor.fetchall()
    cursor.close()

    return render_template('admin_dashboard.html', produtos=produtos)

if __name__ == '__main__':
    app.run(debug=True)