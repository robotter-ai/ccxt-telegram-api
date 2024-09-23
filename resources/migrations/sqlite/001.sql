create table main.user
(
    exchange_id          TEXT    not null,
    exchange_environment TEXT    not null,
    telegram_id          integer not null,
    api_key              TEXT    not null,
    api_secret           TEXT    not null,
    sub_account_id       integer,
    constraint user_pk
        primary key (exchange_id, exchange_environment, api_key)
);
