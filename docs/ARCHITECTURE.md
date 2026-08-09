# Architecture

## Modes

1. Local client-side testing mode: app communicates with local FastAPI backend.
2. Future server mode: backend can be deployed to Railway.

## Flow

START -> connect adapter -> wait candle close -> analyze -> place 60s trade -> settle -> log result.

## Safety

Default is paper/demo mode. Real adapter must be implemented explicitly.
