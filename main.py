import logging
import os
import paramiko
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
import re

load_dotenv()

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[logging.FileHandler("bot.log", encoding="utf-8")]
)
logger = logging.getLogger(__name__)

TOKEN = os.getenv('TOKEN')
RM_HOST = os.getenv('RM_HOST')
RM_PORT = int(os.getenv('RM_PORT'))
RM_USER = os.getenv('RM_USER')
RM_PASSWORD = os.getenv('RM_PASSWORD')

email_pattern = r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+'
phone_pattern = r'(?:\+7|8)[\s-]?\(?\d{3}\)?[\s-]?\d{3}[\s-]?\d{2}[\s-]?\d{2}'
password_pattern = r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[!@#$%^&*()])[A-Za-z\d!@#$%^&*()]{8,}$'


def log_user_action(user_id, command, status):
    logger.info(f"Пользователь {user_id} использует команду {command}. Статус: {status}")


def run_ssh_command(command):
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(RM_HOST, port=RM_PORT, username=RM_USER, password=RM_PASSWORD)

        stdin, stdout, stderr = ssh.exec_command(command)
        output = stdout.read().decode('utf-8')
        ssh.close()

        return output.strip() if output else stderr.read().decode('utf-8').strip()

    except Exception as e:
        logger.error(f"Ошибка SSH подключения: {e}")
        return f"Ошибка подключения к серверу: {e}"


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    await update.message.reply_text(
        "Привет! Я бот для поиска email и номеров телефонов, проверки сложности паролей и мониторинга системы. Введи /find_email, /find_phone_number, /verify_password или любую команду мониторинга, чтобы начать.")
    log_user_action(user_id, "/start", "выполнена")


async def find_email(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    await update.message.reply_text("Отправь мне текст, в котором нужно найти email-адреса.")
    context.user_data['search_mode'] = 'email'
    log_user_action(user_id, "/find_email", "запущена")


async def find_phone_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    await update.message.reply_text("Отправь мне текст, в котором нужно найти номера телефонов.")
    context.user_data['search_mode'] = 'phone'
    log_user_action(user_id, "/find_phone_number", "запущена")


async def verify_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    await update.message.reply_text("Отправь мне пароль, который нужно проверить.")
    context.user_data['search_mode'] = 'password'
    log_user_action(user_id, "/verify_password", "запущена")


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text
    search_mode = context.user_data.get('search_mode')

    if search_mode == 'email':
        emails = re.findall(email_pattern, text)
        if emails:
            await update.message.reply_text(f"Найдены email-адреса: {', '.join(emails)}")
            log_user_action(user_id, "Поиск email", "успешно")
        else:
            await update.message.reply_text("Email-адреса не найдены.")
            log_user_action(user_id, "Поиск email", "не найдены")
    elif search_mode == 'phone':
        phones = re.findall(phone_pattern, text)
        phones = [phone for phone in phones if phone.strip()]
        if phones:
            formatted_phones = ', '.join(phones)
            await update.message.reply_text(f"Найдены номера телефонов: {formatted_phones}")
            log_user_action(user_id, "Поиск номеров", "успешно")
        else:
            await update.message.reply_text("Номера телефонов не найдены.")
            log_user_action(user_id, "Поиск номеров", "не найдены")
    elif search_mode == 'password':
        if re.match(password_pattern, text):
            await update.message.reply_text("Пароль сложный.")
            log_user_action(user_id, "Проверка пароля", "сложный")
        else:
            await update.message.reply_text("Пароль простой.")
            log_user_action(user_id, "Проверка пароля", "простой")
    else:
        await update.message.reply_text(
            "Выбери команду /find_email, /find_phone_number или /verify_password для начала поиска.")
        log_user_action(user_id, "Ошибка", "не выбрана команда")


async def get_release(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = run_ssh_command("cat /etc/*release")
    await update.message.reply_text(f"Информация о релизе:\n{result}")


async def get_uname(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = run_ssh_command("uname -a")
    await update.message.reply_text(f"Информация о системе:\n{result}")


async def get_uptime(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = run_ssh_command("uptime")
    await update.message.reply_text(f"Время работы системы:\n{result}")


async def get_df(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = run_ssh_command("df -h")
    await update.message.reply_text(f"Состояние файловой системы:\n{result}")


async def get_free(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = run_ssh_command("free -h")
    await update.message.reply_text(f"Состояние оперативной памяти:\n{result}")


async def get_mpstat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = run_ssh_command("mpstat")
    await update.message.reply_text(f"Производительность системы:\n{result}")


async def get_w(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = run_ssh_command("w")
    await update.message.reply_text(f"Работающие пользователи:\n{result}")


async def get_auths(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = run_ssh_command("last -n 10")
    await update.message.reply_text(f"Последние 10 входов в систему:\n{result}")


async def get_critical(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = run_ssh_command("journalctl -p crit -n 5")
    await update.message.reply_text(f"Последние 5 критических событий:\n{result}")


async def get_ps(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = run_ssh_command("ps aux")

    file_path = "ps_output.txt"
    with open(file_path, "w") as file:
        file.write(result)

    with open(file_path, "rb") as file:
        await update.message.reply_document(file)

    os.remove(file_path)


async def get_ss(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = run_ssh_command("ss -tuln")
    await update.message.reply_text(f"Используемые порты:\n{result}")


async def get_apt_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args or context.args[0].lower() == 'all':
        result = run_ssh_command("apt list --installed")
        file_path = "apt_list.txt"
        with open(file_path, "w") as file:
            file.write(result)

        with open(file_path, "rb") as file:
            await update.message.reply_document(file)

        os.remove(file_path)
    else:
        package_name = context.args[0]
        result = run_ssh_command(f"apt show {package_name}")

        if result:
            await update.message.reply_text(f"Информация о пакете {package_name}:\n{result}")
        else:
            await update.message.reply_text(f"Пакет {package_name} не найден.")


async def get_services(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = run_ssh_command("systemctl list-units --type=service")
    file_path = "get_services.txt"
    with open(file_path, "w", encoding="utf-8") as file:
        file.write(result)

    with open(file_path, "rb") as file:
        await update.message.reply_document(file)

    os.remove(file_path)

def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("find_email", find_email))
    app.add_handler(CommandHandler("find_phone_number", find_phone_number))
    app.add_handler(CommandHandler("verify_password", verify_password))
    app.add_handler(CommandHandler("get_release", get_release))
    app.add_handler(CommandHandler("get_uname", get_uname))
    app.add_handler(CommandHandler("get_uptime", get_uptime))
    app.add_handler(CommandHandler("get_df", get_df))
    app.add_handler(CommandHandler("get_free", get_free))
    app.add_handler(CommandHandler("get_mpstat", get_mpstat))
    app.add_handler(CommandHandler("get_w", get_w))
    app.add_handler(CommandHandler("get_auths", get_auths))
    app.add_handler(CommandHandler("get_critical", get_critical))
    app.add_handler(CommandHandler("get_ps", get_ps))
    app.add_handler(CommandHandler("get_ss", get_ss))
    app.add_handler(CommandHandler("get_apt_list", get_apt_list))
    app.add_handler(CommandHandler("get_services", get_services))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    app.run_polling()


if __name__ == '__main__':
    main()
