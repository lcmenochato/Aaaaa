import telebot
import sqlite3
import time
import os
import random
import requests
import base64
from io import BytesIO
from telebot import types
from flask import Flask, request, jsonify
from threading import Thread

# Configurações do Bot
TOKEN_TELEGRAM = "8809374742:AAHqz-SLxihWi_IVW_gCYba9Uh1HsoBvbeI"
ID_CANAL_VIP = -1001234567890
ADMIN_ID = 123456789

# Webhook do Discord para Notificações
URL_WEBHOOK_DISCORD = ""



bot = telebot.TeleBot(TOKEN_TELEGRAM)
app = Flask(__name__)

# --- BANCO DE DADOS ---
def iniciar_banco():
    conn = sqlite3.connect('usuarios.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS clientes (
            telegram_id INTEGER,
            transaction_id TEXT PRIMARY KEY,
            status TEXT
        )
    ''')
    conn.commit()
    conn.close()

def salvar_transacao(telegram_id, transaction_id):
    conn = sqlite3.connect('usuarios.db')
    cursor = conn.cursor()
    cursor.execute('INSERT OR REPLACE INTO clientes (telegram_id, transaction_id, status) VALUES (?, ?, ?)',
                   (telegram_id, str(transaction_id), 'PENDENTE'))
    conn.commit()
    conn.close()

def atualizar_status_pago(transaction_id):
    conn = sqlite3.connect('usuarios.db')
    cursor = conn.cursor()
    cursor.execute('SELECT telegram_id FROM clientes WHERE transaction_id = ?', (str(transaction_id),))
    res = cursor.fetchone()
    if res:
        cursor.execute('UPDATE clientes SET status = ? WHERE transaction_id = ?', ('COMPLETO', str(transaction_id)))
        conn.commit()
        conn.close()
        return res[0]
    conn.close()
    return None

# --- NOTIFICAÇÃO DISCORD ---
def notificar_discord_start(user):
    nome = user.first_name if user.first_name else "Sem nome"
    username = f"@{user.username}" if user.username else "Sem username"
    telegram_id = user.id

    payload = {
        "embeds": [
            {
                "title": "🚀 Novo Usuário Iniciou o Bot!",
                "color": 5814783,  # Cor azul/roxa estilizada
                "fields": [
                    {"name": "👤 Nome", "value": nome, "inline": True},
                    {"name": "🏷️ Username", "value": username, "inline": True},
                    {"name": "🆔 Telegram ID", "value": f"`{telegram_id}`", "inline": False}
                ],
                "timestamp": time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
            }
        ]
    }
    try:
        requests.post(URL_WEBHOOK_DISCORD, json=payload, timeout=5)
    except Exception as e:
        print(f"❌ Erro ao enviar notificação para o Discord: {e}")

# --- AUXILIARES ---
def gerar_cpf_valido():
    cpf = [random.randint(0, 9) for _ in range(9)]
    for _ in range(2):
        val = sum([(len(cpf) + 1 - i) * v for i, v in enumerate(cpf)]) % 11
        cpf.append(0 if val < 2 else 11 - val)
    return "".join(map(str, cpf))

# --- API MISTICPAY ---
def criar_pix_mistic(chat_id, tx_id, valor=10):
    url = "https://api.misticpay.com/api/transactions/create"
    headers = {
        "ci": CI,
        "cs": CS,
        "Content-Type": "application/json"
    }
    payload = {
        "amount": valor,
        "payerName": f"Cliente_{chat_id}",
        "payerDocument": gerar_cpf_valido(),
        "transactionId": tx_id,
        "description": "Acesso VIP Amanda"
    }
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        if response.status_code in [200, 201]:
            return response.json()
        return None
    except Exception as e:
        print(f"❌ Erro de conexão com MisticPay: {e}")
        return None

# --- WEBHOOK MISTICPAY (FLASK) ---
@app.route('/webhook', methods=['POST'])
def webhook_misticpay():
    dados = request.get_json()
    print(f"\n--- [WEBHOOK RECEBIDO] ---")
    print(dados)

    if dados and "status" in dados and dados["status"] == "COMPLETO":
        tx_id = dados.get("transactionId")
        telegram_id = atualizar_status_pago(tx_id)

        if telegram_id:
            try:
                link_convite = bot.create_chat_invite_link(ID_CANAL_VIP, member_limit=1).invite_link

                texto_sucesso = (
                    "🎉 **PAGAMENTO CONFIRMADO!** 🎉\n\n"
                    "Obrigada pelo pagamento, meu amor! Seu acesso já foi liberado automaticamente.\n"
                    "Clique no botão abaixo para entrar no meu Canal VIP secreto e aproveitar:  😈👇"
                )
                markup = types.InlineKeyboardMarkup()
                markup.add(types.InlineKeyboardButton("🔓 ENTRAR NO CANAL VIP", url=link_convite))

                bot.send_message(telegram_id, texto_sucesso, reply_markup=markup, parse_mode="Markdown")
                print(f"✅ VIP liberado com sucesso para o usuário {telegram_id}")
            except Exception as e:
                print(f"❌ Erro ao enviar link de acesso no Telegram: {e}")

    return jsonify({"status": "recebido"}), 200

# --- COMANDOS DO TELEGRAM ---
@bot.message_handler(commands=['start'])
def boas_vinda(message):
    chat_id = message.chat.id

    # Envia o log para o seu Webhook do Discord de forma assíncrona
    notificar_discord_start(message.from_user)

    texto = (
        "👑 **BEM-VINDO AO MEU PRIVADO!** 👑\n\n"
        "Oi amor, aqui é a Amanda. 😈 Estava ansiosa esperando você me chamar...\n"
        "Escolha uma opção abaixo para interagir comigo ou ver meus conteúdos:"
    )
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("🔓 ENTRAR NO CANAL VIP (R$ 10)", callback_data="gerar_pix_real"),
        types.InlineKeyboardButton("👣 Ver Prévias de Pés / Fetishes", callback_data="previas_pes_1"),
        types.InlineKeyboardButton("💬 Conversar Comigo no Privado 😈", callback_data="conversa_1")
    )
    bot.send_message(chat_id, texto, reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: True)
def tratar_botoes(call):
    chat_id = call.message.chat.id

    if call.data == "gerar_pix_real":
        bot.answer_callback_query(call.id)
        bot.send_message(chat_id, "⏳ Gerando seu código PIX dinâmico, aguarde alguns segundos...")

        tx_id = f"TX{chat_id}{int(time.time())}"
        res = criar_pix_mistic(chat_id, tx_id, valor=10)

        if res and "data" in res:
            copia_cola = res["data"]["copyPaste"]
            base64_data = res["data"]["qrCodeBase64"]

            salvar_transacao(chat_id, tx_id)

            try:
                if "," in base64_data:
                    base64_data = base64_data.split(",")[1]
                img_data = base64.b64decode(base64_data)
                photo = BytesIO(img_data)
                photo.name = 'qrcode.png'

                bot.send_photo(chat_id, photo, caption="📸 **Escaneie o QR Code acima para pagar:**")
                msg_sucesso = (
                    "📌 **OU COPIE O CÓDIGO PIX ABAIXO:**\n\n"
                    f"`{copia_cola}`\n\n"
                    "⚠️ *O pagamento é processado na hora. O robô vai te mandar o link do canal VIP aqui no chat assim que você pagar!*"
                )
                bot.send_message(chat_id, msg_sucesso, parse_mode="Markdown")
            except Exception as e:
                bot.send_message(chat_id, f"📌 **COPIE O CÓDIGO PIX ABAIXO PARA PAGAR:**\n\n`{copia_cola}`", parse_mode="Markdown")
        else:
            bot.send_message(chat_id, "❌ Erro ao gerar o PIX. Tente novamente.")

    # --- FLUXO DE PRÉVIAS ---
    elif call.data == "previas_pes_1":
        bot.answer_callback_query(call.id)
        video1_nome = "previa.mp4"
        markup_mais = types.InlineKeyboardMarkup()
        markup_mais.add(types.InlineKeyboardButton("🔥 Quer ver mais? 😈", callback_data="previas_pes_2"))
        if os.path.exists(video1_nome):
            with open(video1_nome, 'rb') as video1:
                bot.send_video(chat_id, video1, caption="Olha o que eu preparei para você... Gostou do meu pezinho? 👣", reply_markup=markup_mais)
        else:
            bot.send_message(chat_id, "Gostou do meu pezinho? 👣", reply_markup=markup_mais)

    elif call.data == "previas_pes_2":
        bot.answer_callback_query(call.id)
        video2_nome = "previa2.mp4"
        texto_venda = (
            "👣 **Gostou do que viu, meu amor?** 👣\n\n"
            "Esse rebolado é só um gostinho do que te espera lá dentro. No meu grupo VIP tem muito mais vídeos completos...\n\n"
            "Venha se divertir comigo! Assine o VIP por apenas R$ 10!"
        )
        markup_vip = types.InlineKeyboardMarkup()
        markup_vip.add(types.InlineKeyboardButton("🔓 Entrar no VIP e Ver Tudo (R$ 10)", callback_data="gerar_pix_real"))
        if os.path.exists(video2_nome):
            with open(video2_nome, 'rb') as video2:
                bot.send_video(chat_id, video2, caption=texto_venda, reply_markup=markup_vip, parse_mode="Markdown")
        else:
            bot.send_message(chat_id, texto_venda, reply_markup=markup_vip, parse_mode="Markdown")

    # --- FUNIL DE CONVERSA ---
    elif call.data == "conversa_1":
        bot.answer_callback_query(call.id)
        texto = "📥 **Amanda:** Oi lindo... Me conta, você prefere uma menina mais quietinha ou uma bem safada? 😈"
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(types.InlineKeyboardButton("Quietinha e fofa 😇", callback_data="conversa_2"), types.InlineKeyboardButton("Safada que topa tudo 🔞", callback_data="conversa_2"))
        bot.send_message(chat_id, texto, reply_markup=markup)

    elif call.data == "conversa_2":
        bot.answer_callback_query(call.id)
        texto = "📥 **Amanda:** Eu sei ser os dois... O que te chama mais atenção em mim? Meus pezinhos ou meu rebolado? 😏"
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(types.InlineKeyboardButton("Esses pezinhos lindos 👣", callback_data="conversa_3"), types.InlineKeyboardButton("Esse corpo rebolando 🍑", callback_data="conversa_3"))
        bot.send_message(chat_id, texto, reply_markup=markup)

    elif call.data == "conversa_3":
        bot.answer_callback_query(call.id)
        texto = "📥 **Amanda:** Hmm, você tem muito bom gosto... O que você faria se estivesse aqui no quarto comigo agora? 🙈"
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(types.InlineKeyboardButton("Te daria uma massagem relaxante nos pés 💆‍♂️", callback_data="conversa_4"), types.InlineKeyboardButton("Te pegaria de jeito sem pressa 🔞", callback_data="conversa_4"))
        bot.send_message(chat_id, texto, reply_markup=markup)

    elif call.data == "conversa_4":
        bot.answer_callback_query(call.id)
        texto = "📥 **Amanda:** Nossa, meu coração até acelerou... Se eu te mandasse uma foto do que estou vestindo agora, você conseguiria se controlar? 😈"
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(types.InlineKeyboardButton("Eu ia pirar completamente! 🤯", callback_data="conversa_5"), types.InlineKeyboardButton("Ia querer ver o resto na hora 🥵", callback_data="conversa_5"))
        bot.send_message(chat_id, texto, reply_markup=markup)

    elif call.data == "conversa_5":
        bot.answer_callback_query(call.id)
        texto = "📥 **Amanda:** Então você não vai aguentar o que tem lá dentro... Entra no meu VIP para a gente continuar essa conversa bem de perto... Vem? 💋"
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(types.InlineKeyboardButton("🔓 QUERO ENTRAR NO SEU VIP AGORA (R$ 10)", callback_data="gerar_pix_real"), types.InlineKeyboardButton("⬅️ Voltar ao Menu Inicial", callback_data="voltar_menu"))
        bot.send_message(chat_id, texto, reply_markup=markup)

    elif call.data == "voltar_menu":
        bot.answer_callback_query(call.id)
        texto = "👑 Escolha uma opção abaixo:"
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(types.InlineKeyboardButton("🔓 ENTRAR NO CANAL VIP (R$ 10)", callback_data="gerar_pix_real"), types.InlineKeyboardButton("👣 Ver Prévias de Pés / Fetishes", callback_data="previas_pes_1"), types.InlineKeyboardButton("💬 Conversar Comigo no Privado 😈", callback_data="conversa_1"))
        bot.send_message(chat_id, texto, reply_markup=markup)

# --- EXECUÇÃO ---
def rodar_flask():
    app.run(host='0.0.0.0', port=5000)

if __name__ == "__main__":
    iniciar_banco()

    t = Thread(target=rodar_flask)
    t.daemon = True
    t.start()

    print("bot on!")
    bot.infinity_polling()
