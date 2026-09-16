from sqlalchemy import text

from app.core.config import Settings
from app.main import create_app


async def test_lifespan_creates_a_working_session_factory(settings: Settings) -> None:
    app = create_app(settings)

    async with app.router.lifespan_context(app), app.state.session_factory() as db:
        assert await db.scalar(text("SELECT 1")) == 1
