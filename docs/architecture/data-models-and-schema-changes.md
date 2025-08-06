# Data Models and Schema Changes

### New Data Models

#### TestAchievementProgress
**Purpose:** Isolated testing data for achievement system verification
**Integration:** Separate test schema, mirrors production models

**Key Attributes:**
- test_user_id: int - Mock Discord user ID for testing
- test_achievement_id: int - Test achievement identifier
- test_progress: float - Progress value for testing scenarios
- test_completed_at: datetime - Completion timestamp for testing

**Relationships:**
- **With Existing:** Mirrors production achievement_progress table structure
- **With New:** Links to test fixtures and scenarios

#### TestCurrencyTransaction
**Purpose:** Testing currency system operations and edge cases
**Integration:** Test-only model for transaction testing

**Key Attributes:**
- test_transaction_id: int - Test transaction identifier
- test_from_user: int - Source user for testing
- test_to_user: int - Target user for testing
- test_amount: decimal - Transaction amount for testing

**Relationships:**
- **With Existing:** Mirrors production currency transaction patterns
- **With New:** Part of comprehensive test data suite

### Schema Integration Strategy
**Database Changes Required:**
- **New Tables:** Test-specific mirror tables in dedicated test schema
- **Modified Tables:** None - production schema remains untouched
- **New Indexes:** Performance indexes for test data queries
- **Migration Strategy:** Test schema creation through pytest fixtures

**Backward Compatibility:**
- Production database schema remains completely unchanged
- Test data isolation prevents any impact on live operations
