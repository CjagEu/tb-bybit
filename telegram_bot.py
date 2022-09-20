import telegram

TELEGRAM_TOKEN = '5497695474:AAHGUgF0nZBsb4DR67lIEFYTxw2tjxhjeL0'


def send_message(msg):
    bot = telegram.Bot(TELEGRAM_TOKEN)

    bot.send_message(chat_id="-1001579219770", text="*" + msg + "*", parse_mode=telegram.ParseMode.MARKDOWN)


if __name__ == '__main__':
    send_message()
