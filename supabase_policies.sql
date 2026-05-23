create or replace function public.is_muni_user()
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select exists (
    select 1
    from public.users
    where lower(email) = lower(auth.jwt() ->> 'email')
      and status = 'active'
  );
$$;

grant execute on function public.is_muni_user() to anon, authenticated;

alter table public.users enable row level security;
drop policy if exists "read own active profile" on public.users;
create policy "read own active profile"
on public.users for select
to authenticated
using (lower(email) = lower(auth.jwt() ->> 'email') and status = 'active');

alter table public.settings enable row level security;
drop policy if exists "muni users read settings" on public.settings;
drop policy if exists "muni users write settings" on public.settings;
create policy "muni users read settings" on public.settings for select to authenticated using (public.is_muni_user());
create policy "muni users write settings" on public.settings for all to authenticated using (public.is_muni_user()) with check (public.is_muni_user());

alter table public.content enable row level security;
drop policy if exists "muni users read content" on public.content;
drop policy if exists "muni users write content" on public.content;
create policy "muni users read content" on public.content for select to authenticated using (public.is_muni_user());
create policy "muni users write content" on public.content for all to authenticated using (public.is_muni_user()) with check (public.is_muni_user());

alter table public.services enable row level security;
drop policy if exists "muni users read services" on public.services;
drop policy if exists "muni users write services" on public.services;
create policy "muni users read services" on public.services for select to authenticated using (public.is_muni_user());
create policy "muni users write services" on public.services for all to authenticated using (public.is_muni_user()) with check (public.is_muni_user());

alter table public.documents enable row level security;
drop policy if exists "muni users read documents" on public.documents;
drop policy if exists "muni users write documents" on public.documents;
create policy "muni users read documents" on public.documents for select to authenticated using (public.is_muni_user());
create policy "muni users write documents" on public.documents for all to authenticated using (public.is_muni_user()) with check (public.is_muni_user());

alter table public.mayors enable row level security;
drop policy if exists "muni users read mayors" on public.mayors;
drop policy if exists "muni users write mayors" on public.mayors;
create policy "muni users read mayors" on public.mayors for select to authenticated using (public.is_muni_user());
create policy "muni users write mayors" on public.mayors for all to authenticated using (public.is_muni_user()) with check (public.is_muni_user());

alter table public.municipal_authorities enable row level security;
drop policy if exists "muni users read municipal authorities" on public.municipal_authorities;
drop policy if exists "muni users write municipal authorities" on public.municipal_authorities;
create policy "muni users read municipal authorities" on public.municipal_authorities for select to authenticated using (public.is_muni_user());
create policy "muni users write municipal authorities" on public.municipal_authorities for all to authenticated using (public.is_muni_user()) with check (public.is_muni_user());

alter table public.contacts enable row level security;
drop policy if exists "muni users read contacts" on public.contacts;
drop policy if exists "muni users write contacts" on public.contacts;
create policy "muni users read contacts" on public.contacts for select to authenticated using (public.is_muni_user());
create policy "muni users write contacts" on public.contacts for all to authenticated using (public.is_muni_user()) with check (public.is_muni_user());

alter table public.content_attachments enable row level security;
drop policy if exists "muni users read content attachments" on public.content_attachments;
drop policy if exists "muni users write content attachments" on public.content_attachments;
create policy "muni users read content attachments" on public.content_attachments for select to authenticated using (public.is_muni_user());
create policy "muni users write content attachments" on public.content_attachments for all to authenticated using (public.is_muni_user()) with check (public.is_muni_user());

alter table public.civic_requests enable row level security;
drop policy if exists "public create civic requests" on public.civic_requests;
drop policy if exists "muni users read civic requests" on public.civic_requests;
drop policy if exists "muni users update civic requests" on public.civic_requests;
create policy "public create civic requests" on public.civic_requests for insert to anon, authenticated with check (true);
create policy "muni users read civic requests" on public.civic_requests for select to authenticated using (public.is_muni_user());
create policy "muni users update civic requests" on public.civic_requests for update to authenticated using (public.is_muni_user()) with check (public.is_muni_user());

alter table public.civic_request_attachments enable row level security;
drop policy if exists "public create civic request attachments" on public.civic_request_attachments;
drop policy if exists "muni users read civic request attachments" on public.civic_request_attachments;
create policy "public create civic request attachments" on public.civic_request_attachments for insert to anon, authenticated with check (true);
create policy "muni users read civic request attachments" on public.civic_request_attachments for select to authenticated using (public.is_muni_user());

alter table public.audit_logs enable row level security;
drop policy if exists "muni users create audit logs" on public.audit_logs;
drop policy if exists "muni users read audit logs" on public.audit_logs;
create policy "muni users create audit logs" on public.audit_logs for insert to authenticated with check (public.is_muni_user());
create policy "muni users read audit logs" on public.audit_logs for select to authenticated using (public.is_muni_user());

drop policy if exists "public read municipal files" on storage.objects;
drop policy if exists "authenticated upload municipal files" on storage.objects;
drop policy if exists "anonymous upload civic attachments" on storage.objects;
create policy "public read municipal files"
on storage.objects for select
to anon, authenticated
using (bucket_id = 'municipalidad-marcala');

create policy "authenticated upload municipal files"
on storage.objects for insert
to authenticated
with check (bucket_id = 'municipalidad-marcala' and public.is_muni_user());

create policy "anonymous upload civic attachments"
on storage.objects for insert
to anon
with check (bucket_id = 'municipalidad-marcala' and name like 'attachments/%');
