STICKER_IDS = {
    'welcome': 'CAACAgQAAxkBAAERYvFqLYSw1e7mqt0LreZQ5iAXYLYgwQACmRIAAnZ5WVFtqjwTk98wTTwE',
    'success': 'CAACAgIAAxkBAAERYvNqLYUtRvn80WovxY4pmS_w0Gl4IAAC_gADVp29CtoEYTAu-df_PAQ',
    'payment': 'CAACAgQAAxkBAAERYvVqLYW--BzhGTmOkLiUrL0Nqi0IewAC9BMAAkziGVLzMxdaDdc2ojwE',
    'config': 'CAACAgEAAxkBAAERYxpqLZ_BdzW1SHvfF8lclSlkQ2bkDwACEgAD-wn4TyfquP1sDazXPAQ',
    'error': 'CAACAgIAAxkBAAERYxhqLZ-DqmtKnvuOezC6qxlmw3JxrgACQxgAArbIKUh1S6tFvSw1WDwE',
    'referral': 'CAACAgQAAxkBAAERYvtqLYdkDe9oPhYCCzd5jRmj9eo-tgAC6xQAAndYgVIvZzhm7RBW9jwE',
    'money': 'CAACAgQAAxkBAAERYv1qLYg2VGtarsPxg7UUuJE5cJwsxgACbRIAAkMYUVBj6dJT6kRbJjwE',
}


async def send_sticker(bot, chat_id: int, sticker_key: str) -> bool:
    """Send a sticker with fallback to empty string (no error)."""
    sticker_id = STICKER_IDS.get(sticker_key)
    if sticker_id:
        try:
            await bot.send_sticker(chat_id, sticker_id)
            return True
        except Exception:
            pass
    return False
