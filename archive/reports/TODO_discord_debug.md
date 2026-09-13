# TODO: Discord push debugging

- [ ] Add explicit logging of webhook URL presence + first 20 chars (redacted) before posting
- [ ] Add logging of HTTP status + response body always (even on 200/204)
- [ ] Ensure the code path you run actually calls push_to_discord
- [ ] Add a `--push-discord-always` override (bypass gating)
- [ ] Add a `--dry-run-discord` option to print payload without sending

