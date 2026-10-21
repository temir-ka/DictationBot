from bot.handlers import admin, measurement, settings, start, stats, workout

# Порядок важен: команды из первых роутеров срабатывают раньше
# «ловушек» состояний замера (measurement — последним).
routers = [
    admin.router,
    start.router,
    stats.router,
    settings.router,
    workout.router,
    measurement.router,
]
