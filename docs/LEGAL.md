# Legal and ethical frame

**This is not legal advice.** The chapter 21 material of the design document
must be validated by a lawyer before any real-world deployment on third-party
systems.

Piège makes authorisation a **technical precondition**, not a contractual nicety:

- Nothing executes without a signed, dated, scoped mandate within its validity
  window (`MandatInvalide`, `MandatExpire`).
- Production is banned by the catalogue itself for the families that must never
  touch it — no mandate can lift it (`ProductionInterdite`).
- Every probe and response is logged in an append-only, hash-chained journal
  with an immutable marker distinguishing a test probe from real traffic.
- The service only applies guardrail and policy fixes, after explicit human
  approval; the prompt, the code and the customer corpus are never modified.
- The demonstration dataset is 100 % synthetic and watermarked
  `SYNTHETIQUE — DEMONSTRATION`; tests assert that no email address, identity
  number or real personal datum appears in it.
- Tests that would degrade availability (saturation, unbounded loops) are
  forbidden by design: the catalogue declares bounded call budgets and turns,
  and the engine stops cleanly at the threshold.
