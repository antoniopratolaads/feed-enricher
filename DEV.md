# Feed Enricher Pro — Sviluppo locale

## Setup (una volta)

1. Python 3.11+ installato (attualmente 3.14 OK)
2. Git installato
3. SSH key per droplet già configurata (`~/.ssh/id_ed25519`)

La venv e le deps sono già state installate in `.venv/`.
Il `config.json` è già stato sincronizzato dal droplet.

## Avvio dev server

Doppio click su `start.bat` oppure:
```cmd
start.bat
```

Apre `http://localhost:8501` con hot reload (modifica file → reload automatico).

## Deploy su droplet

Doppio click su `deploy.bat` oppure con messaggio custom:
```cmd
deploy.bat "fix sidebar collapse"
```

Fa: `git add -A && git commit && git push && ssh droplet → pull + rebuild`.

## Storage locale

- Config / cache / sessioni: `%USERPROFILE%\.feed_enricher\`
  - `config.json` — API keys (sync iniziale dal droplet)
  - `cache/` — enrichment hash cache
  - `sessions/` — snapshot progetti
  - `clients/` — multi-cliente feed storico
  - `style_guides/` — style guide per sessione
  - `prompts.json` — prompt templates versionati

Sessioni locali **indipendenti** dal droplet. Per copiarle:
```cmd
ssh root@161.35.91.142 "docker exec feed-enricher tar czf - -C /root/.feed_enricher sessions" | tar xzf - -C %USERPROFILE%\.feed_enricher
```

## Flow tipico

1. Avvia `start.bat`
2. Modifica codice in VS Code
3. Salva → browser ricarica automaticamente in 1-2s
4. Test locale su `http://localhost:8501`
5. Quando stabile: `deploy.bat "descrizione fix"` → online su `http://161.35.91.142/feed/`

## Troubleshooting

**"python non trovato"** — installa da python.org o Microsoft Store.

**Deps mancanti** — elimina `.venv/` e rilancia `start.bat` (reinstalla tutto).

**Porta 8501 occupata** — chiudi altre app Streamlit o cambia porta:
```cmd
.venv\Scripts\streamlit run app.py --server.port 8502
```

**SSH key password** — aggiungi alla ssh-agent:
```cmd
ssh-add C:\Users\%USERNAME%\.ssh\id_ed25519
```
