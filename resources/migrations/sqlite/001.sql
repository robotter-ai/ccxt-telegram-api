create table user (
	id TEXT	not null,
	exchange_id TEXT not null,
	exchange_environment TEXT not null,
	telegram_id integer	not null,
	exchange_api_key TEXT not null,
	exchange_api_secret TEXT	not null,
	data TEXT,
	constraint user_pk primary key (id)
);

create table user_token (
	token TEXT	not null,
	user_id TEXT not null,
	constraint user_token_pk primary key (token)
);
