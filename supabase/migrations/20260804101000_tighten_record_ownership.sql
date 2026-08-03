-- Prevent cross-user pregnancy reassignment even when writes use a privileged backend path.

create or replace function public.enforce_janani_pregnancy_owner()
returns trigger
language plpgsql
set search_path = public
as $$
begin
  if new.pregnancy_id is not null and not exists (
    select 1
    from public.pregnancies pregnancy
    where pregnancy.id = new.pregnancy_id
      and pregnancy.user_id = new.user_id
  ) then
    raise exception 'pregnancy_id does not belong to record owner';
  end if;
  return new;
end;
$$;

create trigger enforce_medication_pregnancy_owner
before insert or update of user_id, pregnancy_id on public.medication_records
for each row execute function public.enforce_janani_pregnancy_owner();

create trigger enforce_appointment_pregnancy_owner
before insert or update of user_id, pregnancy_id on public.appointment_records
for each row execute function public.enforce_janani_pregnancy_owner();

create trigger enforce_attachment_pregnancy_owner
before insert or update of user_id, pregnancy_id on public.attachment_records
for each row execute function public.enforce_janani_pregnancy_owner();

drop policy if exists medication_records_update_own on public.medication_records;
create policy medication_records_update_own
on public.medication_records for update
using (auth.uid() = user_id)
with check (
  auth.uid() = user_id
  and (
    pregnancy_id is null
    or exists (
      select 1 from public.pregnancies pregnancy
      where pregnancy.id = pregnancy_id and pregnancy.user_id = auth.uid()
    )
  )
);

drop policy if exists appointment_records_update_own on public.appointment_records;
create policy appointment_records_update_own
on public.appointment_records for update
using (auth.uid() = user_id)
with check (
  auth.uid() = user_id
  and (
    pregnancy_id is null
    or exists (
      select 1 from public.pregnancies pregnancy
      where pregnancy.id = pregnancy_id and pregnancy.user_id = auth.uid()
    )
  )
);

drop policy if exists attachment_records_update_own on public.attachment_records;
create policy attachment_records_update_own
on public.attachment_records for update
using (auth.uid() = user_id)
with check (
  auth.uid() = user_id
  and storage_object_path like auth.uid()::text || '/%'
  and (
    pregnancy_id is null
    or exists (
      select 1 from public.pregnancies pregnancy
      where pregnancy.id = pregnancy_id and pregnancy.user_id = auth.uid()
    )
  )
);
