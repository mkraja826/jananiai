-- Refresh the PostgREST function signature cache after adding atomic ruleset RPCs.
-- Supabase and PostgREST support schema refresh through the pgrst notification channel.

notify pgrst, 'reload schema';
