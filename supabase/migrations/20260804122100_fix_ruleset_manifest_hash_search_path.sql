-- Supabase installs pgcrypto in the extensions schema. The atomic ruleset
-- approval transaction uses pgcrypto.digest while retaining an explicit,
-- locked search path for its SECURITY DEFINER execution.

alter function public.approve_janani_clinical_safety_ruleset_internal(
  uuid, text, text[], uuid[], timestamptz, timestamptz, uuid
) set search_path = public, extensions;

notify pgrst, 'reload schema';
