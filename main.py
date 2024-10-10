import logging, subprocess
import os
import paramiko
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.ext import CallbackContext
import re
import psycopg2

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
db_name = os.getenv('DB_DATABASE')
rm_password = os.getenv('RM_PASSWORD')
DB_HOST = os.getenv('DB_HOST')
DB_USER = os.getenv('DB_USER')
DB_PASSWORD = os.getenv('DB_PASSWORD')
DB_PORT = os.getenv('DB_PORT')

email_pattern = r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+'
phone_pattern = r'(?:\+7|8)[\s-]?\(?\d{3}\)?[\s-]?\d{3}[\s-]?\d{2}[\s-]?\d{2}'
password_pattern = r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[!@#$%^&*()])[A-Za-z\d!@#$%^&*()]{8,}$'


def log_user_action(user_id, command, status):
    logger.info(f"Пользователь {user_id} использует команду {command}. Статус: {status}")


def run_ssh_command(command, use_sudo=False):
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(RM_HOST, port=RM_PORT, username=RM_USER, password=RM_PASSWORD)

        if use_sudo:
            command = f"echo {RM_PASSWORD} | sudo -S {command}"

        stdin, stdout, stderr = ssh.exec_command(command)
        output = stdout.read().decode('utf-8')
        ssh.close()

        return output.strip() if output else stderr.read().decode('utf-8').strip()

    except Exception as e:
        logger.error(f"Ошибка SSH подключения: {e}")
        return f"Ошибка подключения к серверу: {e}"


def run_ssh_command_db(command, use_sudo=False):
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(DB_HOST, port=DB_PORT, username=DB_USER, password=DB_PASSWORD)

        if use_sudo:
            command = f"echo {RM_PASSWORD} | sudo -S {command}"

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
        "Привет! Я бот для поиска email и номеров телефонов, проверки сложности паролей и много другого. "
        "Введите одну из команд: "
        "/find_email, /find_phone_number,  /verify_password" "\n"
        "/get_repl_logs, /get_emails, /get_phone_numbers" "\n"
        "/get_release, /get_uname, /get_uptime" "\n"
        "/get_df, /get_free, /get_mpstat" "\n"
        "/get_w, /get_auths, /get_critical" "\n"
        "/get_ps, /get_ss, /get_apt_list" "\n"
        "/get_services"
    )
    log_user_action(user_id, "/start", "выполнена")


async def find_email(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    await update.message.reply_text("Отправь мне текст, в котором нужно найти email-адреса.")
    context.user_data['search_mode'] = 'email'
    logger.info(f"Пользователь {user_id} выбрал поиск email")


async def find_phone_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    await update.message.reply_text("Отправь мне текст, в котором нужно найти номера телефонов.")
    context.user_data['search_mode'] = 'phone'
    logger.info(f"Пользователь {user_id} выбрал поиск номеров телефонов")


async def verify_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    await update.message.reply_text("Отправь мне пароль, который нужно проверить.")
    context.user_data['search_mode'] = 'password'
    log_user_action(user_id, "/verify_password", "запущена")


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text
    search_mode = context.user_data.get('search_mode')

    if not context.user_data.get('pending_confirmation'):
        if search_mode == 'email':
            emails = re.findall(email_pattern, text)
            if emails:
                context.user_data['emails'] = emails
                await update.message.reply_text(
                    f"Найдены email-адреса: {', '.join(emails)}\nЗаписать их в базу данных? (да/нет)")
                context.user_data['pending_confirmation'] = 'email'
                logger.info(f"Пользователь {user_id} нашел email: {', '.join(emails)}")
            else:
                await update.message.reply_text("Email-адреса не найдены.")
                logger.info(f"Пользователь {user_id} не нашел email")

        elif search_mode == 'phone':
            phones = re.findall(phone_pattern, text)
            if phones:
                context.user_data['phones'] = phones
                await update.message.reply_text(
                    f"Найдены номера телефонов: {', '.join(phones)}\nЗаписать их в базу данных? (да/нет)")
                context.user_data['pending_confirmation'] = 'phone'
                logger.info(f"Пользователь {user_id} нашел номера телефонов: {', '.join(phones)}")
            else:
                await update.message.reply_text("Номера телефонов не найдены.")
                logger.info(f"Пользователь {user_id} не нашел номера телефонов")

        elif search_mode == 'password':
            if re.match(password_pattern, text):
                await update.message.reply_text("Пароль сложный.")
                logger.info(f"Пользователь {user_id} ввел сложный пароль")
            else:
                await update.message.reply_text("Пароль простой.")
                logger.info(f"Пользователь {user_id} ввел простой пароль")

        else:
            await update.message.reply_text(
                "Выбери одну из следующих команд: "
                "/find_email, /find_phone_number,  /verify_password" "\n"
                "/get_repl_logs, /get_emails, /get_phone_numbers" "\n"
                "/get_release, /get_uname, /get_uptime" "\n"
                "/get_df, /get_free, /get_mpstat" "\n"
                "/get_w, /get_auths, /get_critical" "\n"
                "/get_ps, /get_ss, /get_apt_list" "\n"
                "/get_services")
            logger.info(f"Пользователь {user_id} не выбрал команду")

    else:
        confirmation = text.lower()

        if confirmation == 'да':
            pending_action = context.user_data.get('pending_confirmation')

            if pending_action == 'email':
                emails = context.user_data.get('emails', [])
                if emails:
                    await save_emails_to_db(emails, update)
                else:
                    await update.message.reply_text("Не удалось найти email-адреса для записи.")
            elif pending_action == 'phone':
                phones = context.user_data.get('phones', [])
                if phones:
                    await save_phones_to_db(phones, update)
                else:
                    await update.message.reply_text("Не удалось найти номера телефонов для записи.")

            context.user_data['pending_confirmation'] = None
            context.user_data.pop('emails', None)
            context.user_data.pop('phones', None)

            await update.message.reply_text(
                "Данные записаны. Выберите одну из следующих команд: "
                "/find_email, /find_phone_number,  /verify_password" "\n"
                "/get_repl_logs, /get_emails, /get_phone_numbers" "\n"
                "/get_release, /get_uname, /get_uptime" "\n"
                "/get_df, /get_free, /get_mpstat" "\n"
                "/get_w, /get_auths, /get_critical" "\n"
                "/get_ps, /get_ss, /get_apt_list" "\n"
                "/get_services"
            )

        elif confirmation == 'нет':
            await update.message.reply_text("Запись отменена.")
            logger.info(f"Пользователь {user_id} отменил запись данных")
            context.user_data['pending_confirmation'] = None
            context.user_data.pop('emails', None)
            context.user_data.pop('phones', None)

            await update.message.reply_text(
                "Запись отменена. Выберите одну из следующих команд: "
                "/find_email, /find_phone_number,  /verify_password" "\n"
                "/get_repl_logs, /get_emails, /get_phone_numbers" "\n"
                "/get_release, /get_uname, /get_uptime" "\n"
                "/get_df, /get_free, /get_mpstat" "\n"
                "/get_w, /get_auths, /get_critical" "\n"
                "/get_ps, /get_ss, /get_apt_list" "\n"
                "/get_services"
            )

        else:
            await update.message.reply_text("Пожалуйста, ответьте 'да' или 'нет'.")


async def save_emails_to_db(emails, update):
    success = True
    for email in emails:
        sql_query = f"INSERT INTO email_address(email) VALUES ('{email}');"
        result = run_sql_command(sql_query)
        if 'ERROR' in result:
            success = False
            await update.message.reply_text(f"Ошибка при записи email {email}: {result}")

    if success:
        await update.message.reply_text("Все email-адреса успешно записаны в базу данных.")
    else:
        await update.message.reply_text("Некоторые email-адреса не были записаны из-за ошибок.")


async def save_phones_to_db(phones, update):
    success = True
    for phone in phones:
        sql_query = f"INSERT INTO phone_number(phone) VALUES ('{phone}');"
        result = run_sql_command(sql_query)
        if 'ERROR' in result:
            success = False
            await update.message.reply_text(f"Ошибка при записи номера телефона {phone}: {result}")

    if success:
        await update.message.reply_text("Все номера телефонов успешно записаны в базу данных.")
    else:
        await update.message.reply_text("Некоторые номера телефонов не были записаны из-за ошибок.")


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


async def get_repl_logs(update: Update, context: CallbackContext) -> None:
    try:
        # Выполнение команды для получения логов
        result = subprocess.run(
            ["tail", "-n", "30", "/var/log/postgresql/postgresql.log"],
            capture_output=True,
            text=True
        )
        logs = result.stdout
        if logs:
            await update.message.reply_text(f"Последние репликационные логи:\n{logs}")
        else:
            await update.message.reply_text("Репликационные логи не найдены.")
    except Exception as e:
        await update.message.reply_text(f"Ошибка при получении логов: {str(e)}")



def run_sql_command(sql_query):
    db_name = os.getenv('DB_DATABASE')
    db_user = os.getenv('DB_USER')
    db_password = os.getenv('DB_PASSWORD')
    db_host = os.getenv('DB_HOST')
    db_port = os.getenv('DB_PORT')

    try:
        # Устанавливаем соединение с базой данных
        conn = psycopg2.connect(
            dbname=db_name,
            user=db_user,
            password=db_password,
            host=db_host,
            port=db_port
        )
        cursor = conn.cursor()
        
        # Выполнение SQL-запроса
        cursor.execute(sql_query)
        
        # Если запрос предполагает получение данных (SELECT)
        if sql_query.strip().lower().startswith("select"):
            result = cursor.fetchall()
            conn.close()
            return result
        
        # Если запрос выполняет действие (INSERT, UPDATE, DELETE и т.д.)
        conn.commit()
        conn.close()
        return "Команда успешно выполнена"

    except Exception as e:
        # Логирование ошибки
        logger.error(f"Ошибка выполнения SQL: {e}")
        return f"Ошибка выполнения SQL: {e}"




async def get_emails(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    sql_query = "SELECT email FROM email_address"

    result = run_sql_command(sql_query)

    if result:
        await update.message.reply_text(f"Email-адреса:\n{result}")
        log_user_action(user_id, "Получение email-адресов", "успешно")
    else:
        await update.message.reply_text("Не удалось получить email-адреса.")
        log_user_action(user_id, "Получение email-адресов", "ошибка")


async def get_phone_numbers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    sql_query = "SELECT phone FROM phone_number"

    result = run_sql_command(sql_query)

    if result:
        await update.message.reply_text(f"Номера телефонов:\n{result}")
        log_user_action(user_id, "Получение номеров телефонов", "успешно")
    else:
        await update.message.reply_text("Не удалось получить номера телефонов.")
        log_user_action(user_id, "Получение номеров телефонов", "ошибка")


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
    app.add_handler(CommandHandler("get_repl_logs", get_repl_logs))
    app.add_handler(CommandHandler("get_emails", get_emails))
    app.add_handler(CommandHandler("get_phone_numbers", get_phone_numbers))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    app.run_polling()


if __name__ == '__main__':
    main()
