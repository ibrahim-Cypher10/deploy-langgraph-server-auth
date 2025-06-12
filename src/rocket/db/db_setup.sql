create table public.videos (
  id text not null,
  published_at timestamp with time zone not null,
  title text null,
  url text not null,
  comment_count integer null,
  analysis_summary text null,
  description text null,
  channel_title text null,
  duration text null,
  view_count integer null,
  like_count integer null,
  constraint videos_pkey primary key (id)
) TABLESPACE pg_default;

alter table public.videos enable row level security;

create table public.comments (
  id text not null,
  created_at timestamp with time zone not null default now(),
  text text null,
  like_count integer null,
  reply_count integer null,
  video_id text not null,
  constraint comments_pkey primary key (id),
  constraint comments_video_id_fkey foreign KEY (video_id) references videos (id) on update CASCADE on delete CASCADE
) TABLESPACE pg_default;

alter table public.comments enable row level security;

/* add RLS policies */
