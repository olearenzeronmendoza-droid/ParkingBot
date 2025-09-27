def run_bot():
    token = os.environ.get("BOT_TOKEN")
    if not token:
        raise Exception("❌ BOT_TOKEN not set!")

    async def main():
        bot_app = Application.builder().token(token).build()

        # Commands
        bot_app.add_handler(CommandHandler("start", start_cmd))
        bot_app.add_handler(CommandHandler("about", about_cmd))
        bot_app.add_handler(CommandHandler("register", register_cmd))

        # Debug echo
        bot_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo_all))

        app.bot_app = bot_app
        app.bot_loop = asyncio.get_running_loop()

        print("🚀 Telegram bot is starting polling...")
        await bot_app.run_polling(close_loop=False, stop_signals=None)

    # ✅ Fix: create a new event loop for this thread
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(main())
