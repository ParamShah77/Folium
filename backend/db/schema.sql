-- ============================================================================
-- FinAI Decision Intelligence — reference schema (DOCUMENTATION ONLY, §2G)
--
-- This file is NOT executed by Alembic and is NOT the source of truth. The
-- authoritative, ordered DDL lives in backend/db/migrations/versions/0001..0007.
-- It is kept here as a single-file overview of the full §2C schema for humans.
--
-- To create the schema, run migrations (see SETUP.md), NOT this file:
--     alembic -c backend/db/migrations/alembic.ini upgrade head
-- ============================================================================

-- Extension providing gen_random_uuid() (migration 0001).
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- --- users (0001) -----------------------------------------------------------
-- Financial-profile columns are all OPTIONAL (Amendment 3).
-- Columns: user_id, email, email_verified, password_hash, oauth_provider,
--   oauth_id, name, role, is_active, mfa_enabled, mfa_secret_enc,
--   profile_picture, phone, age, monthly_income, monthly_expense,
--   risk_tolerance, investment_horizon, has_emergency_fund, financial_strategy,
--   goal, created_at, updated_at, last_login_at, deleted_at, deletion_reason.
-- Indexes: idx_users_email, idx_users_deleted.

-- --- refresh_tokens, mfa_backup_codes, mfa_recovery_requests,
--     profile_change_log (0002) --------------------------------------------
-- refresh_tokens: token_hash (SHA-256), jti, expires_at, revoked, ua, ip.
--   Indexes: idx_refresh_tokens_hash, idx_refresh_tokens_user.
-- MFA tables exist now for schema completeness; populated from Milestone 2.

-- --- decisions (0003) -------------------------------------------------------
-- Full decision + pipeline + ML-output + JSONB columns (§2C).
-- Indexes: idx_decisions_user_id, idx_decisions_status (partial),
--   idx_decisions_created_at (DESC).

-- --- audit_logs (0004) ------------------------------------------------------
-- SHA-256 chain (payload_hash, previous_hash, chain_hash). Append-only via
-- RULES audit_no_update / audit_no_delete (DO INSTEAD NOTHING).
-- Indexes: idx_audit_user_id, idx_audit_decision_id.

-- --- portfolios, bias_profiles, market_cache (0005) -------------------------
-- portfolios index: idx_portfolios_user_id (+ updated_at trigger).
-- market_cache is shared (not user-owned) -> no RLS.

-- --- sip_registrations, kite_tokens (0006) ---------------------------------
-- Kite is DEFERRED (Amendment 1) but kept in the schema for future use.

-- --- RLS + admin view (0007) ------------------------------------------------
-- RLS ENABLED + FORCED on: decisions, audit_logs, portfolios,
--   sip_registrations, profile_change_log. Policy (Amendment 9):
--     USING (user_id = NULLIF(current_setting('app.current_user_id', true), '')::uuid)
-- Role app_user created for least-privilege production use.
-- admin_stats_view: 90-day aggregate, NO user_id / PII / financial figures (§2F).
