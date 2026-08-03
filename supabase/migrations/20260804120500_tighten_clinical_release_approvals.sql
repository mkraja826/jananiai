-- Validate each approval link independently so one valid reviewer cannot mask an expired reviewer.

create or replace function public.validate_janani_clinical_release_approval()
returns trigger
language plpgsql
set search_path = public
as $$
declare
  v_release public.clinical_safety_releases%rowtype;
  v_review public.clinical_safety_rule_reviews%rowtype;
  v_reviewer public.clinical_safety_reviewers%rowtype;
begin
  select * into v_release
  from public.clinical_safety_releases release_row
  where release_row.id = new.release_id;

  select * into v_review
  from public.clinical_safety_rule_reviews review_row
  where review_row.id = new.review_id;

  select * into v_reviewer
  from public.clinical_safety_reviewers reviewer_row
  where reviewer_row.id = new.reviewer_id;

  if v_release.id is null or v_review.id is null or v_reviewer.id is null then
    raise exception 'Release approval references an unknown record' using errcode = 'P0002';
  end if;
  if v_review.candidate_id <> v_release.candidate_id
    or v_review.candidate_digest <> v_release.candidate_digest
    or v_review.decision <> 'approve'
  then
    raise exception 'Review does not approve the exact release candidate digest'
      using errcode = '42501';
  end if;
  if v_review.reviewer_id <> new.reviewer_id
    or v_review.reviewer_role <> new.reviewer_role
    or v_reviewer.role <> new.reviewer_role
  then
    raise exception 'Release approval reviewer identity or role mismatch'
      using errcode = '42501';
  end if;
  if new.reviewer_role not in ('obstetrician', 'clinical_safety') then
    raise exception 'Reviewer role cannot approve a clinical safety release'
      using errcode = '42501';
  end if;
  if not v_reviewer.active
    or v_reviewer.credential_verified_at > v_release.approved_at
    or v_reviewer.credential_expires_at <= v_release.approved_at
  then
    raise exception 'Approving reviewer credentials are not current at release approval'
      using errcode = '42501';
  end if;

  return new;
end;
$$;

create trigger validate_clinical_safety_release_approval
before insert on public.clinical_safety_release_approvals
for each row execute function public.validate_janani_clinical_release_approval();

comment on function public.validate_janani_clinical_release_approval is
  'Validates every approval against the exact candidate digest and current reviewer credentials.';
