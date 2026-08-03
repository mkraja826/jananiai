-- Add the missing owner-read policy for privacy-minimised safety audit events.

create policy safety_audit_events_select_own
on public.safety_audit_events for select
to authenticated
using (auth.uid() = user_id);
