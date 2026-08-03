-- Backend-only attachment extraction writer.
-- The mobile client and authenticated user role cannot execute this function.

create or replace function public.record_janani_attachment_extraction(
  p_extraction_id uuid,
  p_attachment_id uuid,
  p_extractor_name text,
  p_extractor_version text,
  p_extracted_text text,
  p_confidence numeric
)
returns uuid
language plpgsql
security definer
set search_path = public
as $$
begin
  if auth.role() <> 'service_role' then
    raise exception 'Service role required' using errcode = '42501';
  end if;

  if not exists (
    select 1
    from public.attachment_records attachment
    where attachment.id = p_attachment_id
  ) then
    raise exception 'Attachment not found' using errcode = 'P0002';
  end if;

  if p_extractor_name is null or length(trim(p_extractor_name)) = 0 then
    raise exception 'Extractor name is required' using errcode = '22023';
  end if;

  if p_extractor_version is null or length(trim(p_extractor_version)) = 0 then
    raise exception 'Extractor version is required' using errcode = '22023';
  end if;

  if p_extracted_text is null or length(trim(p_extracted_text)) = 0 then
    raise exception 'Extracted text is required' using errcode = '22023';
  end if;

  if p_confidence is not null and (p_confidence < 0 or p_confidence > 1) then
    raise exception 'Extraction confidence must be between 0 and 1'
      using errcode = '22023';
  end if;

  insert into public.attachment_extractions (
    id,
    attachment_id,
    extractor_name,
    extractor_version,
    extracted_text,
    confidence,
    user_confirmed_at
  )
  values (
    p_extraction_id,
    p_attachment_id,
    p_extractor_name,
    p_extractor_version,
    p_extracted_text,
    p_confidence,
    null
  )
  on conflict (id) do update
  set
    attachment_id = excluded.attachment_id,
    extractor_name = excluded.extractor_name,
    extractor_version = excluded.extractor_version,
    extracted_text = excluded.extracted_text,
    confidence = excluded.confidence,
    user_confirmed_at = null;

  update public.attachment_records
  set
    extraction_status = 'completed',
    confirmation_status = 'unconfirmed',
    latest_extraction_confidence = p_confidence
  where id = p_attachment_id;

  return p_extraction_id;
end;
$$;

revoke all on function public.record_janani_attachment_extraction(
  uuid, uuid, text, text, text, numeric
) from public, anon, authenticated;

grant execute on function public.record_janani_attachment_extraction(
  uuid, uuid, text, text, text, numeric
) to service_role;

comment on function public.record_janani_attachment_extraction is
  'Service-role-only atomic extraction writer. Users must confirm extracted text separately.';
