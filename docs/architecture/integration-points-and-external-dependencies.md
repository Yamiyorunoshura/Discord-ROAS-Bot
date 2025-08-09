# Integration Points and External Dependencies

### External Services

| Service  | Purpose  | Integration Type | Key Files                      |
| -------- | -------- | ---------------- | ------------------------------ |
| Discord  | Bot Platform | discord.py API | `src/cogs/*/`                  |
| SQLite   | Database | aiosqlite | `src/core/database/`           |

### Internal Integration Points

- **Cog Communication**: Discord cog-based architecture
- **Database Access**: SQLAlchemy ORM throughout
- **Panel Interactions**: Discord interactive components
