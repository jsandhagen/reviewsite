# PostgreSQL Migration Plan

## Overview
This plan details the complete conversion from SQLite to PostgreSQL while maintaining 100% functionality.

## Database Structure Analysis

### Current State
- **Main database file**: `database.py` (79KB, ~1845 lines)
- **Database**: SQLite (`ratings.db`)
- **Tables**: 7 tables (users, games, user_scores, steam_update_log, friends, superlatives, user_superlatives)
- **Connection pattern**: Context manager `get_db()` with hardcoded DB path
- **Direct DB usage**: 16 Python files use sqlite3 directly

### SQLite-Specific Features to Convert

#### 1. Data Types & Auto-increment
- `INTEGER PRIMARY KEY AUTOINCREMENT` → `SERIAL PRIMARY KEY` or `BIGSERIAL`
- All other types (TEXT, REAL, TIMESTAMP) are compatible

#### 2. SQL Syntax Differences
- `ON CONFLICT(user_id, game_id) DO UPDATE SET ...` → Needs constraint name in PostgreSQL
- `PRAGMA` statements → Remove (PostgreSQL doesn't use PRAGMA)
- `NULLS LAST` → Already PostgreSQL-compatible
- `CURRENT_TIMESTAMP` → Compatible

#### 3. Connection & Row Handling
- `sqlite3.connect()` → `psycopg2.connect()` or connection pool
- `sqlite3.Row` → `psycopg2.extras.RealDictCursor`
- `sqlite3.IntegrityError` → `psycopg2.IntegrityError`

#### 4. Transaction Management
- SQLite auto-commit in context → PostgreSQL needs explicit transaction handling
- `conn.commit()` and `conn.rollback()` work the same

## Implementation Steps

### Phase 1: Environment & Dependencies Setup

#### 1.1 Update requirements.txt
**File**: `requirements.txt`
- Add `psycopg2-binary>=2.9.0` (or `psycopg2>=2.9.0` for production)
- Keep Flask and other dependencies

#### 1.2 Update .env configuration
**Files**: `.env`, `.env.example`
- Add `DATABASE_URL` environment variable
- Format: `postgresql://username:password@host:port/database`
- Remove any SQLite-specific configuration

### Phase 2: Core Database Module Conversion

#### 2.1 Update database.py
**File**: `database.py`

**Connection Management**:
- Replace `sqlite3` imports with `psycopg2` and `psycopg2.extras`
- Replace `DB_PATH` with `DATABASE_URL` from environment
- Replace `sqlite3.Row` with `RealDictCursor`
- Remove `PRAGMA encoding = 'UTF-8'` (not needed in PostgreSQL)
- Update `get_db()` context manager for PostgreSQL connection

**Schema Changes in init_db()**:
1. **Primary Keys**:
   - `id INTEGER PRIMARY KEY AUTOINCREMENT` → `id SERIAL PRIMARY KEY`
   - `game_id INTEGER PRIMARY KEY AUTOINCREMENT` → `game_id SERIAL PRIMARY KEY`

2. **ALTER TABLE handling**:
   - SQLite uses try/except for column existence checks
   - PostgreSQL should use: `ALTER TABLE ... ADD COLUMN IF NOT EXISTS ...`
   - Remove all try/except blocks around ALTER statements

3. **UPSERT statements**:
   - Line 736: `ON CONFLICT(user_id, game_id) DO UPDATE SET ...`
     → Add constraint name or use column list
   - Line 805: Same pattern
   - App.py lines 1039, 1153: Same pattern
   - steam_updater.py line 149: Same pattern

4. **Foreign Keys**:
   - SQLite requires `PRAGMA foreign_keys = ON`
   - PostgreSQL has them enabled by default (remove PRAGMA)

5. **Check Constraints**:
   - Already compatible (CHECK clauses work the same)

6. **Timestamps**:
   - `TIMESTAMP DEFAULT CURRENT_TIMESTAMP` → Compatible
   - Python datetime handling with `strftime` → Compatible

**Function Updates**:
- Update all functions using `sqlite3.IntegrityError` → `psycopg2.IntegrityError`
- Review all raw SQL for compatibility
- Test CASE WHEN statements (already compatible)

#### 2.2 Update Query Syntax
**Specific locations**:

1. **get_all_games_with_avg_scores()** (line 1055):
   - `ORDER BY avg_enjoyment DESC NULLS LAST, g.name ASC`
   - ✓ Already PostgreSQL-compatible

2. **UPSERT Operations**:
   - Create unique constraints for UPSERT targets
   - Example: `CREATE UNIQUE INDEX IF NOT EXISTS idx_user_game ON user_scores(user_id, game_id)`

### Phase 3: Application Code Updates

#### 3.1 Update app.py
**File**: `app.py`

Changes needed:
- Import updates (psycopg2 instead of sqlite3)
- Line 2090: SQLite MIME type in backup endpoint → Update for PostgreSQL backup method
- Line 2115: `SELECT name FROM sqlite_master` → `SELECT tablename FROM pg_tables WHERE schemaname='public'`
- Lines with UPSERT (1039, 1153): Update constraint handling

#### 3.2 Update Utility Scripts
**Files requiring updates** (16 total):
1. `fix_skyrim_cover.py` - Direct sqlite3 usage
2. `deduplicate_games.py` - Direct sqlite3 usage
3. `fix_superlative_games.py` - Direct sqlite3 usage
4. `reset_superlatives.py` - Direct sqlite3 usage
5. `restore_and_update.py` - Uses PRAGMA statements
6. `scripts/export_db_schema_excel.py` - sqlite_master queries
7. `verify_aggregates.py` - Direct connection
8. `show_schema.py` - sqlite_master and PRAGMA queries
9. `steam_updater.py` - UPSERT operation (line 149)
10. `setup_admin.py` - Direct connection
11. `migrate_superlatives.py` - Schema creation
12. `migrate_review_points.py` - If it exists
13. `update_aggregates.py` - Direct connection
14. `make_admin.py` - Direct connection
15. `backend.py` - If still used
16. `steam_integration.py` - Check for DB operations

**Pattern for all scripts**:
- Replace `import sqlite3` with PostgreSQL connection
- Use `get_db()` from database.py instead of direct connections where possible
- Update schema introspection queries

### Phase 4: Schema Migration Script

#### 4.1 Create PostgreSQL Schema
**New file**: `create_postgres_schema.py`

Script should:
1. Connect to PostgreSQL using DATABASE_URL
2. Drop existing tables (with confirmation)
3. Create all tables with PostgreSQL syntax
4. Create indexes
5. Create constraints
6. Populate superlatives table

#### 4.2 Data Migration Script
**New file**: `migrate_sqlite_to_postgres.py`

Script should:
1. Read from SQLite database
2. Connect to PostgreSQL
3. Migrate all data preserving IDs
4. Verify row counts
5. Check foreign key integrity
6. Reset sequences for SERIAL columns

### Phase 5: Connection Pooling (Optional but Recommended)

#### 5.1 Implement Connection Pool
**Update**: `database.py`

- Use `psycopg2.pool.SimpleConnectionPool` or `psycopg2.pool.ThreadedConnectionPool`
- Initialize pool on app startup
- Update `get_db()` to use pool
- Ensure proper connection cleanup

Benefits:
- Better performance with concurrent users
- Proper connection management
- Prevents connection exhaustion

### Phase 6: Testing Strategy

#### 6.1 Unit Tests
Create tests for:
- Database connection and context manager
- All CRUD operations
- UPSERT operations
- Transaction rollback
- Concurrent access

#### 6.2 Integration Tests
Test all features:
- User registration and login
- Game addition and updates
- Score submissions
- Friend requests
- Superlatives calculation
- Steam integration
- CSV import/export
- Backlog management

#### 6.3 Data Integrity Tests
Verify:
- Foreign key constraints work
- Unique constraints work
- Check constraints work
- Cascade deletes work
- Default values apply correctly

#### 6.4 Migration Validation
Compare SQLite vs PostgreSQL:
- Row counts for all tables
- Sample data verification
- Aggregate calculations
- Query results

### Phase 7: Deployment Strategy

#### 7.1 Development Environment
1. Install PostgreSQL locally
2. Create development database
3. Test migration script
4. Verify all functionality
5. Performance testing

#### 7.2 Production Migration
1. **Backup SQLite database** (critical!)
2. Schedule maintenance window
3. Deploy new code (with DATABASE_URL)
4. Run migration script
5. Verify data integrity
6. Monitor for errors
7. Keep SQLite backup for rollback

#### 7.3 Rollback Plan
If issues occur:
1. Revert code to SQLite version
2. Restore from SQLite backup
3. Investigate issues offline
4. Retry migration after fixes

## Files to Modify

### Core Files (Critical)
1. `database.py` - Complete rewrite of connection logic
2. `app.py` - Update imports and SQLite-specific code
3. `requirements.txt` - Add psycopg2
4. `.env` - Add DATABASE_URL
5. `.env.example` - Document DATABASE_URL

### Utility Scripts (Update all)
6. `fix_skyrim_cover.py`
7. `deduplicate_games.py`
8. `fix_superlative_games.py`
9. `reset_superlatives.py`
10. `restore_and_update.py`
11. `scripts/export_db_schema_excel.py`
12. `verify_aggregates.py`
13. `show_schema.py`
14. `steam_updater.py`
15. `setup_admin.py`
16. `migrate_superlatives.py`
17. `update_aggregates.py`
18. `make_admin.py`

### New Files (Create)
19. `create_postgres_schema.py` - Schema creation script
20. `migrate_sqlite_to_postgres.py` - Data migration script
21. `test_postgres_migration.py` - Validation tests

### Documentation (Update)
22. `README.md` - Update database setup instructions
23. `DEPLOYMENT_GUIDE.md` - Add PostgreSQL deployment steps
24. `DATABASE_GUIDE.md` - Update for PostgreSQL

## SQL Syntax Conversion Reference

### Data Types
| SQLite | PostgreSQL |
|--------|------------|
| INTEGER | INTEGER or BIGINT |
| TEXT | TEXT or VARCHAR |
| REAL | REAL or DOUBLE PRECISION |
| BLOB | BYTEA |
| INTEGER PRIMARY KEY AUTOINCREMENT | SERIAL PRIMARY KEY |

### Auto-increment
```sql
-- SQLite
id INTEGER PRIMARY KEY AUTOINCREMENT

-- PostgreSQL
id SERIAL PRIMARY KEY
-- or for large tables
id BIGSERIAL PRIMARY KEY
```

### UPSERT
```sql
-- SQLite
INSERT INTO table (col1, col2) VALUES (?, ?)
ON CONFLICT(col1) DO UPDATE SET col2 = ?

-- PostgreSQL (need constraint or columns)
INSERT INTO table (col1, col2) VALUES (%s, %s)
ON CONFLICT (col1) DO UPDATE SET col2 = EXCLUDED.col2
```

### Parameter Placeholders
```python
# SQLite uses ?
cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))

# PostgreSQL uses %s
cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
```

### Schema Introspection
```sql
-- SQLite
SELECT name FROM sqlite_master WHERE type='table'
PRAGMA table_info(table_name)

-- PostgreSQL
SELECT tablename FROM pg_tables WHERE schemaname='public'
SELECT column_name, data_type FROM information_schema.columns WHERE table_name='table_name'
```

## Risk Mitigation

### High-Risk Areas
1. **UPSERT operations** - Most complex change, needs thorough testing
2. **Transaction handling** - PostgreSQL stricter than SQLite
3. **Concurrent access** - PostgreSQL behaves differently under load
4. **Date/time handling** - May have subtle differences

### Medium-Risk Areas
1. **Schema creation** - ALTER TABLE syntax changes
2. **Foreign key constraints** - Always enforced in PostgreSQL
3. **String functions** - Minor differences possible
4. **Type casting** - PostgreSQL stricter with types

### Low-Risk Areas
1. **SELECT queries** - Mostly compatible
2. **Basic CRUD** - Works the same
3. **Ordering and filtering** - Compatible
4. **Aggregations** - Compatible

## Performance Considerations

### PostgreSQL Advantages
- Better concurrent write handling
- Query optimizer
- Indexing options
- Full-text search built-in
- JSON support for future features

### Optimization Opportunities
1. Add indexes for frequently queried columns
2. Use connection pooling
3. Optimize N+1 query patterns
4. Use EXPLAIN ANALYZE for slow queries
5. Consider materialized views for complex aggregations

## Timeline Estimate

- **Phase 1** (Setup): 1-2 hours
- **Phase 2** (database.py): 4-6 hours
- **Phase 3** (app.py + utilities): 6-8 hours
- **Phase 4** (Migration scripts): 4-6 hours
- **Phase 5** (Connection pooling): 2-3 hours
- **Phase 6** (Testing): 8-12 hours
- **Phase 7** (Deployment prep): 2-4 hours

**Total**: 27-41 hours (3-5 full days)

## Success Criteria

- [ ] All 7 tables created in PostgreSQL with correct schema
- [ ] All existing data migrated successfully
- [ ] All 16 utility scripts updated and working
- [ ] All application features working identically
- [ ] No data loss during migration
- [ ] Foreign key constraints functioning
- [ ] Transaction handling working correctly
- [ ] Connection pooling implemented
- [ ] Performance equal to or better than SQLite
- [ ] Complete test coverage
- [ ] Documentation updated
- [ ] Rollback plan tested

## Additional Considerations

### Environment Variables
- Use DATABASE_URL for PostgreSQL connection
- Remove SQLite-specific paths
- Clear error messages if database unavailable

### Migration Approach
- **Clean cutover**: No backwards compatibility needed
- SQLite will be completely replaced with PostgreSQL
- One-time data migration from existing ratings.db
- Keep SQLite backup only for emergency rollback

### Future Enhancements
- Consider using SQLAlchemy ORM for better abstraction
- Implement Alembic for schema migrations
- Add database health checks
- Implement backup automation for PostgreSQL
