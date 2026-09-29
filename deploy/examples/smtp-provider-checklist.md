# SMTP provider checklist for account recovery

Recovery stays disabled (`RECOVERY_ENABLED=false`) until everything below is done in
staging. The backend sends two messages, address verification and password reset,
over TLS SMTP after the database commit. Each contains a single-use link whose secret
is in the URL fragment. See `docs/deployment.md` for the settings and delivery limits.

## Choose the provider or relay

- [ ] A transactional provider (or the university's approved relay) that allows
      automated account email and has a clear data-retention policy.
- [ ] It supports STARTTLS on 587 (`SMTP_TLS=starttls`) or implicit TLS on 465
      (`SMTP_TLS=implicit`) with a publicly trusted certificate. The backend always
      verifies the certificate and has no option to turn that off.
- [ ] The sending limits are well above expected recovery volume. The backend already
      limits recovery to `RECOVERY_RATE_LIMIT` requests per client IP per window.

## Protect the link secrets

- [ ] **Turn off click tracking and link rewriting.** A rewritten link sends the
      recipient through the provider, and the provider stores the original URL,
      fragment secret included.
- [ ] Turn off open tracking pixels and message-content archiving, or set the
      shortest retention the provider allows.
- [ ] Restrict dashboard access to operators who need it, because message logs may
      show recipients and subjects.

## Domain and sender

- [ ] `SMTP_FROM` is a verified sender on a domain you control, ideally a subdomain
      such as `accounts@mail.example.edu`.
- [ ] SPF includes the provider, DKIM signing is enabled for the domain, and DMARC is
      published (start with `p=none` and reporting, then tighten).
- [ ] Bounces and complaints go to a monitored address or webhook, and the provider
      suppresses repeatedly failing addresses.

## Credentials and configuration

- [ ] Create a sending-only credential or API key for this service; don't reuse a
      personal or admin login.
- [ ] Put `SMTP_HOST`, `SMTP_PORT`, `SMTP_TLS`, `SMTP_USERNAME`, `SMTP_PASSWORD` and
      `SMTP_FROM` in the service's environment file (root-owned, mode 0640, group
      `gopher`). Never commit them or put them in the frontend.
- [ ] `RECOVERY_FRONTEND_URL` is the HTTPS `/recovery` page, with no query or fragment,
      served with the headers in the frontend README.
- [ ] Have a documented way to rotate the credential and revoke the old one.

## Rehearse in staging

- [ ] With `RECOVERY_ENABLED=true` in staging, enroll a real test mailbox, verify it,
      request a reset and complete it. Check the link opens the recovery page and the
      fragment disappears from the address bar.
- [ ] Check the message passes SPF, DKIM and DMARC in the recipient's headers and
      doesn't land in spam at the main university mail provider.
- [ ] Break the credentials on purpose and confirm the API still answers 202, the
      failure increments `gopher_recovery_deliveries_total{success="false"}`, and no
      secret appears in logs.
- [ ] Alert on delivery failures. Delivery is best-effort with no durable queue, so
      users retry if a message never arrives.
