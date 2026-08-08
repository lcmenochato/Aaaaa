# ==============================================================================
# SISTEMA COMPLETO DE VENDAS DE CURSOS (TELEGRAM BOT + GOATPAY PIX)
# ==============================================================================

import os
import requests
from flask import Flask, request, jsonify

# ------------------------------------------------------------------------------
# 1. CONFIGURAÇÕES PRINCIPAIS (INSIRA AS SUAS CHAVES AQUI)
# ------------------------------------------------------------------------------

# Chave de API da GoatPay (Obtida em: Dashboard GoatPay -> Integrações -> Chaves de API)
GOATPAY_API_KEY = os.getenv("GOATPAY_API_KEY", "gp_live_e8f273876ef9e2938ec1517dcf33a1d4cce3c733bb23e6ba")

# Token do Bot do Telegram (Obtido com o @BotFather)
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8685151517:AAG_v3Nx3F5NedqTNRJCMrC3tX6DsJODFFk")

# Link do Grupo "Mais Cursos" / Grupo Geral
LINK_MAIS_CURSOS = "https://t.me/+I3vVaPwoIsg4ZGIx"

# URL base da API da GoatPay
GOATPAY_BASE_URL = "https://api.goatpay.com.br/v1"

# ------------------------------------------------------------------------------
# 2. CATÁLOGO DE PRODUTOS E LINKS DE ENTREGA
# ------------------------------------------------------------------------------

PRODUTOS = {
    "vip_semanal": {
        "nome": "Vip semanal",
        "preco": 5.50,
        "link_entrega": ""  # Cole aqui o link de acesso exclusivo do Curso Básico
    },
    "vip_mensal": {
        "nome": "Vip mensal",
        "preco": 7.90,
        "link_entrega": ""  # Cole aqui o link de acesso exclusivo do Curso Intermediário
    },
    "vip_vitalicio": {
        "nome": "Vip vitalicio",
        "preco": 10,90,
        "link_entrega": ""  # Cole aqui o link de acesso exclusivo do Curso Completo
    }
}

def obter_link_entrega(produto_id: str) -> str:
    """Retorna o link do curso ou o link do grupo geral como fallback."""
    produto = PRODUTOS.get(produto_id)
    if not produto:
        return LINK_MAIS_CURSOS
    
    link = produto.get("link_entrega", "").strip()
    return link if link else LINK_MAIS_CURSOS

# ------------------------------------------------------------------------------
# 3. INTEGRAÇÃO COM A API DA GOATPAY (GERAÇÃO DE PIX)
# ------------------------------------------------------------------------------

def criar_pix_goatpay(produto_id: str, chat_id: str):
    """
    Gera cobrança PIX na GoatPay e retorna código PIX Copia e Cola e QR Code Base64.
    """
    if produto_id not in PRODUTOS:
        raise ValueError("Produto não cadastrado.")

    produto = PRODUTOS[produto_id]
    
    headers = {
        "X-API-Key": GOATPAY_API_KEY,
        "Content-Type": "application/json"
    }
    
    payload = {
        "amount": produto["preco"],
        "description": f"Compra: {produto['nome']}",
        "externalReference": f"{produto_id}|{chat_id}"  # Associa o produto e o cliente Telegram
    }

    url = f"{GOATPAY_BASE_URL}/payment-pix/create"
    response = requests.post(url, json=payload, headers=headers)
    
    if response.status_code == 200:
        res_data = response.json()
        if res_data.get("success"):
            data = res_data.get("data", {})
            return {
                "transacao_id": data.get("id"),
                "pix_copia_e_cola": data.get("copyPaste"),
                "qr_code_base64": data.get("qrCodeBase64")
            }
        else:
            raise Exception(f"Erro na GoatPay: {res_data.get('message')}")
    else:
        raise Exception(f"Erro HTTP {response.status_code}: {response.text}")

# ------------------------------------------------------------------------------
# 4. ENVIOS E MENUS NO TELEGRAM
# ------------------------------------------------------------------------------

def enviar_mensagem_telegram(chat_id: str, texto: str, reply_markup=None):
    """Envia uma mensagem para o utilizador via Telegram Bot API."""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": texto,
        "parse_mode": "Markdown"
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
        
    try:
        requests.post(url, json=payload)
    except Exception as e:
        print(f"Erro ao enviar mensagem Telegram: {e}")

def enviar_menu_principal(chat_id: str):
    """
    Envia o menu de cursos com botões inline de PAGAMENTO e o botão 'Grupo de previas'.
    """
    texto = (
        " *Bem-vindo(a) ao meu privado *\n\n"
        "Quer ver meu lado putinha sozinha e acompanhada de todas as formas? "
      ""
        "+3 Vídeos novos todos os dias ✅😈"
      "💜 Mais de 150 Fotos e vídeos do meu privacy "
      "💜 Sexo com meu primo, tio e prima"
      "💜 Sorteio a cada 5 dias de chamada de vídeo"
      ""
      "🔥 Espanhola    🎥 Videos personalizados"
      "🔥 Fetiches        🎥 Gozando gostoso"
      "🔥 Sexo anal       🎥 Me masturbando"
      ""
      "✅ 7 Dias de garantia para pedir o seu dinheiro de volta"
      "✅ Compra 100% Confiável e discreta"
      "✅ Atualizações diárias no grupo de prévias"
    )
    
    # Teclado Inline: Botões de Pagamento + Botão de Redirecionamento
    keyboard = {
        "inline_keyboard": [
            [
                {
                    "text": " Comprar Vip semanal - R$ 5,50",
                    "callback_data": "pagar_vip_semanal"
                }
            ],
            [
                {
                    "text": "Comprar Vip mensal - R$ 7,90",
                    "callback_data": "pagar_vip_mensal"
                }
            ],
            [
                {
                    "text": "Comprar Vip Vitalicio - R$ 10,90",
                    "callback_data": "pagar_vip_vitalicio"
                }
            ],
            [
                {
                    "text": "Grupo de previas ",
                    "url": LINK_MAIS_CURSOS
                }
            ]
        ]
    }
    
    enviar_mensagem_telegram(chat_id, texto, reply_markup=keyboard)

# ------------------------------------------------------------------------------
# 5. SERVIDOR FLASK (WEBHOOK TELEGRAM + WEBHOOK GOATPAY)
# ------------------------------------------------------------------------------

app = Flask(__name__)

# --- WEBHOOK DO TELEGRAM ---
@app.route("/telegram/webhook", methods=["POST"])
def telegram_webhook():
    """
    Processa mensagens e cliques em botões do Telegram.
    """
    update = request.json or {}
    
    # 1. Quando o utilizador envia uma mensagem (ex: /start)
    if "message" in update:
        message = update["message"]
        chat_id = message.get("chat", {}).get("id")
        text = message.get("text", "")
        
        if text.startswith("/start"):
            enviar_menu_principal(chat_id)
            return jsonify({"status": "ok"}), 200

    # 2. Quando o utilizador clica num botão de PAGAMENTO
    elif "callback_query" in update:
        callback = update["callback_query"]
        chat_id = callback.get("message", {}).get("chat", {}).get("id")
        callback_data = callback.get("data", "")
        
        # Mapeia qual curso foi clicado
        mapa_produtos = {
            "pagar_vip_semanal": "vip_semanal",
            "pagar_vip_mensal": "vip_mensal",
            "pagar_vip_vitalicio": "vip_vitalicio"
        }
        
        if callback_data in mapa_produtos:
            produto_id = mapa_produtos[callback_data]
            produto = PRODUTOS[produto_id]
            
            enviar_mensagem_telegram(chat_id, f"⏳ Gerando PIX para o *{produto['nome']}*...")
            
            try:
                pix_info = criar_pix_goatpay(produto_id, str(chat_id))
                copia_e_cola = pix_info["pix_copia_e_cola"]
                
                msg_pix = (
    f"✅ *PIX Gerado com Sucesso!*\n\n"
    f"📌 *Produto:* {produto['nome']}\n"
    f"💰 *Valor:* R$ {produto['preco']:.2f}\n\n"
    f"👇 *Copie o código PIX abaixo e pague no app do seu banco:*\n\n"
    f"`{copia_e_cola}`\n\n"
    f" *Após o pagamento, seu acesso será liberado automaticamente aqui!*"
)
                enviar_mensagem_telegram(chat_id, msg_pix)
                
            except Exception as e:
                enviar_mensagem_telegram(chat_id, f"❌ Erro ao gerar PIX: {str(e)}")
                
        return jsonify({"status": "ok"}), 200

    return jsonify({"status": "ignored"}), 200


# --- WEBHOOK DA GOATPAY (CONFIRMAÇÃO AUTOMÁTICA) ---
@app.route("/webhook/goatpay", methods=["POST"])
def goatpay_webhook():
    """
    Recebe aviso da GoatPay quando o PIX é pago e entrega o link do curso.
    """
    payload = request.json or {}
    
    event_type = payload.get("event")
    data = payload.get("data", {})
    
    if event_type == "payment.paid":
        external_ref = data.get("externalReference", "")
        
        if "|" in external_ref:
            produto_id, chat_id = external_ref.split("|", 1)
            
            if produto_id in PRODUTOS:
                produto = PRODUTOS[produto_id]
                link_acesso = obter_link_entrega(produto_id)
                
                msg_sucesso = (
    f"🎉 *Pagamento Confirmado!*\n\n"
    f"Obrigada por adquirir o *{produto['nome']}*.\n\n"
    f"🔗 *Acesse meus conteudos pelo link abaixo:*\n"
    f"{link_acesso}\n\n"
    f"Bom proveito!"
)
                
                enviar_mensagem_telegram(chat_id, msg_sucesso)
                return jsonify({"status": "success", "delivered": True}), 200

    return jsonify({"status": "ignored"}), 200


# ------------------------------------------------------------------------------
# EXECUÇÃO DO SERVIDOR
# ------------------------------------------------------------------------------

if __name__ == "__main__":
    print("Servidor rodando e pronto...")
    app.run(host="0.0.0.0", port=5000)
