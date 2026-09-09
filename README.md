# Ratepension Stock Server

Live aktiedata server for ratepension dashboard.

## Setup

`ash
pip install -r requirements.txt
python stock-server.py
`

Server kører på http://localhost:5000

## API

- GET /api/portfolio - Hele porteføljen
- GET /api/health - Server status

## Railway Deployment

Deploy med:
`
git push origin master
`

Railway læser Procfile automatisk.
